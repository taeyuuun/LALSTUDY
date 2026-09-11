import json
import zipfile
import io
import sqlite3
import requests
import streamlit as st
from pathlib import Path
import math
import re
import html
from i18n import language_selector, L
from knowledge_widget import render_knowledge_archive_widget
from openai_sidebar import render_openai_usage_panel

DATA_FILE = Path("method_profiles.json")
IMAGE_INDEX_FILE = Path("figure_images.json")
LICENSE_FILE = Path("license_metadata.json")
DB_FILE = Path("research_1000.db")
CACHE_DIR = Path("figure_cache")
CACHE_DIR.mkdir(exist_ok=True)

FIGURES_PER_PAGE = 8

st.set_page_config(
    page_title="LALSTUDY · Figure Explorer",
    page_icon="🧬",
    layout="wide"
)

@st.cache_data
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

profiles = load_json(DATA_FILE)
image_index = load_json(IMAGE_INDEX_FILE) if IMAGE_INDEX_FILE.exists() else {}
license_metadata = load_json(LICENSE_FILE) if LICENSE_FILE.exists() else {}
profiles_by_name = {p["name"]: p for p in profiles}

LICENSE_URLS = {
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-NC-ND 4.0": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif",
    ".tif", ".tiff", ".webp"
}

def clean_markup(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()

def unique_keep_order(items):
    out = []
    seen = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out

@st.cache_data
def load_figure_rights():
    rights = {}
    if not DB_FILE.exists():
        return rights

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    try:
        cur.execute("""
        SELECT p.pmcid, f.figure_name, fr.rights_status, fr.rights_evidence
        FROM figure_rights AS fr
        JOIN figures AS f ON fr.figure_id = f.id
        JOIN papers AS p ON f.paper_id = p.id
        """)

        for pmcid, figure_name, status, evidence in cur.fetchall():
            rights[(pmcid, figure_name)] = {
                "status": status,
                "evidence": evidence or ""
            }
    except sqlite3.OperationalError:
        pass

    conn.close()
    return rights

figure_rights = load_figure_rights()

def paper_cache_dir(pmcid):
    folder = CACHE_DIR / pmcid
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def download_inline_images(pmcid):
    folder = paper_cache_dir(pmcid)
    marker = folder / "_download_complete.txt"

    if marker.exists():
        return True, "cached"

    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/"
        f"{pmcid}/supplementaryFiles"
    )

    try:
        response = requests.get(url, timeout=90)
        response.raise_for_status()

        zbytes = io.BytesIO(response.content)
        if not zipfile.is_zipfile(zbytes):
            return False, "응답이 ZIP 파일이 아닙니다."

        image_count = 0

        with zipfile.ZipFile(zbytes) as z:
            for member in z.infolist():
                if member.is_dir():
                    continue

                name = Path(member.filename).name
                suffix = Path(name).suffix.lower()

                if suffix not in IMAGE_EXTENSIONS:
                    continue

                target = folder / name
                with z.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())

                image_count += 1

        marker.write_text(str(image_count), encoding="utf-8")
        return True, f"{image_count} images cached"

    except Exception as e:
        return False, str(e)

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
            and not p.name.startswith("_")
            and p.suffix.lower() in IMAGE_EXTENSIONS
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

def get_license_info(pmcid):
    return license_metadata.get(
        pmcid,
        {
            "license_code": "UNKNOWN",
            "display_policy": "LINK_ONLY_OR_REVIEW",
            "copyright_statement": ""
        }
    )

def get_figure_rights(pmcid, figure_name):
    return figure_rights.get(
        (pmcid, figure_name),
        {
            "status": "UNKNOWN",
            "evidence": ""
        }
    )

def can_display_figure(pmcid, figure_name):
    lic = get_license_info(pmcid)
    rights = get_figure_rights(pmcid, figure_name)

    if rights["status"] == "REVIEW_REQUIRED":
        return False

    return lic["display_policy"] in {
        "SHOW_WITH_ATTRIBUTION",
        "SHOW_NONCOMMERCIAL_UNMODIFIED_WITH_ATTRIBUTION",
        "SHOW"
    }

