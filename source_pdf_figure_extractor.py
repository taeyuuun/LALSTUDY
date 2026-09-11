import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


EXTRACTOR_VERSION = "1"

CAPTION_START_RE = re.compile(
    r"^\s*(?:fig(?:ure)?\.?\s*)(\d+)\b",
    re.IGNORECASE,
)


def available() -> bool:
    return fitz is not None


def _block_text(block: Dict) -> str:
    parts = []

    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")

            if text:
                parts.append(str(text))

    return " ".join(parts).strip()


def _figure_key(number: str) -> str:
    return f"fig{int(number)}"


def _looks_like_prose(text: str) -> bool:
    text = (text or "").strip()

    if CAPTION_START_RE.match(text):
        return False

    words = text.split()

    if len(words) < 20:
        return False

    punctuation = sum(
        text.count(ch)
        for ch in [".", ",", ";", ":"]
    )

    return punctuation >= 2


def _horizontal_overlap_ratio(a, b) -> float:
    try:
        ax0, _, ax1, _ = [float(v) for v in a]
        bx0, _, bx1, _ = [float(v) for v in b]
    except Exception:
        return 0.0

    overlap = max(
        0.0,
        min(ax1, bx1) - max(ax0, bx0),
    )

    denom = max(
        1.0,
        min(ax1 - ax0, bx1 - bx0),
    )

    return overlap / denom


def _find_caption_candidates(doc) -> List[Dict]:
    """
    Only accept text blocks that START with Fig. N / Figure N.
    Body references such as "(Fig. 7A)" never match.
    """
    candidates = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]

        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue

            text = _block_text(block)

            match = CAPTION_START_RE.match(text)

            if not match:
                continue

            bbox = block.get("bbox")

            if (
                not bbox
                or len(bbox) != 4
            ):
                continue

            number = match.group(1)

            score = len(text)

            # Real scientific captions often enumerate panels.
            if re.search(
                r"\(\s*A\s*\)",
                text,
                flags=re.IGNORECASE,
            ):
                score += 300

            candidates.append(
                {
                    "number": number,
                    "figure_label": f"Fig. {int(number)}",
                    "figure_key": _figure_key(number),
                    "page_idx": page_idx,
                    "bbox": [float(v) for v in bbox],
                    "caption": text,
                    "score": score,
                }
            )

    # Deduplicate by Figure number, preferring the richest caption block.
    best = {}

    for item in candidates:
        key = item["figure_key"]
        old = best.get(key)

        if (
            old is None
            or item["score"] > old["score"]
        ):
            best[key] = item

    output = list(best.values())

    output.sort(
        key=lambda x: int(x["number"])
    )

    return output


def _caption_column(
    page,
    caption_rect,
):
    page_width = float(page.rect.width)

    ratio = (
        caption_rect.width
        / max(1.0, page_width)
    )

    # Full-width caption / Figure.
    if ratio >= 0.68:
        return (
            12.0,
            page_width - 12.0,
        )

    # Column-local Figure.
    padding = max(
        8.0,
        caption_rect.width * 0.04,
    )

    return (
        max(
            12.0,
            caption_rect.x0 - padding,
        ),
        min(
            page_width - 12.0,
            caption_rect.x1 + padding,
        ),
    )


def _find_crop_top(
    page,
    *,
    x0: float,
    x1: float,
    caption_y: float,
) -> float:
    """
    Find the last genuine prose block above the Figure in the same column.
    The Figure begins after that paragraph.

    Panel labels, axes, legends, short method labels, and other Figure text
    are intentionally not treated as prose.
    """
    target_column = (
        x0,
        0.0,
        x1,
        caption_y,
    )

    bottoms = []

    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue

        bbox = block.get("bbox")

        if (
            not bbox
            or len(bbox) != 4
        ):
            continue

        if float(bbox[3]) >= caption_y - 8:
            continue

        if (
            _horizontal_overlap_ratio(
                bbox,
                target_column,
            )
            < 0.50
        ):
            continue

        text = _block_text(block)

        if not _looks_like_prose(text):
            continue

        bottoms.append(float(bbox[3]))

    if not bottoms:
        return 12.0

    proposed = max(bottoms) + 6.0

    # Preserve enough height for a real scientific Figure.
    if caption_y - proposed < 70:
        return 12.0

    return proposed


def _render_figure(
    *,
    doc,
    item: Dict,
    cache_dir: Path,
) -> Optional[Path]:
    page = doc[item["page_idx"]]

    caption_rect = (
        fitz.Rect(item["bbox"])
        & page.rect
    )

    x0, x1 = _caption_column(
        page,
        caption_rect,
    )

    crop_bottom = (
        caption_rect.y0 - 5.0
    )

    crop_top = _find_crop_top(
        page,
        x0=x0,
        x1=x1,
        caption_y=crop_bottom,
    )

    rect = fitz.Rect(
        x0,
        crop_top,
        x1,
        crop_bottom,
    ) & page.rect

    if (
        rect.width < 60
        or rect.height < 70
    ):
        return None

    pix = page.get_pixmap(
        matrix=fitz.Matrix(
            2.6,
            2.6,
        ),
        clip=rect,
        alpha=False,
    )

    out = (
        cache_dir
        / (
            item["figure_key"]
            + "_source_pdf.png"
        )
    )

    pix.save(str(out))

    return out


def extract_figures_from_source_pdf(
    *,
    pdf_bytes: bytes,
    paper_hash: str,
    cache_root: str = "figure_cache/source_pdf_v1",
    force: bool = False,
) -> List[Dict]:
    """
    Deterministic Figure extraction from the original uploaded PDF.

    No AI/API call is used.
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

    if force and cache_dir.exists():
        shutil.rmtree(
            cache_dir,
            ignore_errors=True,
        )

    if (
        not force
        and meta_path.exists()
    ):
        try:
            payload = json.loads(
                meta_path.read_text(
                    encoding="utf-8"
                )
            )

            if (
                payload.get(
                    "extractor_version"
                )
                == EXTRACTOR_VERSION
                and payload.get(
                    "engine"
                )
                == "source_pdf_caption_v1"
            ):
                figures = payload.get(
                    "figures",
                    [],
                )

                if isinstance(
                    figures,
                    list,
                ):
                    return figures

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

    try:
        captions = (
            _find_caption_candidates(
                doc
            )
        )

        figures = []

        for item in captions:
            image_path = _render_figure(
                doc=doc,
                item=item,
                cache_dir=cache_dir,
            )

            if image_path is None:
                continue

            figures.append(
                {
                    "figure_label": item[
                        "figure_label"
                    ],
                    "figure_key": item[
                        "figure_key"
                    ],
                    "page_number": (
                        item["page_idx"]
                        + 1
                    ),
                    "caption": item[
                        "caption"
                    ],
                    "image_path": str(
                        image_path
                    ),
                    "bbox": item[
                        "bbox"
                    ],
                    "engine": (
                        "source_pdf_caption_v1"
                    ),
                    "asset_mode": (
                        "original_pdf_caption_anchor_direct"
                    ),
                    "extractor_version": (
                        EXTRACTOR_VERSION
                    ),
                }
            )

    finally:
        doc.close()

    meta_path.write_text(
        json.dumps(
            {
                "engine": (
                    "source_pdf_caption_v1"
                ),
                "extractor_version": (
                    EXTRACTOR_VERSION
                ),
                "figures": figures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return figures
