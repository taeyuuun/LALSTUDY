import json
import zipfile
import io
import requests
import streamlit as st
from pathlib import Path

DATA_FILE = Path("method_profiles.json")
IMAGE_INDEX_FILE = Path("figure_images.json")
CACHE_DIR = Path("figure_cache")
CACHE_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Experimental Method Explorer",
    page_icon="🧬",
    layout="wide"
)

@st.cache_data
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

profiles = load_json(DATA_FILE)
image_index = load_json(IMAGE_INDEX_FILE) if IMAGE_INDEX_FILE.exists() else {}

profiles_by_name = {p["name"]: p for p in profiles}

# ============================================================
# FIGURE CACHE HELPERS
# ============================================================

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp"
}

def paper_cache_dir(pmcid):
    folder = CACHE_DIR / pmcid
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def download_inline_images(pmcid):
    """
    Europe PMC supplementaryFiles endpoint:
    OA content에서는 inline images가 기본 포함됨.
    논문당 최초 1회만 ZIP을 받아 캐시에 이미지들을 저장.
    """
    folder = paper_cache_dir(pmcid)
    marker = folder / "_download_complete.txt"

    if marker.exists():
        return True, "cached"

    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/"
        f"{pmcid}/supplementaryFiles"
    )

    try:
        r = requests.get(url, timeout=90)
        r.raise_for_status()

        # ZIP인지 확인
        if not zipfile.is_zipfile(io.BytesIO(r.content)):
            return False, (
                f"Europe PMC 응답이 ZIP이 아닙니다. "
                f"status={r.status_code}, content-type={r.headers.get('content-type')}"
            )

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            image_count = 0

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

        marker.write_text(
            f"{image_count} images",
            encoding="utf-8"
        )

        return True, f"{image_count} images cached"

    except Exception as e:
        return False, str(e)

def find_cached_image(pmcid, href):
    """
    XML의 xlink:href와 ZIP 안 이미지 파일명을 최대한 유연하게 매칭.
    """
    if not href:
        return None

    folder = paper_cache_dir(pmcid)

    if not folder.exists():
        return None

    href_name = Path(href).name
    href_stem = Path(href_name).stem.lower()
    href_name_lower = href_name.lower()

    candidates = []

    for p in folder.iterdir():
        if not p.is_file():
            continue

        if p.name.startswith("_"):
            continue

        if p.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        candidates.append(p)

    # 1. 파일명 정확 일치
    for p in candidates:
        if p.name.lower() == href_name_lower:
            return p

    # 2. stem 정확 일치 (확장자 차이 허용)
    for p in candidates:
        if p.stem.lower() == href_stem:
            return p

    # 3. stem 포함 관계 fallback
    for p in candidates:
        p_stem = p.stem.lower()

        if href_stem in p_stem or p_stem in href_stem:
            return p

    return None

# ============================================================
# HEADER
# ============================================================

st.title("🧬 Experimental Method Explorer")
st.caption(
    "Nature Communications OA immunology corpus — beta"
)

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("Search")

selected_method = st.sidebar.selectbox(
    "Method",
    sorted(profiles_by_name.keys())
)

keyword = st.sidebar.text_input(
    "Keyword",
    placeholder="Foxp3, T cell, IL-6, tumor ..."
).strip()

search_scope = st.sidebar.radio(
    "Keyword 검색 범위",
    [
        "논문 제목 + Figure caption",
        "Figure caption만",
        "논문 제목만"
    ]
)

show_only_figures = st.sidebar.checkbox(
    "Figure가 연결된 논문만 보기",
    value=False
)

max_results = st.sidebar.slider(
    "최대 표시 논문 수",
    10, 200, 30, 10
)

# ============================================================
# PROFILE
# ============================================================

profile = profiles_by_name[selected_method]

st.header(profile["name"])

c1, c2, c3, c4 = st.columns(4)

c1.metric("Papers", profile.get("paper_count", 0))
c2.metric("Figures", profile.get("figure_count", 0))
c3.metric("Category", profile.get("category") or "-")
c4.metric("Submethods", len(profile.get("submethods", [])))

if profile.get("parent_method"):
    st.write("**Parent method:**", profile["parent_method"])

left, right = st.columns(2)

with left:
    st.subheader("Aliases")
    st.write(", ".join(profile.get("aliases", [])) or "-")

with right:
    st.subheader("Submethods")
    st.write(", ".join(profile.get("submethods", [])) or "-")

# ============================================================
# CO METHODS
# ============================================================

st.divider()
st.subheader("🔗 Frequently co-used methods")