METHOD_TERMS = []

for profile in profiles:
    canonical = profile.get("name", "")
    terms = [canonical] + profile.get("aliases", [])

    for term in terms:
        if term and len(term) >= 2:
            METHOD_TERMS.append((term, canonical))

def contains_term(text, term):
    pattern = (
        r"(?<![A-Za-z0-9])"
        + re.escape(term)
        + r"(?![A-Za-z0-9])"
    )
    return bool(re.search(pattern, text, flags=re.IGNORECASE))

def detect_methods_explicit(text):
    found = []
    for term, canonical in METHOD_TERMS:
        if contains_term(text, term):
            found.append(canonical)
    return unique_keep_order(found)[:8]

PANEL_LABEL_RE = r"[a-hA-H](?:\s*[–—-]\s*[a-hA-H])?(?:\s*,\s*[a-hA-H])*"

def normalize_panel_label(label):
    label = label.strip().replace("—", "–").replace("-", "–")
    label = re.sub(r"\s+", "", label)
    return label.upper()

def find_panel_markers(caption):
    candidates = []

    # High-confidence: (a), (b), (a-c)
    pattern_parenthesized = re.compile(
        rf"\(({PANEL_LABEL_RE})\)",
        re.IGNORECASE
    )

    for m in pattern_parenthesized.finditer(caption):
        candidates.append({
            "label": normalize_panel_label(m.group(1)),
            "marker_start": m.start(),
            "content_start": m.end(),
            "confidence": "high"
        })

    # High-confidence: "a, Representative..." after start/period/semicolon
    pattern_punctuated = re.compile(
        rf"(?:^|(?<=[.;]))\s*"
        rf"({PANEL_LABEL_RE})"
        rf"\s*[,:\.]\s+",
        re.IGNORECASE
    )

    for m in pattern_punctuated.finditer(caption):
        candidates.append({
            "label": normalize_panel_label(m.group(1)),
            "marker_start": m.start(1),
            "content_start": m.end(),
            "confidence": "high"
        })

    # Medium confidence: "a Experimental design. b UMAP..."
    pattern_bare = re.compile(
        r"(?:^|(?<=[.;]))\s*"
        r"([a-hA-H])\s+"
        r"(?=[A-Z0-9αβγΔ])"
    )

    for m in pattern_bare.finditer(caption):
        candidates.append({
            "label": normalize_panel_label(m.group(1)),
            "marker_start": m.start(1),
            "content_start": m.end(),
            "confidence": "medium"
        })

    by_position = {}

    for item in candidates:
        pos = item["marker_start"]
        if pos not in by_position:
            by_position[pos] = item
        elif (
            item["confidence"] == "high"
            and by_position[pos]["confidence"] != "high"
        ):
            by_position[pos] = item

    markers = sorted(
        by_position.values(),
        key=lambda x: x["marker_start"]
    )

    high_count = sum(
        1 for m in markers
        if m["confidence"] == "high"
    )

    if len(markers) < 2 and high_count == 0:
        return []

    return markers

def split_caption_into_panels(caption):
    caption = clean_markup(caption)
    markers = find_panel_markers(caption)

    if not markers:
        return [{
            "label": "FULL",
            "text": caption,
            "confidence": "fallback"
        }]

    panels = []

    preamble = caption[:markers[0]["marker_start"]].strip(" .;:")
    if preamble and len(preamble) > 10:
        panels.append({
            "label": "OVERVIEW",
            "text": preamble,
            "confidence": "context"
        })

    for i, marker in enumerate(markers):
        start = marker["content_start"]
        end = markers[i + 1]["marker_start"] if i + 1 < len(markers) else len(caption)

        text = caption[start:end].strip(" .;:")

        if text:
            panels.append({
                "label": marker["label"],
                "text": text,
                "confidence": marker["confidence"]
            })

    return panels

