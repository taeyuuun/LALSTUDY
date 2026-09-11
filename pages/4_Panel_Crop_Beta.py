import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import streamlit as st
from i18n import language_selector, L
from knowledge_widget import render_knowledge_archive_widget
from ai_provider import render_openai_usage_panel

# ============================================================
# FILES
# ============================================================

DATA_FILE = Path("method_profiles.json")
IMAGE_INDEX_FILE = Path("figure_images.json")
CACHE_DIR = Path("figure_cache")

st.set_page_config(
    page_title="LALSTUDY · Panel Crop Beta",
    page_icon="✂️",
    layout="wide"
)

# ============================================================
# LOAD
# ============================================================

@st.cache_data
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

profiles = load_json(DATA_FILE)
image_index = load_json(IMAGE_INDEX_FILE) if IMAGE_INDEX_FILE.exists() else {}

profiles_by_name = {p["name"]: p for p in profiles}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif",
    ".tif", ".tiff", ".webp"
}

# ============================================================
# IMAGE MATCH
# ============================================================

def find_cached_image(pmcid, href):
    if not href:
        return None

    folder = CACHE_DIR / pmcid
    if not folder.exists():
        return None

    href_name = Path(href).name
    href_stem = Path(href_name).stem.lower()
    href_lower = href_name.lower()

    candidates = [
        p for p in folder.iterdir()
        if (
            p.is_file()
            and p.suffix.lower() in IMAGE_EXTENSIONS
            and not p.name.startswith("_")
        )
    ]

    for p in candidates:
        if p.name.lower() == href_lower:
            return p

    for p in candidates:
        if p.stem.lower() == href_stem:
            return p

    for p in candidates:
        stem = p.stem.lower()
        if href_stem in stem or stem in href_stem:
            return p

    return None

# ============================================================
# PANEL LABEL PARSING
# ============================================================

PANEL_LABEL_RE = r"[a-hA-H](?:\s*[–—-]\s*[a-hA-H])?(?:\s*,\s*[a-hA-H])*"

def normalize_panel_label(label):
    label = label.strip().replace("—", "–").replace("-", "–")
    label = re.sub(r"\s+", "", label)
    return label.upper()

def expand_label(label):
    """
    A-C -> A,B,C
    A,B,C -> A,B,C
    A -> A
    """
    label = normalize_panel_label(label)

    if "–" in label:
        left, right = label.split("–", 1)

        if (
            len(left) == 1
            and len(right) == 1
            and left.isalpha()
            and right.isalpha()
        ):
            return [
                chr(c)
                for c in range(
                    ord(left),
                    ord(right) + 1
                )
            ]

    if "," in label:
        return [
            x.strip()
            for x in label.split(",")
            if x.strip()
        ]

    return [label]

def split_caption_panels(caption):
    """
    Simpler robust caption splitter.
    """
    patterns = [
        re.compile(
            rf"\(({PANEL_LABEL_RE})\)",
            re.IGNORECASE
        ),
        re.compile(
            rf"(?:^|(?<=[.;]))\s*"
            rf"({PANEL_LABEL_RE})"
            rf"\s*[,:\.]\s+",
            re.IGNORECASE
        )
    ]

    markers = []

    for pattern in patterns:
        for m in pattern.finditer(caption):
            group = m.group(1)

            markers.append({
                "label": normalize_panel_label(group),
                "marker_start": m.start(1),
                "content_start": m.end()
            })

    # dedupe positions
    uniq = {}
    for m in markers:
        uniq[m["marker_start"]] = m

    markers = sorted(
        uniq.values(),
        key=lambda x: x["marker_start"]
    )

    if not markers:
        return []

    panels = []

    for i, marker in enumerate(markers):
        start = marker["content_start"]

        if i + 1 < len(markers):
            end = markers[i + 1]["marker_start"]
        else:
            end = len(caption)

        text = caption[start:end].strip(" .;:")

        expanded = expand_label(marker["label"])

        if len(expanded) == 1:
            panels.append({
                "label": expanded[0],
                "text": text
            })
        else:
            # grouped labels share the same caption segment
            for lab in expanded:
                panels.append({
                    "label": lab,
                    "text": text
                })

    # unique labels, preserve order
    seen = set()
    out = []

    for panel in panels:
        if panel["label"] not in seen:
            seen.add(panel["label"])
            out.append(panel)

    return out

