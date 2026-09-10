import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from mineru import MinerU
except Exception:
    MinerU = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


MINERU_EXTRACTOR_VERSION = "4"

CAPTION_RE = re.compile(
    r"^\s*(?:fig(?:ure)?\.?\s*)(\d+[A-Za-z]?)\s*[.:]?\s*",
    re.IGNORECASE,
)


def mineru_available() -> bool:
    return MinerU is not None


def normalize_figure_label(text: str) -> str:
    text = (text or "").strip()

    m = CAPTION_RE.match(text)

    if not m:
        m = re.search(
            r"(?i)\bfig(?:ure)?\.?\s*(\d+[A-Za-z]?)\b",
            text,
        )

    if not m:
        return ""

    return f"Fig. {m.group(1)}"


def figure_key(label: str) -> str:
    m = re.search(
        r"(?i)(\d+)([A-Za-z]?)",
        label or "",
    )

    if not m:
        return re.sub(
            r"\W+",
            "",
            (label or "").lower(),
        )

    return (
        f"fig{m.group(1)}"
        f"{m.group(2).lower()}"
    )


def _text_from_lines(block: Dict) -> str:
    out = []

    for line in block.get("lines", []):
        for span in line.get("spans", []):
            value = (
                span.get("content")
                or span.get("text")
                or ""
            )

            if value:
                out.append(str(value))

    return " ".join(out).strip()


def _find_middle_json(output_dir: Path) -> Optional[Path]:
    """
    MinerU names this artifact differently depending on the API/client path.

    Official online API packages may expose `layout.json`, which corresponds
    to the intermediate `middle.json` structure. Local/client-side generation
    may instead produce `<stem>_middle.json` or `middle.json`.
    """

    preferred_patterns = [
        "*_middle.json",
        "middle.json",
        "layout.json",
        "*layout.json",
    ]

    seen = set()
    candidates = []

    for pattern in preferred_patterns:
        for path in output_dir.rglob(pattern):
            resolved = str(path.resolve())

            if resolved in seen:
                continue

            seen.add(resolved)

            # Avoid accidentally selecting unrelated tiny metadata JSON files.
            if path.is_file():
                candidates.append(path)

    if not candidates:
        return None

    def score(path: Path):
        name = path.name.lower()

        if name.endswith("_middle.json"):
            rank = 4
        elif name == "middle.json":
            rank = 3
        elif name == "layout.json":
            rank = 2
        elif name.endswith("layout.json"):
            rank = 1
        else:
            rank = 0

        try:
            size = path.stat().st_size
        except Exception:
            size = 0

        return (rank, size)

    candidates.sort(
        key=score,
        reverse=True,
    )

    return candidates[0]


def _union_bbox(boxes: List[List[float]]) -> Optional[List[float]]:
    valid = []

    for box in boxes:
        if (
            isinstance(box, (list, tuple))
            and len(box) == 4
        ):
            try:
                valid.append(
                    [float(v) for v in box]
                )
            except Exception:
                pass

    if not valid:
        return None

    return [
        min(b[0] for b in valid),
        min(b[1] for b in valid),
        max(b[2] for b in valid),
        max(b[3] for b in valid),
    ]


def _bbox_to_pdf_rect(
    *,
    bbox,
    page_size,
    pdf_page,
    backend: str,
):
    if (
        not isinstance(bbox, (list, tuple))
        or len(bbox) != 4
    ):
        return None

    try:
        x0, y0, x1, y1 = [
            float(v)
            for v in bbox
        ]
    except Exception:
        return None

    values = [
        x0, y0, x1, y1
    ]

    pdf_w = float(pdf_page.rect.width)
    pdf_h = float(pdf_page.rect.height)

    # VLM middle.json can use normalized coordinates.
    if all(
        -0.05 <= v <= 1.05
        for v in values
    ):
        return fitz.Rect(
            x0 * pdf_w,
            y0 * pdf_h,
            x1 * pdf_w,
            y1 * pdf_h,
        )

    # Pipeline/office middle.json normally uses coordinates in page_size units.
    if (
        isinstance(page_size, (list, tuple))
        and len(page_size) == 2
    ):
        try:
            src_w = float(page_size[0])
            src_h = float(page_size[1])

            # If bbox is plausibly in page_size coordinate system.
            if (
                src_w > 0
                and src_h > 0
                and max(x0, x1) <= src_w * 1.25
                and max(y0, y1) <= src_h * 1.25
            ):
                return fitz.Rect(
                    x0 / src_w * pdf_w,
                    y0 / src_h * pdf_h,
                    x1 / src_w * pdf_w,
                    y1 / src_h * pdf_h,
                )
        except Exception:
            pass

    # Final fallback: final-output-like 0..1000 coordinates.
    if all(
        -20 <= v <= 1020
        for v in values
    ):
        return fitz.Rect(
            x0 / 1000.0 * pdf_w,
            y0 / 1000.0 * pdf_h,
            x1 / 1000.0 * pdf_w,
            y1 / 1000.0 * pdf_h,
        )

    return None


