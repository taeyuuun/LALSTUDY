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


MINERU_EXTRACTOR_VERSION = "2"

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


def _caption_to_text(value) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        out = []

        for item in value:
            if isinstance(item, str):
                out.append(item)

            elif isinstance(item, dict):
                content = item.get(
                    "content",
                    "",
                )

                if content:
                    out.append(
                        str(content)
                    )

                children = item.get(
                    "children"
                )

                if isinstance(
                    children,
                    list,
                ):
                    out.append(
                        _caption_to_text(
                            children
                        )
                    )

        return " ".join(
            x
            for x in out
            if x
        ).strip()

    if isinstance(value, dict):
        if "content" in value:
            return str(
                value.get(
                    "content",
                    "",
                )
            ).strip()

    return str(value).strip()


def _coerce_content_list(value):
    if value is None:
        return None

    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        for key in [
            "content_list",
            "data",
            "items",
        ]:
            candidate = value.get(
                key
            )

            if isinstance(
                candidate,
                list,
            ):
                return candidate

        return None

    if isinstance(value, str):
        try:
            parsed = json.loads(
                value
            )

            return _coerce_content_list(
                parsed
            )
        except Exception:
            return None

    return None


def _find_content_list(
    result,
    output_dir: Path,
):
    direct = _coerce_content_list(
        getattr(
            result,
            "content_list",
            None,
        )
    )

    if direct is not None:
        return direct

    candidates = list(
        output_dir.rglob(
            "*content_list.json"
        )
    )

    for path in candidates:
        try:
            parsed = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            parsed = _coerce_content_list(
                parsed
            )

            if parsed is not None:
                return parsed

        except Exception:
            pass

    return []


def _resolve_asset_path(
    output_dir: Path,
    img_path: str,
) -> Optional[Path]:
    if not img_path:
        return None

    raw = Path(
        str(img_path).replace(
            "\\",
            "/",
        )
    )

    direct_candidates = [
        output_dir / raw,
        output_dir / raw.name,
    ]

    for candidate in direct_candidates:
        if candidate.exists():
            return candidate

    matches = list(
        output_dir.rglob(
            raw.name
        )
    )

    return (
        matches[0]
        if matches
        else None
    )


def _entry_payload(entry: Dict) -> Tuple[str, str]:
    """
    Returns: (img_path, caption)
    Supports both legacy content_list and V2-like structures.
    """
    entry_type = str(
        entry.get(
            "type",
            "",
        )
    ).lower()

    if entry_type not in {
        "image",
        "chart",
    }:
        return "", ""

    # Legacy content_list.
    img_path = str(
        entry.get(
            "img_path",
            "",
        )
        or ""
    )

    caption = (
        entry.get(
            "image_caption"
        )
        or entry.get(
            "chart_caption"
        )
        or entry.get(
            "img_caption"
        )
        or []
    )

    # V2-like nested content.
    content = entry.get(
        "content"
    )

    if isinstance(
        content,
        dict,
    ):
        source = content.get(
            "image_source"
        )

        if (
            isinstance(
                source,
                dict,
            )
            and source.get(
                "path"
            )
        ):
            img_path = str(
                source.get(
                    "path"
                )
            )

        caption = (
            content.get(
                "image_caption"
            )
            or content.get(
                "chart_caption"
            )
            or caption
        )

    return (
        img_path,
        _caption_to_text(
            caption
        ),
    )


def _copy_asset(
    source: Path,
    cache_dir: Path,
    key: str,
) -> Path:
    suffix = (
        source.suffix.lower()
        if source.suffix
        else ".png"
    )

    if suffix not in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }:
        suffix = ".png"

    target = (
        cache_dir
        / f"{key}{suffix}"
    )

    if (
        not target.exists()
        or target.stat().st_size
        != source.stat().st_size
    ):
        shutil.copy2(
            source,
            target,
        )

    return target