# ============================================================
# WHITESPACE SEGMENTATION
# ============================================================

def trim_outer_white(img, white_threshold=248):
    """
    Remove huge white margins around entire figure.
    """
    rgb = np.array(
        img.convert("RGB")
    )

    gray = rgb.mean(axis=2)

    content = gray < white_threshold

    ys, xs = np.where(content)

    if len(xs) == 0 or len(ys) == 0:
        return img, (0, 0, img.width, img.height)

    x0 = max(0, xs.min() - 5)
    x1 = min(img.width, xs.max() + 6)

    y0 = max(0, ys.min() - 5)
    y1 = min(img.height, ys.max() + 6)

    return img.crop((x0, y0, x1, y1)), (x0, y0, x1, y1)

def smooth1d(arr, window=11):
    if len(arr) < window:
        return arr

    kernel = np.ones(window) / window

    return np.convolve(
        arr,
        kernel,
        mode="same"
    )

def find_gutters(
    img,
    axis,
    white_threshold=248,
    max_ink_fraction=0.012,
    min_width_fraction=0.01,
    edge_ignore_fraction=0.03
):
    """
    axis=0 => horizontal gutters (rows)
    axis=1 => vertical gutters (cols)
    """

    gray = np.array(
        img.convert("L")
    )

    ink = gray < white_threshold

    if axis == 1:
        frac = ink.mean(axis=0)
        length = img.width
    else:
        frac = ink.mean(axis=1)
        length = img.height

    frac = smooth1d(
        frac,
        window=max(
            3,
            int(length * 0.005) | 1
        )
    )

    whiteish = (
        frac < max_ink_fraction
    )

    min_width = max(
        3,
        int(length * min_width_fraction)
    )

    edge_ignore = int(
        length * edge_ignore_fraction
    )

    runs = []

    start = None

    for i, flag in enumerate(whiteish):

        if flag and start is None:
            start = i

        elif not flag and start is not None:
            if i - start >= min_width:
                runs.append((start, i))
            start = None

    if start is not None:
        if length - start >= min_width:
            runs.append((start, length))

    # Ignore outer margins
    runs = [
        (a, b)
        for a, b in runs
        if (
            a > edge_ignore
            and b < length - edge_ignore
        )
    ]

    return runs

def split_positions_from_gutters(gutters):
    return [
        int((a + b) / 2)
        for a, b in gutters
    ]

def make_rects_from_splits(
    width,
    height,
    x_splits,
    y_splits
):
    xs = [0] + sorted(x_splits) + [width]
    ys = [0] + sorted(y_splits) + [height]

    rects = []

    for r in range(len(ys) - 1):
        for c in range(len(xs) - 1):

            x0 = xs[c]
            x1 = xs[c + 1]
            y0 = ys[r]
            y1 = ys[r + 1]

            w = x1 - x0
            h = y1 - y0

            if w < width * 0.08:
                continue

            if h < height * 0.08:
                continue

            rects.append(
                (x0, y0, x1, y1)
            )

    return rects

def score_rect_content(img, rect):
    crop = img.crop(rect).convert("L")
    arr = np.array(crop)

    ink_fraction = (
        arr < 245
    ).mean()

    return float(ink_fraction)

