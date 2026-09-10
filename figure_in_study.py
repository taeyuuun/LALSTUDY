import json
import re
from pathlib import Path
from typing import List, Dict, Optional

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


FIG_LABEL_RE = re.compile(r"(?i)\b(fig(?:ure)?\.?\s*[0-9]+[A-Za-z]?)\b")


def pymupdf_available() -> bool:
    return fitz is not None


def normalize_figure_label(label: str) -> str:
    label = (label or "").strip()
    if not label:
        return ""

    label = re.sub(r"(?i)^figure", "Fig.", label)
    label = re.sub(r"\s+", " ", label)
    label = label.replace("Fig ", "Fig. ")
    label = label.replace("FIG ", "Fig. ")
    label = label.replace("FIGURE ", "Fig. ")
    return label.strip()


def label_key(label: str) -> str:
    norm = normalize_figure_label(label).lower()
    norm = norm.replace("figure", "fig")
    norm = norm.replace("fig.", "fig")
    norm = norm.replace(" ", "")
    return norm


def _caption_text(block: dict) -> str:
    lines = block.get("lines", [])
    out = []
    for line in lines:
        for span in line.get("spans", []):
            out.append(span.get("text", ""))
    return " ".join(out).strip()


def _find_caption_blocks(page) -> List[dict]:
    data = page.get_text("dict")
    blocks = []

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue

        text = _caption_text(block)
        if not text:
            continue

        if FIG_LABEL_RE.search(text):
            x0, y0, x1, y1 = block.get("bbox", (0, 0, 0, 0))
            label_match = FIG_LABEL_RE.search(text)
            label = normalize_figure_label(label_match.group(1)) if label_match else "Figure"
            blocks.append(
                {
                    "bbox": (x0, y0, x1, y1),
                    "text": text,
                    "label": label,
                }
            )

    blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
    return blocks


def _safe_crop(page, rect, zoom=2.0):
    rect = fitz.Rect(rect)
    rect = rect & page.rect

    if rect.width < 30 or rect.height < 30:
        return None

    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
    return pix.tobytes("png")


def extract_study_figures(
    pdf_bytes: bytes,
    paper_hash: str,
    cache_root: str = "figure_cache/study_figures",
) -> List[Dict]:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed.")

    cache_dir = Path(cache_root) / paper_hash
    meta_path = cache_dir / "figures.json"

    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    cache_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    items = []

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            caption_blocks = _find_caption_blocks(page)

            if not caption_blocks:
                continue

            prev_caption_bottom = 18.0
            page_margin = 18.0

            for local_idx, block in enumerate(caption_blocks):
                x0, y0, x1, y1 = block["bbox"]

                crop_top = prev_caption_bottom if local_idx > 0 else page_margin
                crop_bottom = max(crop_top + 40, y0 - 8)
                crop_rect = (
                    page_margin,
                    crop_top,
                    page.rect.width - page_margin,
                    crop_bottom,
                )

                png_bytes = _safe_crop(page, crop_rect, zoom=2.0)
                if png_bytes is None:
                    prev_caption_bottom = y1 + 8
                    continue

                label = block["label"]
                key = label_key(label)

                out_name = f"{page_index+1:03d}_{key}.png"
                out_path = cache_dir / out_name
                out_path.write_bytes(png_bytes)

                items.append(
                    {
                        "figure_label": label,
                        "figure_key": key,
                        "page_number": page_index + 1,
                        "caption": block["text"],
                        "image_path": str(out_path),
                    }
                )

                prev_caption_bottom = y1 + 8
    finally:
        doc.close()

    meta_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return items


def find_matching_figure(extracted_figures: List[Dict], figure_label: str) -> Optional[Dict]:
    target = label_key(figure_label)
    if not target:
        return None

    for item in extracted_figures:
        if item.get("figure_key") == target:
            return item

    for item in extracted_figures:
        key = item.get("figure_key", "")
        if target in key or key in target:
            return item

    return None