co_methods = profile.get("frequently_co_used_methods", [])

if co_methods:
    cols = st.columns(min(5, len(co_methods)))

    for i, item in enumerate(co_methods[:5]):
        with cols[i]:
            st.metric(
                item["method"],
                f'{item["paper_count"]} papers'
            )

# ============================================================
# FILTER
# ============================================================

papers = profile.get("papers", [])
keyword_lower = keyword.lower()
filtered_papers = []

for paper in papers:
    title = str(paper.get("title", ""))
    figures = paper.get("figures", [])

    title_match = keyword_lower in title.lower() if keyword_lower else True

    matching_figures = []

    for fig in figures:
        caption = str(fig.get("caption", ""))

        if not keyword_lower or keyword_lower in caption.lower():
            matching_figures.append(fig)

    if not keyword_lower:
        include = True
    elif search_scope == "논문 제목 + Figure caption":
        include = title_match or bool(matching_figures)
    elif search_scope == "Figure caption만":
        include = bool(matching_figures)
    else:
        include = title_match

    if show_only_figures and not figures:
        include = False

    if include:
        filtered_papers.append({
            **paper,
            "_matching_figures": matching_figures
        })

# ============================================================
# RESULTS
# ============================================================

st.divider()
st.subheader("📚 Papers")

st.write(
    f'검색 결과: **{len(filtered_papers)}편**'
    if keyword
    else f'전체 관련 논문: **{len(filtered_papers)}편**'
)

for paper in filtered_papers[:max_results]:

    title = paper.get("title", "Untitled")
    year = paper.get("year", "")
    doi = paper.get("doi", "")
    pmcid = paper.get("pmcid", "")

    all_figures = paper.get("figures", [])
    matching_figures = paper.get("_matching_figures", [])

    with st.expander(f"{title} ({year})"):

        meta1, meta2 = st.columns(2)
        meta1.write(f"**PMCID:** {pmcid}")
        meta2.write(f"**DOI:** {doi}")

        if doi:
            st.link_button(
                "DOI 열기",
                f"https://doi.org/{doi}"
            )

        if pmcid:
            st.link_button(
                "Europe PMC 열기",
                f"https://europepmc.org/articles/{pmcid}"
            )

        # 논문 단위 이미지 캐시 버튼
        if pmcid:
            cache_folder = paper_cache_dir(pmcid)
            cached_marker = cache_folder / "_download_complete.txt"

            if not cached_marker.exists():
                if st.button(
                    "📥 이 논문의 Figure 이미지 불러오기",
                    key=f"load_{pmcid}"
                ):
                    with st.spinner(
                        "Europe PMC에서 Figure 파일 받는 중..."
                    ):
                        ok, message = download_inline_images(pmcid)

                    if ok:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            else:
                st.caption(
                    "Figure 이미지가 로컬 캐시에 저장되어 있습니다."
                )

        if keyword and search_scope != "논문 제목만":
            figures_to_show = matching_figures
        else:
            figures_to_show = all_figures

        if not figures_to_show:
            st.info(
                "현재 이 method와 직접 연결된 Figure caption이 없습니다."
            )
            continue

        for fig in figures_to_show:

            fig_name = fig.get("figure", "Figure")
            caption = fig.get("caption", "")

            st.markdown(f"### {fig_name}")

            # XML에서 얻은 graphic href
            href = (
                image_index
                .get(pmcid, {})
                .get(fig_name, {})
                .get("href", "")
            )

            local_image = find_cached_image(
                pmcid,
                href
            )

            if local_image:
                st.image(
                    str(local_image),
                    caption=f"{fig_name} — PMC OA figure",
                    use_container_width=True
                )
            else:
                if (paper_cache_dir(pmcid) / "_download_complete.txt").exists():
                    st.warning(
                        f"캐시에는 이미지를 받았지만 "
                        f"{fig_name}의 XML 파일명({href or '없음'})과 "
                        f"매칭되는 파일을 찾지 못했습니다."
                    )
                else:
                    st.caption(
                        "위의 'Figure 이미지 불러오기' 버튼을 누르면 "
                        "실제 이미지를 표시합니다."
                    )

            if keyword and keyword_lower in caption.lower():
                pos = caption.lower().find(keyword_lower)
                start = max(0, pos - 250)
                end = min(
                    len(caption),
                    pos + len(keyword) + 450
                )
                st.info(caption[start:end])
            else:
                st.write(caption)

            st.markdown("---")

st.caption(
    "Beta — Figure images are fetched from Europe PMC OA supplementaryFiles "
    "and cached locally on demand."
)