PANEL_TYPE_RULES = [
    (
        "Flow cytometry / gating",
        [r"\bflow cytometr", r"\bFACS\b", r"\bgating\b", r"\bdot plot\b"]
    ),
    (
        "UMAP / dimensionality reduction",
        [r"\bUMAP\b", r"\bt-?SNE\b", r"\bdimensionality reduction\b"]
    ),
    (
        "Microscopy / representative image",
        [r"\bmicroscop", r"\bconfocal\b", r"\bimmunofluorescen",
         r"\brepresentative images?\b", r"\bfluorescence images?\b"]
    ),
    (
        "Histology / tissue staining",
        [r"\bhistolog", r"\bH&E\b", r"\bhematoxylin", r"\bimmunohistochem"]
    ),
    (
        "Western blot / immunoblot",
        [r"\bwestern blot", r"\bimmunoblot", r"\bblotting\b"]
    ),
    ("Heatmap", [r"\bheat ?map\b"]),
    ("Volcano plot", [r"\bvolcano plot\b"]),
    (
        "Survival curve",
        [r"\bKaplan[- ]Meier\b", r"\bsurvival curve\b", r"\boverall survival\b"]
    ),
    (
        "ELISA / concentration assay",
        [r"\bELISA\b", r"\benzyme-linked immunosorbent\b"]
    ),
    (
        "Sequencing / transcriptomics",
        [r"\bRNA[- ]?seq\b", r"\bRNA sequencing\b",
         r"\bsingle[- ]cell RNA\b", r"\btranscriptom"]
    ),
    (
        "Schematic / experimental design",
        [r"\bschematic\b", r"\bexperimental design\b",
         r"\bstudy design\b", r"\bworkflow\b"]
    ),
    (
        "Quantification / summary graph",
        [r"\bquantification\b", r"\bpercentage\b", r"\bfrequency\b",
         r"\bmean\b", r"\brelative\b", r"\bnormalized\b"]
    ),
]

def detect_panel_type(text):
    scores = []

    for label, patterns in PANEL_TYPE_RULES:
        score = sum(
            1 for pattern in patterns
            if re.search(pattern, text, re.IGNORECASE)
        )

        if score:
            scores.append((score, label))

    if not scores:
        return "Experimental result / unspecified"

    scores.sort(reverse=True)
    return scores[0][1]

SAMPLE_PATTERNS = [
    ("Human patients", r"\bpatients?\b|\bhuman subjects?\b"),
    ("Human", r"\bhuman\b"),
    ("Mouse / mice", r"\bmice\b|\bmouse\b|\bmurine\b"),
    ("PBMC", r"\bPBMCs?\b|peripheral blood mononuclear cells?"),
    ("Whole blood", r"\bwhole blood\b"),
    ("Plasma", r"\bplasma\b"),
    ("Serum", r"\bserum\b"),
    ("Bone marrow", r"\bbone marrow\b"),
    ("Lymph node", r"\blymph nodes?\b"),
    ("Spleen", r"\bspleen\b|\bsplenic\b"),
    ("Lung", r"\blung\b|\bpulmonary\b"),
    ("Tumor tissue", r"\btumou?r\b|\btumou?r tissue\b"),
    ("Macrophages", r"\bmacrophages?\b"),
    ("Monocytes", r"\bmonocytes?\b"),
    ("Neutrophils", r"\bneutrophils?\b"),
    ("Dendritic cells", r"\bdendritic cells?\b|\bDCs\b"),
    ("CD4 T cells", r"\bCD4\+?\s*T[- ]?cells?\b"),
    ("CD8 T cells", r"\bCD8\+?\s*T[- ]?cells?\b"),
    ("T cells", r"\bT[- ]?cells?\b"),
    ("B cells", r"\bB[- ]?cells?\b"),
    ("NK cells", r"\bNK[- ]?cells?\b|natural killer cells?"),
    ("Fibroblasts", r"\bfibroblasts?\b"),
    ("Epithelial cells", r"\bepithelial cells?\b"),
]

