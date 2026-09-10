import json
import re
from pathlib import Path
from typing import Dict, List, Optional

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


EXTRACTOR_VERSION = "2"

# IMPORTANT:
# Caption detection is ANCHORED at the beginning of the text block.
# Body sentences such as "... (Fig. 2A)" are therefore ignored.
CAPTION_START_RE = re.compile(
    r"^\s*(fig(?:ure)?\.?\s*(\d+[A-Za-z]?))\s*[.:]?\s+",
    re.IGNORECASE,
)


def pymupdf_available() -> bool:
    return fitz is not None


def normalize_figure_label(label: str) -> str:
    label = (label or "").strip()
    if not label:
        return ""

    m = re.search(r"(?i)(?:fig(?:ure)?\.?)\s*(\d+[A-Za-z]?)", label)

    if not m:
        return label

    return f"Fig. {m.group(1)}"


def label_key(label: str) -> str:
    norm = normalize_figure_label(label)

    m = re.search(r"(?i)fig\.\s*(\d+)([A-Za-z]?)", norm)

    if not m:
        return re.sub(r"\W+", "", norm.lower())

    return f"fig{m.group(1)}{m.group(2).lower()}"


def figure_sort_key(item: Dict):
    label = item.get("figure_label", "")

    m = re.search(r"(\d+)([A-Za-z]?)", label)

    if not m:
        return (9999, label)

    return (
        int(m.group(1)),
        m.group(2).lower(),
    )


def _block_text(block: dict) -> str:
    out = []

    for line in block.get("lines", []):
        for span in line.get("spans", []):
            value = span.get("text", "")

            if value:
                out.append(value)

    return " ".join(out).strip()


def _horizontal_overlap(a, b) -> float:
    ax0, _, ax1, _ = a
    bx0, _, bx1, _ = b

    overlap = max(
        0.0,
        min(ax1, bx1) - max(ax0, bx0),
    )

    denom = max(
        1.0,
        min(ax1 - ax0, bx1 - bx0),
    )

    return overlap / denom


def _looks_like_body_prose(text: str) -> bool:
    text = (text or "").strip()

    if len(text) < 120:
        return False

    if CAPTION_START_RE.match(text):
        return False

    words = text.split()

    if len(words) < 22:
        return False

    # Figure labels / axis labels are usually much shorter and less prose-like.
    punctuation = sum(
        text.count(ch)
        for ch in [".", ",", ";", ":"]
    )

    return punctuation >= 2


def _caption_score(text: str, bbox, page_height: float) -> float:
    """
    If duplicate caption-like blocks somehow exist, prefer a proper,
    information-rich caption rather than a stray heading.
    """
    score = 0.0

    if CAPTION_START_RE.match(text):
        score += 10.0

    length = len(text)

    if 60 <= length <= 2500:
        score += 3.0

    if re.search(r"\(\s*[A-H]\s*\)", text):
        score += 2.0

    if re.search(r"(?i)\b[A-H]\s+(?:and|–|-)\s+[A-H]\b", text):
        score += 1.0

    # Real captions are frequently in the middle/lower portion of a page.
    y0 = bbox[1]
    if y0 > page_height * 0.25:
        score += 0.5

    return score


def _find_real_caption_blocks(page) -> List[Dict]:
    page_dict = page.get_text("dict")
    candidates = []

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        text = _block_text(block)

        match = CAPTION_START_RE.match(text)

        if not match:
            continue

        bbox = tuple(
            block.get(
                "bbox",
                (0, 0, 0, 0),
            )
        )

        label = normalize_figure_label(
            match.group(1)
        )

        candidates.append(
            {
                "bbox": bbox,
                "text": text,
                "label": label,
                "key": label_key(label),
                "score": _caption_score(
                    text,
                    bbox,
                    page.rect.height,
                ),
            }
        )

    return candidates