def detect_panel_rects(
    img,
    expected_panels
):
    """
    Try whitespace splits and choose layout
    whose number of content-containing cells
    is closest to expected_panels.
    """

    trimmed, trim_box = trim_outer_white(img)

    v_gutters = find_gutters(
        trimmed,
        axis=1
    )

    h_gutters = find_gutters(
        trimmed,
        axis=0
    )

    v_positions = split_positions_from_gutters(
        v_gutters
    )

    h_positions = split_positions_from_gutters(
        h_gutters
    )

    # limit to strongest-like candidates by width
    v_positions = v_positions[:6]
    h_positions = h_positions[:6]

    candidates = []

    # Try subsets of top gutters.
    # This gives grid candidates like 1x2, 2x2, 2x3...
    x_choices = [[]]

    for x in v_positions:
        x_choices.append([x])

    if len(v_positions) >= 2:
        x_choices.append(v_positions[:2])

    if len(v_positions) >= 3:
        x_choices.append(v_positions[:3])

    y_choices = [[]]

    for y in h_positions:
        y_choices.append([y])

    if len(h_positions) >= 2:
        y_choices.append(h_positions[:2])

    if len(h_positions) >= 3:
        y_choices.append(h_positions[:3])

    for xs in x_choices:
        for ys in y_choices:

            rects = make_rects_from_splits(
                trimmed.width,
                trimmed.height,
                xs,
                ys
            )

            useful = []

            for rect in rects:
                score = score_rect_content(
                    trimmed,
                    rect
                )

                if score > 0.015:
                    useful.append(
                        (rect, score)
                    )

            n = len(useful)

            if n == 0:
                continue

            # Main objective: match panel count.
            # Secondary: avoid crazy fragmentation.
            count_penalty = abs(
                n - expected_panels
            )

            fragment_penalty = (
                len(rects) - n
            ) * 0.25

            total_score = (
                count_penalty
                + fragment_penalty
            )

            candidates.append({
                "score": total_score,
                "rects": [
                    r for r, s in useful
                ],
                "trim_box": trim_box
            })

    if not candidates:
        return [], trim_box

    candidates.sort(
        key=lambda x: x["score"]
    )

    best = candidates[0]

    rects = best["rects"]

    # reading order:
    # top-to-bottom, left-to-right
    rects.sort(
        key=lambda r: (
            r[1],
            r[0]
        )
    )

    # force expected count if too many:
    if len(rects) > expected_panels:
        rects = rects[:expected_panels]

    return rects, trim_box

# ============================================================
# FALLBACK GRID
# ============================================================

def fallback_grid_rects(
    img,
    expected_panels
):
    """
    Choose sensible regular grid.
    """

    if expected_panels <= 1:
        rows, cols = 1, 1

    elif expected_panels == 2:
        rows, cols = 1, 2

    elif expected_panels == 3:
        rows, cols = 1, 3

    elif expected_panels == 4:
        rows, cols = 2, 2

    elif expected_panels <= 6:
        rows, cols = 2, 3

    else:
        cols = 3
        rows = math.ceil(
            expected_panels / cols
        )

    rects = []

    for r in range(rows):
        for c in range(cols):

            if len(rects) >= expected_panels:
                break

            x0 = int(
                img.width * c / cols
            )

            x1 = int(
                img.width * (c + 1) / cols
            )

            y0 = int(
                img.height * r / rows
            )

            y1 = int(
                img.height * (r + 1) / rows
            )

            rects.append(
                (x0, y0, x1, y1)
            )

    return rects

# ============================================================
# CROP
# ============================================================

def crop_panel(
    img,
    rect,
    padding=10
):
    x0, y0, x1, y1 = rect

    x0 = max(
        0,
        x0 - padding
    )

    y0 = max(
        0,
        y0 - padding
    )

    x1 = min(
        img.width,
        x1 + padding
    )

    y1 = min(
        img.height,
        y1 + padding
    )

    return img.crop(
        (x0, y0, x1, y1)
    )

# ============================================================
# UI
# ============================================================

lang = language_selector()

render_openai_usage_panel(lang=lang)

render_knowledge_archive_widget(lang=lang)

st.title(L(lang,"✂️ Experimental Panel Crop Explorer","✂️ Experimental Panel Crop Explorer"))

st.caption(L(lang,
    "자동 panel crop beta — whitespace segmentation + caption labels",
    "Automatic panel cropping beta — whitespace segmentation + caption labels"
))

st.sidebar.header(L(lang,"검색","Search"))

selected_method = st.sidebar.selectbox(
    "Method",
    sorted(
        profiles_by_name.keys()
    )
)

keyword = st.sidebar.text_input(
    L(lang,"키워드","Keyword"),
    placeholder="Foxp3, T cell, IL-6 ..."
).strip()

segmentation_mode = st.sidebar.radio(
    L(lang,"Crop 방식","Crop mode"),
    [
        "Auto whitespace",
        "Fallback regular grid"
    ]
)

profile = profiles_by_name[
    selected_method
]

keyword_lower = keyword.lower()

figure_items = []