def detect_samples(text):
    found = []

    for label, pattern in SAMPLE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(label)

    if "CD4 T cells" in found or "CD8 T cells" in found:
        if "T cells" in found:
            found.remove("T cells")

    return found[:8]

TARGET_REGEXES = [
    r"\bCD\d{1,3}[A-Za-z0-9]*\+?\b",
    r"\bPD-?1\b",
    r"\bPD-L1\b",
    r"\bCTLA-?4\b",
    r"\bFOXP3\b",
    r"\bFoxp3\b",
    r"\bKi-?67\b",
    r"\bIL[- ]?\d+[A-Za-z]?\b",
    r"\bTNF[- ]?α?\b",
    r"\bTGF[- ]?β\d*\b",
    r"\bIFN[- ]?[αβγA-Za-z0-9]+\b",
    r"\bCXCL\d+\b",
    r"\bCCL\d+\b",
    r"\bCXCR\d+\b",
    r"\bCCR\d+\b",
    r"\bTLR\d+\b",
    r"\bSTAT\d+\b",
    r"\bpSTAT\d+\b",
    r"\bHLA-[A-Za-z0-9]+\b",
    r"\bNLRP\d+\b",
    r"\bcGAS\b",
    r"\bSTING\b",
    r"\bmTORC?1?\b",
    r"\bNF-?κB\b",
    r"\bGSDM[A-Z]\b",
    r"\bTREM\d+\b",
]

def detect_targets(text):
    found = []

    for pattern in TARGET_REGEXES:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if isinstance(match, tuple):
                match = "".join(match)
            found.append(match)

    for token in re.findall(r"\b[A-Z][A-Z0-9]{2,8}\b", text):
        if token in {
            "DNA", "RNA", "PBS", "SEM", "SD",
            "NS", "WT", "KO", "OVA", "FACS",
            "UMAP", "ELISA", "PCR"
        }:
            continue
        found.append(token)

    return unique_keep_order(found)[:12]

READOUT_PATTERNS = [
    ("Cell frequency / proportion", r"\bfrequency\b|\bpercentage\b|\bproportion\b|%\s*of"),
    ("Expression", r"\bexpression\b|\bexpressing\b"),
    ("Fluorescence / MFI", r"\bMFI\b|\bfluorescen"),
    ("Cytokine level", r"\bcytokine\b|\bpg/ml\b|\bng/ml\b"),
    ("Cell count", r"\bcell count\b|\bnumbers? of\b"),
    ("Proliferation", r"\bproliferation\b|\bproliferative\b"),
    ("Viability", r"\bviability\b|\bviable\b"),
    ("Apoptosis / cell death", r"\bapoptosis\b|\bcell death\b|\bdead cells?\b"),
    ("Signaling / phosphorylation", r"\bphosphorylat|\bpSTAT\b"),
    ("Tumor burden", r"\btumou?r volume\b|\btumou?r burden\b|\btumou?r size\b"),
    ("Survival", r"\bsurvival\b"),
    ("Gene expression", r"\btranscript|\bgene expression\b|\bmRNA\b"),
    ("Protein abundance", r"\bprotein level\b|\bprotein abundance\b"),
]

def detect_readouts(text):
    found = []
    for label, pattern in READOUT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(label)
    return found[:6]

def detect_comparisons(text):
    rules = [
        (r"\bversus\b|\bvs\.?\b", "Group A vs Group B"),
        (r"\bcontrol\b", "Control included"),
        (r"\bvehicle\b", "Vehicle control"),
        (r"\btreated with\b|\btreatment\b", "Treatment comparison"),
        (r"\bWT\b|wild[- ]type", "WT comparison"),
        (r"\bKO\b|\bknockout\b|\bdeficien", "KO / deficiency comparison"),
        (r"\bbefore\b.*\bafter\b|\bpre[- ]?.*\bpost[- ]?", "Before vs after"),
    ]

    found = []
    for pattern, label in rules:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(label)

    return found[:5]