def _render_middle_bbox(
    *,
    pdf_bytes: bytes,
    page_idx: int,
    bbox,
    page_size,
    backend: str,
    cache_dir: Path,
    key: str,
    zoom: float = 2.5,
) -> Optional[Path]:
    if fitz is None:
        return None

    doc = None

    try:
        doc = fitz.open(
            stream=pdf_bytes,
            filetype="pdf",
        )

        if (
            page_idx < 0
            or page_idx >= len(doc)
        ):
            return None

        page = doc[page_idx]

        rect = _bbox_to_pdf_rect(
            bbox=bbox,
            page_size=page_size,
            pdf_page=page,
            backend=backend,
        )

        if rect is None:
            return None

        # Tiny padding to avoid clipping panel labels/axes.
        pad_x = max(
            2.0,
            rect.width * 0.015,
        )
        pad_y = max(
            2.0,
            rect.height * 0.02,
        )

        rect = fitz.Rect(
            rect.x0 - pad_x,
            rect.y0 - pad_y,
            rect.x1 + pad_x,
            rect.y1 + pad_y,
        ) & page.rect

        if (
            rect.width < 45
            or rect.height < 45
        ):
            return None

        pix = page.get_pixmap(
            matrix=fitz.Matrix(
                zoom,
                zoom,
            ),
            clip=rect,
            alpha=False,
        )

        target = (
            cache_dir
            / f"{key}_middle.png"
        )

        pix.save(
            str(target)
        )

        return target

    except Exception:
        return None

    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


def _extract_from_middle_json(
    *,
    middle_json: Dict,
    pdf_bytes: bytes,
    cache_dir: Path,
) -> List[Dict]:
    backend = str(
        middle_json.get(
            "_backend",
            "",
        )
    ).lower()

    # MinerU online API may serialize the middle structure as layout.json
    # without the private `_backend` marker.
    if not backend:
        backend = "vlm"

    pdf_info = middle_json.get(
        "pdf_info",
        [],
    )

    best_by_key = {}

    for page in pdf_info:
        if not isinstance(
            page,
            dict,
        ):
            continue

        page_idx = int(
            page.get(
                "page_idx",
                0,
            )
        )

        page_size = page.get(
            "page_size"
        )

        for para in page.get(
            "para_blocks",
            [],
        ):
            if not isinstance(
                para,
                dict,
            ):
                continue

            para_type = str(
                para.get(
                    "type",
                    "",
                )
            ).lower()

            if para_type not in {
                "image",
                "chart",
            }:
                continue

            blocks = para.get(
                "blocks",
                [],
            )

            captions = []
            body_boxes = []

            for block in blocks:
                if not isinstance(
                    block,
                    dict,
                ):
                    continue

                block_type = str(
                    block.get(
                        "type",
                        "",
                    )
                ).lower()

                if block_type in {
                    "image_caption",
                    "chart_caption",
                }:
                    text = _text_from_lines(
                        block
                    )

                    if text:
                        captions.append(
                            text
                        )

                elif block_type in {
                    "image_body",
                    "chart_body",
                }:
                    if block.get(
                        "bbox"
                    ):
                        body_boxes.append(
                            block[
                                "bbox"
                            ]
                        )

                    # Some multi-panel figures expose the useful geometry
                    # only at line/span level. Union all of them.
                    for line in block.get(
                        "lines",
                        [],
                    ):
                        if line.get(
                            "bbox"
                        ):
                            body_boxes.append(
                                line[
                                    "bbox"
                                ]
                            )

                        for span in line.get(
                            "spans",
                            [],
                        ):
                            if span.get(
                                "bbox"
                            ):
                                body_boxes.append(
                                    span[
                                        "bbox"
                                    ]
                                )

            caption = " ".join(
                x
                for x in captions
                if x
            ).strip()

            # Figure captions only; references/body prose do not pass.
            if not CAPTION_RE.match(
                caption
            ):
                continue

            label = normalize_figure_label(
                caption
            )

            if not label:
                continue

            key = figure_key(
                label
            )

            # Most important change:
            # use ALL image_body / line / span bboxes under the same
            # level-1 MinerU Figure container.
            body_bbox = _union_bbox(
                body_boxes
            )

            # If body geometry is missing, use the level-1 image container bbox.
            if body_bbox is None:
                body_bbox = para.get(
                    "bbox"
                )

            if body_bbox is None:
                continue

            rendered = _render_middle_bbox(
                pdf_bytes=pdf_bytes,
                page_idx=page_idx,
                bbox=body_bbox,
                page_size=page_size,
                backend=backend,
                cache_dir=cache_dir,
                key=key,
            )

            if rendered is None:
                continue

            candidate = {
                "figure_label": label,
                "figure_key": key,
                "page_number": (
                    page_idx + 1
                ),
                "caption": caption,
                "image_path": str(
                    rendered
                ),
                "bbox": body_bbox,
                "engine": (
                    "mineru_middle_json"
                ),
                "asset_mode": (
                    "union_all_image_body_bboxes"
                ),
                "backend": backend,
                "extractor_version": (
                    MINERU_EXTRACTOR_VERSION
                ),
            }

            old = best_by_key.get(
                key
            )

            if (
                old is None
                or len(
                    candidate[
                        "caption"
                    ]
                )
                > len(
                    old[
                        "caption"
                    ]
                )
            ):
                best_by_key[
                    key
                ] = candidate

    figures = list(
        best_by_key.values()
    )

    def sort_key(item):
        m = re.search(
            r"(\d+)",
            item.get(
                "figure_label",
                "",
            ),
        )

        return (
            int(m.group(1))
            if m
            else 9999
        )

    figures.sort(
        key=sort_key
    )

    return figures