def _column_bounds(page, caption_bbox):
    """
    Use the caption's column instead of the whole page.

    This prevents a right-column figure crop from also including article text
    from the left column.
    """
    page_width = page.rect.width
    margin = 14.0

    x0, _, x1, _ = caption_bbox
    width = max(1.0, x1 - x0)
    width_ratio = width / page_width

    if width_ratio >= 0.70:
        return (
            margin,
            page_width - margin,
        )

    # Single-column caption: expand slightly around the caption width.
    pad = max(
        8.0,
        width * 0.05,
    )

    return (
        max(margin, x0 - pad),
        min(page_width - margin, x1 + pad),
    )


def _find_crop_top(page, caption_bbox, crop_x0, crop_x1):
    """
    Find the latest prose block above the caption in the SAME column.
    The figure should start after that body-text block.

    If no suitable prose block exists, use the top page margin.
    """
    caption_y0 = caption_bbox[1]

    column_rect = (
        crop_x0,
        0,
        crop_x1,
        caption_y0,
    )

    page_dict = page.get_text("dict")
    prose_bottoms = []

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        bbox = tuple(
            block.get(
                "bbox",
                (0, 0, 0, 0),
            )
        )

        text = _block_text(block)

        if not _looks_like_body_prose(text):
            continue

        if bbox[3] >= caption_y0 - 8:
            continue

        if _horizontal_overlap(
            bbox,
            column_rect,
        ) < 0.45:
            continue

        prose_bottoms.append(
            bbox[3]
        )

    if not prose_bottoms:
        return 14.0

    return min(
        caption_y0 - 45.0,
        max(prose_bottoms) + 8.0,
    )


def _image_bbox_candidates(page, caption_bbox, crop_x0, crop_x1):
    """
    Raster panels can give us a stronger visual-bound hint.
    If available, use them to avoid unnecessary prose/whitespace.
    """
    caption_y0 = caption_bbox[1]
    column_rect = (
        crop_x0,
        0,
        crop_x1,
        caption_y0,
    )

    out = []

    try:
        page_dict = page.get_text("dict")

        for block in page_dict.get("blocks", []):
            if block.get("type") != 1:
                continue

            bbox = tuple(
                block.get(
                    "bbox",
                    (0, 0, 0, 0),
                )
            )

            if bbox[1] >= caption_y0:
                continue

            if _horizontal_overlap(
                bbox,
                column_rect,
            ) < 0.25:
                continue

            out.append(bbox)

    except Exception:
        pass

    return out


def _safe_crop(page, rect, zoom=2.1):
    clip = fitz.Rect(rect) & page.rect

    if (
        clip.width < 45
        or clip.height < 45
    ):
        return None

    pix = page.get_pixmap(
        matrix=fitz.Matrix(
            zoom,
            zoom,
        ),
        clip=clip,
        alpha=False,
    )

    return pix.tobytes("png")


def _build_crop(page, caption):
    bbox = caption["bbox"]

    crop_x0, crop_x1 = (
        _column_bounds(
            page,
            bbox,
        )
    )

    crop_top = _find_crop_top(
        page,
        bbox,
        crop_x0,
        crop_x1,
    )

    image_boxes = (
        _image_bbox_candidates(
            page,
            bbox,
            crop_x0,
            crop_x1,
        )
    )

    if image_boxes:
        image_top = min(
            b[1]
            for b in image_boxes
        )

        # Do not move above the prose boundary.
        crop_top = max(
            crop_top,
            image_top - 18.0,
        )

        # If images extend a little outside the caption width,
        # include them, but never invade the opposite article column heavily.
        visual_x0 = min(
            b[0]
            for b in image_boxes
        )
        visual_x1 = max(
            b[2]
            for b in image_boxes
        )

        page_width = page.rect.width

        if (
            visual_x1 - visual_x0
        ) < page_width * 0.72:
            crop_x0 = max(
                12.0,
                min(
                    crop_x0,
                    visual_x0 - 10.0,
                ),
            )

            crop_x1 = min(
                page_width - 12.0,
                max(
                    crop_x1,
                    visual_x1 + 10.0,
                ),
            )

    crop_bottom = (
        bbox[1] - 6.0
    )

    if (
        crop_bottom - crop_top
    ) < 45.0:
        return None, None

    rect = (
        crop_x0,
        crop_top,
        crop_x1,
        crop_bottom,
    )

    return (
        _safe_crop(
            page,
            rect,
        ),
        rect,
    )