def infer_panel_purpose(panel_type, targets, lang):
    target_text = ", ".join(targets[:3]) if targets else L(lang,"주요 지표","key readouts")
    if panel_type == "Flow cytometry / gating":
        return L(lang, f"세포 population을 gating하거나 {target_text} 양성 세포의 분포를 보여주는 패널로 추정됩니다.", f"Likely shows cell-population gating or the distribution of cells positive for {target_text}.")
    if panel_type == "Quantification / summary graph":
        return L(lang, f"다른 패널에서 관찰한 결과를 정량화하여 {target_text}의 차이를 비교하는 패널로 추정됩니다.", f"Likely quantifies observations from other panels and compares differences in {target_text}.")
    if panel_type == "Microscopy / representative image":
        return L(lang, f"조직/세포에서 {target_text}의 위치 또는 형태를 대표 이미지로 보여주는 패널로 추정됩니다.", f"Likely provides representative images of the localization or morphology of {target_text} in cells or tissue.")
    if panel_type == "UMAP / dimensionality reduction":
        return L(lang,"고차원 단일세포 데이터를 저차원 공간에 배치해 세포군 또는 상태의 구조를 보여주는 패널로 추정됩니다.","Likely projects high-dimensional single-cell data into a low-dimensional space to show cell populations or states.")
    if panel_type == "Western blot / immunoblot":
        return L(lang, f"{target_text} 단백질의 abundance 또는 signaling 변화를 band로 확인하는 패널로 추정됩니다.", f"Likely uses bands to assess abundance or signaling changes involving {target_text}.")
    if panel_type == "Heatmap":
        return L(lang,"여러 gene/protein/cell state의 상대적 패턴을 색으로 비교하는 패널로 추정됩니다.","Likely compares relative patterns across genes, proteins, or cell states using color intensity.")
    if panel_type == "Schematic / experimental design":
        return L(lang,"실험군, 처리 과정 또는 전체 workflow를 설명하는 설계도 패널로 추정됩니다.","Likely summarizes experimental groups, treatment steps, or the overall workflow.")
    return L(lang, f"{target_text}에 대한 실험 결과를 보여주는 패널로 추정됩니다.", f"Likely presents an experimental result involving {target_text}.")

def build_panel_card(panel_text, figure_level_method):
    panel_text = clean_markup(panel_text)

    methods = detect_methods_explicit(panel_text)
    samples = detect_samples(panel_text)
    targets = detect_targets(panel_text)
    readouts = detect_readouts(panel_text)
    comparisons = detect_comparisons(panel_text)
    panel_type = detect_panel_type(panel_text)
    purpose = infer_panel_purpose(panel_type, targets, lang)

    return {
        "panel_type": panel_type,
        "purpose": purpose,
        "methods": methods,
        "samples": samples,
        "targets": targets,
        "readouts": readouts,
        "comparisons": comparisons,
        "figure_level_method": figure_level_method
    }

lang = language_selector()

render_openai_usage_panel(lang=lang)

render_knowledge_archive_widget(lang=lang)

st.title(L(lang,"🧬 실험 Figure Explorer","🧬 Experimental Figure Explorer"))
st.caption(L(lang,
    "Figure → Panel A/B/C/D → 실험 해석",
    "Figure → Panel A/B/C/D → experimental interpretation"
))

st.sidebar.header(L(lang,"Figure 검색","Figure Search"))

method_options = sorted(profiles_by_name.keys())

jump_method = st.session_state.pop(
    "lal_method_jump",
    None
)

if (
    jump_method
    and jump_method in method_options
):
    st.session_state[
        "lal_explorer_method"
    ] = jump_method

if (
    st.session_state.get(
        "lal_explorer_method"
    )
    not in method_options
):
    st.session_state[
        "lal_explorer_method"
    ] = method_options[0]

selected_method = st.sidebar.selectbox(
    "Method",
    method_options,
    key="lal_explorer_method",
)