def extract_figures_with_mineru(
    *,
    pdf_bytes: bytes,
    paper_hash: str,
    token: str,
    cache_root: str = "figure_cache/mineru_middle_v3",
    language: str = "en",
    force: bool = False,
) -> List[Dict]:
    if not mineru_available():
        raise RuntimeError(
            "mineru-open-sdk is not installed."
        )

    if fitz is None:
        raise RuntimeError(
            "PyMuPDF is not installed."
        )

    if not token:
        raise ValueError(
            "MINERU_TOKEN is not configured."
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
                == MINERU_EXTRACTOR_VERSION
                and payload.get(
                    "engine"
                )
                == "mineru_middle_json"
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

    with tempfile.TemporaryDirectory(
        prefix="lalstudy_mineru_"
    ) as tmp:
        tmp_dir = Path(tmp)

        pdf_path = (
            tmp_dir
            / "paper.pdf"
        )

        output_dir = (
            tmp_dir
            / "mineru_output"
        )

        pdf_path.write_bytes(
            pdf_bytes
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        with MinerU(token) as client:
            client.set_source(
                "LALSTUDY"
            )

            result = client.extract(
                str(pdf_path),
                model="vlm",
                language=language,
                timeout=600,
            )

            result.save_all(
                str(output_dir)
            )

        middle_path = (
            _find_middle_json(
                output_dir
            )
        )

        if middle_path is None:
            json_files = sorted(
                str(path.relative_to(output_dir))
                for path in output_dir.rglob("*.json")
            )

            preview = ", ".join(
                json_files[:25]
            )

            if len(json_files) > 25:
                preview += ", ..."

            raise RuntimeError(
                "MinerU completed, but no middle/layout JSON artifact was found. "
                f"JSON files present: {preview or 'none'}"
            )

        middle_json = json.loads(
            middle_path.read_text(
                encoding="utf-8"
            )
        )

        figures = (
            _extract_from_middle_json(
                middle_json=middle_json,
                pdf_bytes=pdf_bytes,
                cache_dir=cache_dir,
            )
        )

        if not figures:
            raise RuntimeError(
                "MinerU middle.json was found, but no complete main Figure containers were extracted."
            )

    meta_path.write_text(
        json.dumps(
            {
                "engine": (
                    "mineru_middle_json"
                ),
                "extractor_version": (
                    MINERU_EXTRACTOR_VERSION
                ),
                "figures": figures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return figures