def extract_study_figures(
    pdf_bytes: bytes,
    paper_hash: str,
    cache_root: str = "figure_cache/study_figures_v2",
) -> List[Dict]:
    """
    Figure extractor v2.

    Improvements over v1:
    - only caption blocks STARTING with Fig./Figure are accepted
    - one canonical crop per Figure label
    - crop follows the caption column, not the entire page width
    - nearby body prose is used as a crop boundary
    - raster image boxes refine the visual bounds when available
    """
    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is not installed."
        )

    cache_dir = (
        Path(cache_root)
        / paper_hash
    )

    meta_path = (
        cache_dir
        / "figures.json"
    )

    if meta_path.exists():
        try:
            payload = json.loads(
                meta_path.read_text(
                    encoding="utf-8"
                )
            )

            if (
                isinstance(payload, dict)
                and payload.get(
                    "extractor_version"
                ) == EXTRACTOR_VERSION
            ):
                items = payload.get(
                    "figures",
                    [],
                )

                if isinstance(
                    items,
                    list,
                ):
                    return items

        except Exception:
            pass

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    # key -> best caption candidate across the whole paper
    best_by_key = {}

    try:
        for page_index in range(
            len(doc)
        ):
            page = doc[
                page_index
            ]

            for caption in (
                _find_real_caption_blocks(
                    page
                )
            ):
                key = caption["key"]

                candidate = {
                    **caption,
                    "page_index": page_index,
                }

                old = best_by_key.get(
                    key
                )

                if (
                    old is None
                    or candidate["score"]
                    > old["score"]
                    or (
                        candidate["score"]
                        == old["score"]
                        and len(
                            candidate["text"]
                        )
                        > len(
                            old["text"]
                        )
                    )
                ):
                    best_by_key[
                        key
                    ] = candidate

        items = []

        for key, caption in (
            best_by_key.items()
        ):
            page_index = caption[
                "page_index"
            ]

            page = doc[
                page_index
            ]

            png_bytes, crop_rect = (
                _build_crop(
                    page,
                    caption,
                )
            )

            if png_bytes is None:
                continue

            out_name = (
                f"{page_index + 1:03d}_"
                f"{key}.png"
            )

            out_path = (
                cache_dir
                / out_name
            )

            out_path.write_bytes(
                png_bytes
            )

            items.append(
                {
                    "figure_label": caption[
                        "label"
                    ],
                    "figure_key": key,
                    "page_number": (
                        page_index + 1
                    ),
                    "caption": caption[
                        "text"
                    ],
                    "image_path": str(
                        out_path
                    ),
                    "crop_rect": [
                        round(
                            float(v),
                            2,
                        )
                        for v in crop_rect
                    ],
                    "extractor_version": (
                        EXTRACTOR_VERSION
                    ),
                }
            )

        items.sort(
            key=figure_sort_key
        )

    finally:
        doc.close()

    meta_path.write_text(
        json.dumps(
            {
                "extractor_version": EXTRACTOR_VERSION,
                "figures": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return items


def find_matching_figure(
    extracted_figures: List[Dict],
    figure_label: str,
) -> Optional[Dict]:
    target = label_key(
        figure_label
    )

    if not target:
        return None

    by_key = {
        item.get(
            "figure_key"
        ): item
        for item in extracted_figures
    }

    if target in by_key:
        return by_key[
            target
        ]

    # AI may return "Figure 2A" while local extraction stores the whole "Fig. 2".
    target_number = re.search(
        r"fig(\d+)",
        target,
    )

    if target_number:
        base_key = (
            "fig"
            + target_number.group(1)
        )

        if base_key in by_key:
            return by_key[
                base_key
            ]

    return None