keyword = st.sidebar.text_input(
    "Keyword",
    placeholder="Foxp3, IL-6, T cell, tumor ..."
).strip()

safe_only = st.sidebar.checkbox(
    L(lang,"공개 표시 가능 Figure만","Only Figures allowed for public display"),
    value=True
)

profile = profiles_by_name[selected_method]

st.header(selected_method)

a, b, c, d = st.columns(4)
a.metric("Papers", profile.get("paper_count", 0))
b.metric("Figures", profile.get("figure_count", 0))
c.metric("Category", profile.get("category") or "-")
d.metric("Submethods", len(profile.get("submethods", [])))

keyword_lower = keyword.lower()
gallery_items = []

for paper in profile.get("papers", []):
    pmcid = paper.get("pmcid", "")
    title = clean_markup(paper.get("title", ""))
    doi = paper.get("doi", "")
    year = paper.get("year", "")

    for figure in paper.get("figures", []):
        figure_name = figure.get("figure", "Figure")
        caption = clean_markup(figure.get("caption", ""))

        if keyword_lower:
            combined = (title + " " + caption).lower()
            if keyword_lower not in combined:
                continue

        image_info = (
            image_index
            .get(pmcid, {})
            .get(figure_name, {})
        )

        href = image_info.get("href", "")
        allowed = can_display_figure(pmcid, figure_name)

        if safe_only and not allowed:
            continue

        raw_panels = split_caption_into_panels(caption)

        panels = []
        for panel in raw_panels:
            panel_card = build_panel_card(
                panel["text"],
                selected_method
            )
            panels.append({
                **panel,
                **panel_card
            })

        gallery_items.append({
            "pmcid": pmcid,
            "doi": doi,
            "title": title,
            "year": year,
            "figure_name": figure_name,
            "caption": caption,
            "href": href,
            "allowed": allowed,
            "panels": panels,
        })

st.divider()
st.subheader(L(lang,"🖼 Panel-aware Figure Gallery","🖼 Panel-aware Figure Gallery"))
st.write(L(lang,f"검색된 Figure: **{len(gallery_items)}개**",f"Figures found: **{len(gallery_items)}**"))

panel_total = sum(
    len(item["panels"])
    for item in gallery_items
)

st.write(L(lang,
    f"자동 분리된 Panel/segment: **{panel_total}개**",
    f"Automatically separated panels/segments: **{panel_total}**"
))

if not gallery_items:
    st.warning(L(lang,"조건에 맞는 Figure가 없습니다.","No Figures match the current filters."))
    st.stop()

search_signature = (
    selected_method,
    keyword,
    safe_only
)

if "last_search_signature" not in st.session_state:
    st.session_state.last_search_signature = search_signature

if st.session_state.last_search_signature != search_signature:
    st.session_state.gallery_page = 1
    st.session_state.last_search_signature = search_signature

total_pages = math.ceil(
    len(gallery_items) / FIGURES_PER_PAGE
)

if "gallery_page" not in st.session_state:
    st.session_state.gallery_page = 1

if st.session_state.gallery_page > total_pages:
    st.session_state.gallery_page = 1

nav1, nav2, nav3 = st.columns([1, 3, 1])

with nav1:
    if st.button(
        L(lang,"⬅ 이전","⬅ Previous"),
        disabled=st.session_state.gallery_page <= 1,
        use_container_width=True
    ):
        st.session_state.gallery_page -= 1
        st.rerun()

with nav2:
    st.markdown(
        "<div style='text-align:center;font-size:18px'>"
        f"Page {st.session_state.gallery_page} / {total_pages}"
        "</div>",
        unsafe_allow_html=True
    )

with nav3:
    if st.button(
        L(lang,"다음 ➡","Next ➡"),
        disabled=st.session_state.gallery_page >= total_pages,
        use_container_width=True
    ):
        st.session_state.gallery_page += 1
        st.rerun()

start = (
    st.session_state.gallery_page - 1
) * FIGURES_PER_PAGE