for paper in profile.get(
    "papers",
    []
):

    pmcid = paper.get(
        "pmcid",
        ""
    )

    title = paper.get(
        "title",
        ""
    )

    doi = paper.get(
        "doi",
        ""
    )

    year = paper.get(
        "year",
        ""
    )

    for fig in paper.get(
        "figures",
        []
    ):

        fig_name = fig.get(
            "figure",
            "Figure"
        )

        caption = fig.get(
            "caption",
            ""
        )

        if keyword_lower:

            combined = (
                title
                + " "
                + caption
            ).lower()

            if keyword_lower not in combined:
                continue

        image_info = (
            image_index
            .get(pmcid, {})
            .get(fig_name, {})
        )

        href = image_info.get(
            "href",
            ""
        )

        local_image = (
            find_cached_image(
                pmcid,
                href
            )
        )

        if not local_image:
            continue

        panels = split_caption_panels(
            caption
        )

        if len(panels) < 2:
            continue

        figure_items.append({
            "pmcid": pmcid,
            "title": title,
            "year": year,
            "doi": doi,
            "figure_name": fig_name,
            "caption": caption,
            "image_path": local_image,
            "panels": panels
        })

st.write(L(lang,
    f"Panel crop 가능한 Figure: **{len(figure_items)}개**",
    f"Figures available for panel cropping: **{len(figure_items)}**"
))

if not figure_items:
    st.warning(L(lang,
        "현재 캐시된 이미지 중 panel label을 2개 이상 인식한 Figure가 없습니다.",
        "No cached Figure currently has two or more detected panel labels."
    ))
    st.stop()

selected_index = st.selectbox(
    L(lang,"Figure 선택","Select Figure"),
    range(
        len(figure_items)
    ),
    format_func=lambda i: (
        f"{figure_items[i]['figure_name']} | "
        f"{figure_items[i]['title'][:90]}"
    )
)

item = figure_items[
    selected_index
]

st.divider()

st.subheader(
    f"{item['figure_name']} — "
    f"{item['title']}"
)

img = Image.open(
    item["image_path"]
).convert("RGB")

st.image(
    img,
    caption=L(lang,"원본 Figure","Original Figure"),
    use_container_width=True
)

expected = len(
    item["panels"]
)

st.write(L(lang,
    f"Caption에서 감지한 panel 수: **{expected}개**",
    f"Panels detected from caption: **{expected}**"
))

# ============================================================
# SPLIT
# ============================================================

trimmed, trim_box = trim_outer_white(
    img
)

if segmentation_mode == "Auto whitespace":

    rects, auto_trim_box = (
        detect_panel_rects(
            img,
            expected
        )
    )

    work_img = img.crop(
        auto_trim_box
    )

    if len(rects) != expected:

        st.warning(
            L(lang,
            f"자동 segmentation이 {len(rects)}개 영역을 찾았습니다. caption panel 수({expected})와 달라 regular grid fallback을 사용합니다.",
            f"Automatic segmentation found {len(rects)} regions, which differs from the caption panel count ({expected}); using regular-grid fallback."
        )
        )

        work_img = trimmed

        rects = fallback_grid_rects(
            work_img,
            expected
        )

    else:

        st.success(
            L(lang,
            f"자동 segmentation 성공: {len(rects)}개 영역",
            f"Automatic segmentation succeeded: {len(rects)} regions"
        )
        )

else:

    work_img = trimmed

    rects = fallback_grid_rects(
        work_img,
        expected
    )

# ============================================================
# PANEL DISPLAY
# ============================================================

st.divider()

cols_per_row = 2

for start in range(
    0,
    expected,
    cols_per_row
):

    cols = st.columns(
        cols_per_row
    )

    for offset in range(
        cols_per_row
    ):

        idx = start + offset

        if idx >= expected:
            continue

        panel = item["panels"][idx]

        rect = rects[idx]

        crop = crop_panel(
            work_img,
            rect
        )

        with cols[offset]:

            st.markdown(
                f"## Panel {panel['label']}"
            )

            st.image(
                crop,
                use_container_width=True
            )

            st.markdown(
                f"**{L(lang,'Panel caption','Panel caption')}**"
            )

            st.write(
                panel["text"]
            )

# ============================================================
# ORIGINAL CAPTION
# ============================================================

with st.expander(
    L(lang,"원문 Figure caption 전체","Full original Figure caption")
):
    st.write(
        item["caption"]
    )

st.caption(L(lang,
    "Beta: 자동 crop은 OCR이 아니라 whitespace/layout heuristic을 사용합니다. 복잡한 multi-panel Figure는 잘못 나뉠 수 있으며 그 경우 regular-grid fallback을 사용할 수 있습니다.",
    "Beta: automatic cropping uses whitespace/layout heuristics, not OCR. Complex multi-panel figures can be split incorrectly. If so, switch to the regular-grid fallback."
))