def _render_bbox_from_pdf(
    *,
    pdf_bytes: bytes,
    page_idx: int,
    bbox,
    cache_dir: Path,
    key: str,
    zoom: float = 2.4,
) -> Optional[Path]:
    """
    Render the ORIGINAL PDF page using MinerU's content-block bbox.

    MinerU content_list bbox uses normalized 0..1000 coordinates.
    This avoids relying on img_path, which can represent only one image span
    from a multi-panel Figure.
    """
    if fitz is None:
        return None

    if (
        not isinstance(bbox, (list, tuple))
        or len(bbox) != 4
    ):
        return None

    try:
        doc = fitz.open(
            stream=pdf_bytes,
            filetype="pdf",
        )

        if (
            page_idx < 0
            or page_idx >= len(doc)
        ):
            doc.close()
            return None

        page = doc[page_idx]

        x0, y0, x1, y1 = [
            float(v)
            for v in bbox
        ]

        # content_list coordinates are normalized to 0-1000.
        rect = fitz.Rect(
            x0 / 1000.0 * page.rect.width,
            y0 / 1000.0 * page.rect.height,
            x1 / 1000.0 * page.rect.width,
            y1 / 1000.0 * page.rect.height,
        )

        rect = rect & page.rect

        if (
            rect.width < 40
            or rect.height < 40
        ):
            doc.close()
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
            / f"{key}_bbox.png"
        )

        pix.save(
            str(target)
        )

        doc.close()

        return target

    except Exception:
        try:
            doc.close()
        except Exception:
            pass

        return None


def extract_figures_with_mineru(
    *,
    pdf_bytes: bytes,
    paper_hash: str,
    token: str,
    cache_root: str = "figure_cache/mineru_precision",
    language: str = "en",
) -> List[Dict]:
    if not mineru_available():
        raise RuntimeError(
            "mineru-open-sdk is not installed."
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

    if meta_path.exists():
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
                == "mineru_precision_vlm"
            ):
                figures = payload.get(
                    "figures",
                    []
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

    # MinerU SDK accepts local file paths.
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

            # Save all rich assets locally so img_path can be resolved.
            result.save_all(
                str(output_dir)
            )

            content_list = (
                _find_content_list(
                    result,
                    output_dir,
                )
            )

        best_by_key = {}

        for entry in content_list:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            img_path, caption = (
                _entry_payload(
                    entry
                )
            )

            if not caption:
                continue

            # Main safeguard: only accept captions that themselves begin
            # with Fig./Figure. Body references are ignored.
            if not CAPTION_RE.match(
                caption
            ):
                continue

            label = (
                normalize_figure_label(
                    caption
                )
            )

            if not label:
                continue

            key = figure_key(
                label
            )

            page_idx = int(
                entry.get(
                    "page_idx",
                    0,
                )
            )

            block_bbox = entry.get(
                "bbox"
            )

            # PRIMARY:
            # Use MinerU to locate the WHOLE image content block,
            # then render that region from the original PDF.
            #
            # Do NOT trust content_list img_path as the primary Figure asset:
            # multi-panel figures may contain multiple image spans and the
            # simplified img_path can point to only one panel.
            rendered = _render_bbox_from_pdf(
                pdf_bytes=pdf_bytes,
                page_idx=page_idx,
                bbox=block_bbox,
                cache_dir=cache_dir,
                key=key,
            )

            extraction_asset_mode = (
                "mineru_bbox_pdf_render"
            )

            # FALLBACK:
            # If bbox rendering is impossible, keep the old MinerU asset path.
            if rendered is None:
                asset = _resolve_asset_path(
                    output_dir,
                    img_path,
                )

                if asset is None:
                    continue

                rendered = _copy_asset(
                    asset,
                    cache_dir,
                    key,
                )

                extraction_asset_mode = (
                    "mineru_img_path_fallback"
                )

            candidate = {
                "figure_label": label,
                "figure_key": key,
                "page_number": page_idx + 1,
                "caption": caption,
                "image_path": str(
                    rendered
                ),
                "bbox": block_bbox,
                "engine": (
                    "mineru_precision_vlm"
                ),
                "asset_mode": (
                    extraction_asset_mode
                ),
                "extractor_version": (
                    MINERU_EXTRACTOR_VERSION
                ),
            }

            old = best_by_key.get(
                key
            )

            # Prefer the richer caption if MinerU produced duplicate blocks.
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

    meta_path.write_text(
        json.dumps(
            {
                "engine": (
                    "mineru_precision_vlm"
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