page_items = gallery_items[
    start:start + FIGURES_PER_PAGE
]

pmcids_needed = sorted({
    item["pmcid"]
    for item in page_items
    if (
        item["allowed"]
        and item["pmcid"]
        and not find_cached_image(
            item["pmcid"],
            item["href"]
        )
    )
})

if pmcids_needed:
    if st.button(
        L(lang,
            f"📥 현재 페이지 이미지 불러오기 ({len(pmcids_needed)}개 논문)",
            f"📥 Load images for this page ({len(pmcids_needed)} papers)"
        ),
        type="primary",
        use_container_width=True
    ):
        progress = st.progress(0)
        failures = []

        for i, pmcid in enumerate(pmcids_needed, start=1):
            ok, message = download_inline_images(pmcid)

            if not ok:
                failures.append((pmcid, message))

            progress.progress(i / len(pmcids_needed))

        if failures:
            with st.expander(
                L(lang,f"다운로드 실패 {len(failures)}개",f"Download failures: {len(failures)}")
            ):
                for pmcid, message in failures:
                    st.write(pmcid, message)

        st.rerun()

st.divider()

for item in page_items:
    pmcid = item["pmcid"]
    fig_name = item["figure_name"]

    lic = get_license_info(pmcid)
    rights = get_figure_rights(pmcid, fig_name)

    with st.container(border=True):
        st.markdown(f"## {fig_name}")
        st.caption(item["title"])

        image_col, meta_col = st.columns([1.5, 1])

        with image_col:
            if item["allowed"]:
                local_image = find_cached_image(
                    pmcid,
                    item["href"]
                )

                if local_image:
                    st.image(
                        str(local_image),
                        use_container_width=True
                    )
                else:
                    st.info(L(lang,"이미지 미캐시","Image not cached"))
            else:
                st.warning(L(lang,
                    "⚠️ 권리 검토 필요 — 이미지를 표시하지 않습니다.",
                    "⚠️ Rights review required — image is not displayed."
                ))

        with meta_col:
            st.markdown(f"**Year:** {item['year']}")
            st.markdown(
                f"**Figure-level method context:** "
                f"`{selected_method}`"
            )
            st.markdown(
                f"**Panels detected:** "
                f"{len(item['panels'])}"
            )

            license_code = lic.get(
                "license_code",
                "UNKNOWN"
            )

            if license_code == "CC BY 4.0":
                st.success("CC BY 4.0")
            elif license_code == "CC BY-NC-ND 4.0":
                st.info("CC BY-NC-ND 4.0")
            else:
                st.warning(license_code)

        st.markdown(
            L(lang,"### 🔬 Panel별 해석","### 🔬 Panel-by-panel interpretation")
        )

        panels = item["panels"]

        panel_labels = [
            (
                L(lang,"전체 설명","Overview")
                if panel["label"] == "OVERVIEW"
                else (
                    "Full Figure"
                    if panel["label"] == "FULL"
                    else f"Panel {panel['label']}"
                )
            )
            for panel in panels
        ]

        tabs = st.tabs(panel_labels)

        for tab, panel in zip(tabs, panels):
            with tab:
                p_left, p_right = st.columns([1.15, 1])

                with p_left:
                    st.markdown(
                        f"#### {panel['panel_type']}"
                    )
                    st.write(panel["purpose"])

                    if panel["methods"]:
                        st.markdown(
                            L(lang,"**이 panel에서 명시적으로 확인된 실험기법**","**Experimental methods explicitly mentioned in this panel**")
                        )
                        st.write(
                            " · ".join(panel["methods"])
                        )
                    else:
                        st.caption(
                            L(lang,
                            f"Panel 문장 자체에는 method가 명시되지 않았습니다. Figure-level tag는 {selected_method}입니다.",
                            f"The panel text does not explicitly name a method. The Figure-level tag is {selected_method}."
                        )
                        )

                    if panel["samples"]:
                        st.markdown(L(lang,"**샘플 / 모델**","**Sample / Model**"))
                        st.write(
                            " · ".join(panel["samples"])
                        )

                    if panel["targets"]:
                        st.markdown("**Marker / Target**")
                        st.write(
                            " · ".join(panel["targets"])
                        )

                    if panel["readouts"]:
                        st.markdown("**Readout**")
                        st.write(
                            " · ".join(panel["readouts"])
                        )

                    if panel["comparisons"]:
                        st.markdown(L(lang,"**비교 구조**","**Comparison structure**"))
                        st.write(
                            " · ".join(panel["comparisons"])
                        )

                with p_right:
                    st.markdown("#### Panel caption")
                    st.write(panel["text"])

                    if panel["confidence"] == "fallback":
                        st.warning(L(lang,
                            "Panel label을 안정적으로 분리하지 못해 Figure 전체 caption을 사용했습니다.",
                            "Panel labels could not be separated reliably, so the full Figure caption is used."
                        ))
                    elif panel["confidence"] == "medium":
                        st.caption(
                            "Panel label 자동 인식: medium confidence"
                        )

        with st.expander(
            L(lang,"🧠 이 Figure를 공부할 때 추천 순서","🧠 Suggested order for studying this Figure")
        ):
            st.markdown(L(lang,
                """
**1. Overview / schematic가 있으면 먼저 본다.**  
실험군, 처리 순서, sample이 무엇인지 잡는다.

**2. Gating / microscopy / UMAP 같은 관찰 패널을 본다.**  
무엇을 어떻게 측정했는지 파악한다.

**3. Quantification panel을 본다.**  
앞 패널의 시각적 차이가 실제 숫자로도 차이가 나는지 확인한다.

**4. 비교군을 확인한다.**  
WT vs KO, control vs treatment, patient vs healthy 등 무엇을 기준으로 결론을 내렸는지 본다.

**5. 마지막으로 논문의 주장과 연결한다.**  
이 Figure가 단순 correlation인지, mechanism을 직접 지지하는 실험인지 구분한다.
                """,
                """
**1. Start with an overview or schematic if available.**  
Identify the groups, treatment sequence, and sample type.

**2. Inspect observation panels such as gating, microscopy, or UMAP.**  
Determine what was measured and how.

**3. Check the quantification panel.**  
Ask whether the visual difference is also supported numerically.

**4. Identify the comparison groups.**  
For example: WT vs KO, control vs treatment, patient vs healthy.

**5. Connect the Figure back to the paper's claim.**  
Distinguish simple correlation from experiments that directly support a mechanism.
                """
            ))

        with st.expander(
            L(lang,"📄 원문 Figure caption 전체","📄 Full original Figure caption")
        ):
            st.write(item["caption"])

        with st.expander(
            "🔗 Source / License"
        ):
            st.write(f"**PMCID:** {pmcid}")

            if item["doi"]:
                st.write(f"**DOI:** {item['doi']}")

            st.write(f"**License:** {license_code}")

            if lic.get("copyright_statement"):
                st.write(
                    "**Copyright:**",
                    lic["copyright_statement"]
                )

            if rights["evidence"]:
                st.write(
                    "**Rights flag:**",
                    rights["evidence"]
                )

            if license_code in LICENSE_URLS:
                st.link_button(
                    "License",
                    LICENSE_URLS[license_code],
                    use_container_width=True
                )

            if item["doi"]:
                st.link_button(
                    "Original article",
                    f"https://doi.org/{item['doi']}",
                    use_container_width=True
                )

st.divider()

st.caption(L(lang,
    "Panel parsing과 해석은 규칙 기반 beta 기능입니다. Panel label이 잘못 분리될 수 있으며 Figure-level method tag가 모든 panel에 해당 method가 사용되었다는 뜻은 아닙니다.",
    "Panel parsing and interpretation are rule-based beta features. Panel labels can occasionally be split incorrectly, and a Figure-level method tag does not imply that every panel uses that method."
))
