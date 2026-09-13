import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


EXTRACTOR_VERSION = "4"
ENGINE_NAME = "source_pdf_caption_v4"

CAPTION_START_RE = re.compile(
    r"^\s*(?:fig(?:ure)?\.?\s*)(\d+)\b",
    re.IGNORECASE,
)


SHORT_FIGURE_LABEL_RE = re.compile(
    r"^\s*(?:fig(?:ure)?\.?\s*)(\d+)\b",
    re.IGNORECASE,
)

TABLE_LABEL_RE = re.compile(
    r"^\s*table\s+\d+\b",
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
    """
    Distinguish real article prose from text embedded inside a Figure.

    Scientific Figures can contain many whitespace tokens because of axis
    values, lane labels, concentrations, and panel text. Real prose must
    contain a meaningful density of alphabetic words and punctuation.
    """
    text = (text or "").strip()

    if CAPTION_START_RE.match(text):
        return False

    words = text.split()

    if len(words) < 20:
        return False

    alpha_words = re.findall(
        r"\b[A-Za-z][A-Za-z-]{2,}\b",
        text,
    )

    if len(alpha_words) < 10:
        return False

    if (
        len(alpha_words)
        / max(1, len(words))
        < 0.35
    ):
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


def _intersection_area(a, b) -> float:
    ax0, ay0, ax1, ay1 = [float(v) for v in a]
    bx0, by0, bx1, by1 = [float(v) for v in b]

    x0 = max(ax0, bx0)
    y0 = max(ay0, by0)
    x1 = min(ax1, bx1)
    y1 = min(ay1, by1)

    if x1 <= x0 or y1 <= y0:
        return 0.0

    return (x1 - x0) * (y1 - y0)


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


def _scaled_caption_column(
    source_page,
    target_page,
    caption_rect,
):
    """
    Transfer the caption's horizontal column to an adjacent page.

    Most journal PDFs keep identical page sizes, but scaling makes this safe
    for mixed-size PDFs too.
    """
    source_width = max(
        1.0,
        float(source_page.rect.width),
    )
    target_width = float(
        target_page.rect.width
    )

    x0, x1 = _caption_column(
        source_page,
        caption_rect,
    )

    scale = (
        target_width
        / source_width
    )

    return (
        max(
            12.0,
            x0 * scale,
        ),
        min(
            target_width - 12.0,
            x1 * scale,
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


def _find_previous_page_crop_top(
    page,
    *,
    x0: float,
    x1: float,
    crop_bottom: float,
) -> Optional[float]:
    """
    Cross-page case:
    Figure is on the previous PDF page and its caption starts on the next page.

    Here we do NOT have a caption boundary on the Figure page. We therefore
    look for the last genuine prose block in the same column and crop the
    remaining lower page region. If the remaining space is too small, this
    candidate is rejected rather than falling back to a whole-page crop.
    """
    target_column = (
        x0,
        0.0,
        x1,
        crop_bottom,
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

        if (
            _horizontal_overlap_ratio(
                bbox,
                target_column,
            )
            < 0.45
        ):
            continue

        text = _block_text(block)

        if not _looks_like_prose(text):
            continue

        bottoms.append(
            float(bbox[3])
        )

    if not bottoms:
        return 12.0

    proposed = max(bottoms) + 8.0

    # A useful cross-page Figure region should have substantial height.
    if crop_bottom - proposed < 90:
        return None

    return proposed


def _visual_evidence(
    page,
    rect,
) -> Dict[str, float]:
    """
    Score how Figure-like a candidate crop is.

    Raster images strongly support a Figure. Vector drawings are also useful
    because many journal plots are vector PDF objects. Long prose blocks count
    against the candidate; short labels / axes count mildly in favor.
    """
    rect_tuple = (
        float(rect.x0),
        float(rect.y0),
        float(rect.x1),
        float(rect.y1),
    )

    rect_area = max(
        1.0,
        float(rect.width * rect.height),
    )

    raster_count = 0
    raster_area = 0.0
    prose_count = 0
    prose_chars = 0
    short_label_count = 0

    try:
        page_dict = page.get_text("dict")

        for block in page_dict.get("blocks", []):
            bbox = block.get("bbox")

            if (
                not bbox
                or len(bbox) != 4
            ):
                continue

            overlap_area = _intersection_area(
                bbox,
                rect_tuple,
            )

            if overlap_area <= 0:
                continue

            if block.get("type") == 1:
                raster_count += 1
                raster_area += overlap_area
                continue

            if block.get("type") != 0:
                continue

            text = _block_text(block)

            if not text:
                continue

            if _looks_like_prose(text):
                prose_count += 1
                prose_chars += len(text)
            elif len(text) <= 160:
                short_label_count += 1

    except Exception:
        pass

    drawing_count = 0

    try:
        for drawing in page.get_drawings():
            drect = drawing.get("rect")

            if drect is None:
                continue

            if (
                fitz.Rect(drect)
                & rect
            ).get_area() > 0:
                drawing_count += 1

    except Exception:
        pass

    raster_fraction = min(
        1.0,
        raster_area / rect_area,
    )

    height_fraction = min(
        1.0,
        float(rect.height)
        / max(
            1.0,
            float(page.rect.height),
        ),
    )

    score = 0.0
    score += raster_fraction * 8.0
    score += min(
        3.5,
        raster_count * 0.75,
    )
    score += min(
        4.0,
        drawing_count * 0.12,
    )
    score += min(
        2.0,
        short_label_count * 0.12,
    )
    score += min(
        1.2,
        height_fraction * 1.6,
    )

    score -= min(
        4.5,
        prose_count * 1.15,
    )
    score -= min(
        2.0,
        prose_chars / 900.0,
    )

    return {
        "score": round(
            score,
            4,
        ),
        "raster_count": float(
            raster_count
        ),
        "raster_fraction": round(
            raster_fraction,
            4,
        ),
        "drawing_count": float(
            drawing_count
        ),
        "prose_count": float(
            prose_count
        ),
        "short_label_count": float(
            short_label_count
        ),
        "height_fraction": round(
            height_fraction,
            4,
        ),
    }


def _same_page_candidate(
    *,
    page,
    caption_rect,
) -> Optional[Dict]:
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

    evidence = _visual_evidence(
        page,
        rect,
    )

    return {
        "page_idx": page.number,
        "rect": rect,
        "evidence": evidence,
        "mode": "same_page",
    }


def _previous_page_candidate(
    *,
    source_page,
    previous_page,
    caption_rect,
) -> Optional[Dict]:
    x0, x1 = _scaled_caption_column(
        source_page,
        previous_page,
        caption_rect,
    )

    crop_bottom = (
        float(previous_page.rect.height)
        - 12.0
    )

    crop_top = _find_previous_page_crop_top(
        previous_page,
        x0=x0,
        x1=x1,
        crop_bottom=crop_bottom,
    )

    if crop_top is None:
        return None

    rect = fitz.Rect(
        x0,
        crop_top,
        x1,
        crop_bottom,
    ) & previous_page.rect

    if (
        rect.width < 60
        or rect.height < 90
    ):
        return None

    evidence = _visual_evidence(
        previous_page,
        rect,
    )

    return {
        "page_idx": previous_page.number,
        "rect": rect,
        "evidence": evidence,
        "mode": "previous_page",
    }


def _select_candidate(
    *,
    caption_page,
    caption_rect,
    same_candidate,
    previous_candidate,
) -> Optional[Dict]:
    """
    Keep the old same-page behavior unless there is real evidence for the
    cross-page layout.

    Strongest clue:
    a caption beginning near the top of the page. In journals this frequently
    means the Figure itself ended on the previous page.
    """
    if (
        same_candidate is None
        and previous_candidate is None
    ):
        return None

    if same_candidate is None:
        return previous_candidate

    if previous_candidate is None:
        return same_candidate

    same_score = float(
        same_candidate["evidence"]["score"]
    )
    previous_score = float(
        previous_candidate["evidence"]["score"]
    )

    caption_top_ratio = (
        float(caption_rect.y0)
        / max(
            1.0,
            float(caption_page.rect.height),
        )
    )

    # Very top-of-page caption + decent previous-page visual evidence.
    if (
        caption_top_ratio <= 0.22
        and previous_score >= 0.75
        and previous_score >= same_score - 0.75
    ):
        return previous_candidate

    # Caption still high on page and previous candidate is clearly stronger.
    if (
        caption_top_ratio <= 0.36
        and previous_score >= same_score + 0.60
    ):
        return previous_candidate

    # Same-page region has little Figure evidence but previous page is strong.
    if (
        same_score < 0.80
        and previous_score >= 1.75
    ):
        return previous_candidate

    return same_candidate



def _short_figure_label_on_page(
    page,
) -> Optional[int]:
    """
    Find a short text label such as "Figure 3" on a visual page.

    Long blocks are deliberately ignored because those are usually legends,
    not labels attached to the Figure itself.
    """
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue

        text = _block_text(block).strip()

        if (
            not text
            or len(text) > 90
            or len(text.split()) > 16
        ):
            continue

        match = SHORT_FIGURE_LABEL_RE.match(text)

        if match:
            return int(match.group(1))

    return None


def _page_has_table_label(
    page,
) -> bool:
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue

        text = _block_text(block).strip()

        if (
            text
            and len(text) <= 100
            and TABLE_LABEL_RE.match(text)
        ):
            return True

    return False


def _page_visual_bounds(
    page,
):
    """
    Build a tight-ish bounding box around raster images and vector graphics.

    This is used only for detached Figure pages near the end of a manuscript.
    """
    visual_rects = []

    try:
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 1:
                continue

            bbox = block.get("bbox")

            if (
                bbox
                and len(bbox) == 4
            ):
                rect = fitz.Rect(bbox)

                if rect.get_area() >= 900:
                    visual_rects.append(rect)
    except Exception:
        pass

    try:
        for drawing in page.get_drawings():
            drect = drawing.get("rect")

            if drect is None:
                continue

            rect = fitz.Rect(drect)

            # Ignore tiny ticks / glyph-like drawing fragments.
            if rect.get_area() >= 80:
                visual_rects.append(rect)
    except Exception:
        pass

    if not visual_rects:
        return None

    union = fitz.Rect(visual_rects[0])

    for rect in visual_rects[1:]:
        union.include_rect(rect)

    # Expand to include nearby panel labels / axis text.
    expanded = fitz.Rect(
        union.x0 - 18,
        union.y0 - 24,
        union.x1 + 18,
        union.y1 + 24,
    ) & page.rect

    try:
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue

            bbox = block.get("bbox")

            if (
                not bbox
                or len(bbox) != 4
            ):
                continue

            text = _block_text(block).strip()

            if (
                not text
                or _looks_like_prose(text)
                or len(text) > 180
            ):
                continue

            block_rect = fitz.Rect(bbox)

            nearby = fitz.Rect(
                expanded.x0 - 10,
                expanded.y0 - 35,
                expanded.x1 + 10,
                expanded.y1 + 35,
            ) & page.rect

            if (
                block_rect
                & nearby
            ).get_area() > 0:
                union.include_rect(block_rect)
    except Exception:
        pass

    union = fitz.Rect(
        union.x0 - 14,
        union.y0 - 14,
        union.x1 + 14,
        union.y1 + 14,
    ) & page.rect

    if (
        union.width < 80
        or union.height < 80
    ):
        return None

    return union


def _scan_detached_endmatter_pages(
    doc,
    captions: List[Dict],
) -> List[Dict]:
    """
    Scan pages AFTER the final text caption for appended Figure pages.

    This specifically targets preprint/manuscript layouts where all legends
    are in the manuscript body and the actual Figures are appended at the end.
    """
    if not captions:
        return []

    last_caption_page = max(
        int(item["page_idx"])
        for item in captions
    )

    if last_caption_page >= len(doc) - 1:
        return []

    candidates = []

    for page_idx in range(
        last_caption_page + 1,
        len(doc),
    ):
        page = doc[page_idx]

        explicit_number = (
            _short_figure_label_on_page(
                page
            )
        )

        # A clearly labelled Table page should not be silently consumed
        # by the sequential Figure fallback.
        if (
            explicit_number is None
            and _page_has_table_label(page)
        ):
            continue

        rect = _page_visual_bounds(
            page
        )

        if rect is None:
            continue

        evidence = _visual_evidence(
            page,
            rect,
        )

        page_area = max(
            1.0,
            float(
                page.rect.width
                * page.rect.height
            ),
        )

        area_fraction = (
            float(
                rect.width
                * rect.height
            )
            / page_area
        )

        has_real_visual = (
            evidence.get(
                "raster_count",
                0,
            )
            >= 1
            or (
                evidence.get(
                    "drawing_count",
                    0,
                )
                >= 1
                and area_fraction >= 0.16
            )
        )

        if not has_real_visual:
            continue

        # Explicit Figure labels are strong evidence.
        if explicit_number is not None:
            min_score = 0.20
        else:
            min_score = 0.95

        if (
            float(
                evidence.get(
                    "score",
                    0.0,
                )
            )
            < min_score
            or area_fraction < 0.10
        ):
            continue

        candidates.append(
            {
                "page_idx": page_idx,
                "rect": rect,
                "evidence": evidence,
                "mode": "detached_endmatter",
                "explicit_number": explicit_number,
                "area_fraction": round(
                    area_fraction,
                    4,
                ),
            }
        )

    return candidates


def _build_detached_figure_map(
    doc,
    captions: List[Dict],
) -> Dict[str, Dict]:
    """
    Match appended endmatter Figure pages to text captions.

    Matching order:
    1) explicit short "Figure N" label on the visual page
    2) exact-count sequential fallback

    The sequential fallback is intentionally conservative. It is only used
    when the number of remaining visual pages exactly matches the number of
    remaining Figure captions.
    """
    candidates = _scan_detached_endmatter_pages(
        doc,
        captions,
    )

    if not candidates:
        return {}

    caption_by_number = {
        int(item["number"]): item
        for item in captions
    }

    result = {}
    used_pages = set()

    # Strong mapping: explicit Figure N text on the appended visual page.
    for candidate in candidates:
        number = candidate.get(
            "explicit_number"
        )

        if (
            number is None
            or number not in caption_by_number
        ):
            continue

        key = _figure_key(
            str(number)
        )

        old = result.get(
            key
        )

        if (
            old is None
            or float(
                candidate["evidence"]["score"]
            )
            > float(
                old["evidence"]["score"]
            )
        ):
            mapped = dict(candidate)
            mapped[
                "match_confidence"
            ] = "explicit_label"
            result[key] = mapped
            used_pages.add(
                candidate["page_idx"]
            )

    unresolved = [
        item
        for item in captions
        if item["figure_key"] not in result
    ]

    unused_candidates = [
        item
        for item in candidates
        if (
            item["page_idx"]
            not in used_pages
            and item.get(
                "explicit_number"
            )
            is None
        )
    ]

    unresolved.sort(
        key=lambda x: int(
            x["number"]
        )
    )
    unused_candidates.sort(
        key=lambda x: int(
            x["page_idx"]
        )
    )

    # Conservative bioRxiv/preprint fallback:
    # if appended visual pages and unresolved captions have an exact 1:1
    # count, map them in manuscript order.
    if (
        unresolved
        and len(unresolved)
        == len(unused_candidates)
    ):
        for caption, candidate in zip(
            unresolved,
            unused_candidates,
        ):
            mapped = dict(candidate)
            mapped[
                "match_confidence"
            ] = "sequential_exact"
            result[
                caption["figure_key"]
            ] = mapped

    return result


def _choose_local_or_detached(
    *,
    local_candidate,
    detached_candidate,
    caption_page_idx: int,
):
    if detached_candidate is None:
        return local_candidate

    if local_candidate is None:
        return detached_candidate

    detached_page_idx = int(
        detached_candidate[
            "page_idx"
        ]
    )

    if detached_page_idx <= caption_page_idx:
        return local_candidate

    local_score = float(
        local_candidate.get(
            "evidence",
            {},
        ).get(
            "score",
            0.0,
        )
    )

    detached_score = float(
        detached_candidate.get(
            "evidence",
            {},
        ).get(
            "score",
            0.0,
        )
    )

    confidence = detached_candidate.get(
        "match_confidence",
        "",
    )

    # An explicit Figure number on the appended page is the strongest signal.
    if (
        confidence == "explicit_label"
        and detached_score >= 0.20
    ):
        return detached_candidate

    # Exact-count sequential mapping is only available when the entire
    # appended Figure run lines up 1:1 with unresolved captions.
    if (
        confidence == "sequential_exact"
        and detached_score >= 0.95
        and (
            local_score < 2.40
            or detached_score
            >= local_score - 0.35
        )
    ):
        return detached_candidate

    return local_candidate



def _render_candidate(
    *,
    doc,
    item: Dict,
    cache_dir: Path,
    detached_candidate: Optional[Dict] = None,
) -> Optional[Dict]:
    caption_page = doc[
        item["page_idx"]
    ]

    caption_rect = (
        fitz.Rect(item["bbox"])
        & caption_page.rect
    )

    same_candidate = _same_page_candidate(
        page=caption_page,
        caption_rect=caption_rect,
    )

    previous_candidate = None

    if item["page_idx"] > 0:
        previous_page = doc[
            item["page_idx"] - 1
        ]

        previous_candidate = (
            _previous_page_candidate(
                source_page=caption_page,
                previous_page=previous_page,
                caption_rect=caption_rect,
            )
        )

    local_selected = _select_candidate(
        caption_page=caption_page,
        caption_rect=caption_rect,
        same_candidate=same_candidate,
        previous_candidate=previous_candidate,
    )

    selected = _choose_local_or_detached(
        local_candidate=local_selected,
        detached_candidate=detached_candidate,
        caption_page_idx=int(
            item["page_idx"]
        ),
    )

    if selected is None:
        return None

    figure_page = doc[
        selected["page_idx"]
    ]

    rect = selected["rect"]

    pix = figure_page.get_pixmap(
        matrix=fitz.Matrix(
            2.6,
            2.6,
        ),
        clip=rect,
        alpha=False,
    )

    mode = selected.get(
        "mode",
        "same_page",
    )

    suffix_map = {
        "previous_page": "_cross_page",
        "detached_endmatter": "_endmatter",
        "same_page": "_same_page",
    }

    suffix = suffix_map.get(
        mode,
        "_figure",
    )

    out = (
        cache_dir
        / (
            item["figure_key"]
            + suffix
            + "_source_pdf_v4.png"
        )
    )

    pix.save(
        str(out)
    )

    return {
        "image_path": out,
        "figure_page_idx": selected[
            "page_idx"
        ],
        "caption_page_idx": item[
            "page_idx"
        ],
        "crop_rect": [
            round(
                float(v),
                2,
            )
            for v in [
                rect.x0,
                rect.y0,
                rect.x1,
                rect.y1,
            ]
        ],
        "selection_mode": mode,
        "selection_score": selected[
            "evidence"
        ],
        "match_confidence": selected.get(
            "match_confidence",
            "local",
        ),
    }


def extract_figures_from_source_pdf(
    *,
    pdf_bytes: bytes,
    paper_hash: str,
    cache_root: str = "figure_cache/source_pdf_v4",
    force: bool = False,
) -> List[Dict]:
    """
    Deterministic Figure extraction from the original uploaded PDF.

    v4 supports three common manuscript layouts:
    - normal: Figure and legend/caption on the same PDF page
    - cross-page: Figure on the previous page, caption on the next page
    - detached endmatter: legends in the manuscript body, Figures appended
      together near the end of the PDF (common in preprints/manuscripts)

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
                == ENGINE_NAME
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

        detached_map = (
            _build_detached_figure_map(
                doc,
                captions,
            )
        )

        for item in captions:
            rendered = _render_candidate(
                doc=doc,
                item=item,
                cache_dir=cache_dir,
                detached_candidate=(
                    detached_map.get(
                        item["figure_key"]
                    )
                ),
            )

            if rendered is None:
                continue

            figure_page_number = (
                rendered[
                    "figure_page_idx"
                ]
                + 1
            )

            caption_page_number = (
                rendered[
                    "caption_page_idx"
                ]
                + 1
            )

            figures.append(
                {
                    "figure_label": item[
                        "figure_label"
                    ],
                    "figure_key": item[
                        "figure_key"
                    ],
                    # Keep page_number as the actual visible Figure page.
                    "page_number": (
                        figure_page_number
                    ),
                    "figure_page_number": (
                        figure_page_number
                    ),
                    "caption_page_number": (
                        caption_page_number
                    ),
                    "caption": item[
                        "caption"
                    ],
                    "image_path": str(
                        rendered[
                            "image_path"
                        ]
                    ),
                    "bbox": item[
                        "bbox"
                    ],
                    "crop_rect": rendered[
                        "crop_rect"
                    ],
                    "engine": ENGINE_NAME,
                    "asset_mode": (
                        "original_pdf_detached_endmatter"
                        if rendered[
                            "selection_mode"
                        ]
                        == "detached_endmatter"
                        else (
                            "original_pdf_caption_anchor_cross_page"
                            if rendered[
                                "selection_mode"
                            ]
                            == "previous_page"
                            else
                            "original_pdf_caption_anchor_direct"
                        )
                    ),
                    "cross_page": (
                        rendered[
                            "figure_page_idx"
                        ]
                        != rendered[
                            "caption_page_idx"
                        ]
                    ),
                    "detached_endmatter": (
                        rendered[
                            "selection_mode"
                        ]
                        == "detached_endmatter"
                    ),
                    "match_confidence": rendered.get(
                        "match_confidence",
                        "local",
                    ),
                    "selection_mode": rendered[
                        "selection_mode"
                    ],
                    "selection_score": rendered[
                        "selection_score"
                    ],
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
                "engine": ENGINE_NAME,
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
