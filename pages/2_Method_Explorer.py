import io
import json
import zipfile
from pathlib import Path

import requests
import streamlit as st

from ai_provider import (
    get_openai_api_key,
    openai_ready,
)
from ai_router import (
    generate_method_encyclopedia_entry,
)
from i18n import language_selector, L
from knowledge_archive import get_supabase_credentials
from knowledge_widget import render_knowledge_archive_widget
from method_wiki import (
    FACET_DEFINITIONS,
    MethodWikiStore,
    facet_label,
    facet_title,
    infer_facets,
    normalize_method_name,
)
from openai_sidebar import render_openai_usage_panel


APP_VERSION = "v0.5.0-beta"

DATA_FILE = Path("method_profiles.json")
IMAGE_INDEX_FILE = Path("figure_images.json")
CACHE_DIR = Path("figure_cache")
CACHE_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="LALSTUDY Method Wiki",
    page_icon="🧬",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


profiles = load_json(DATA_FILE)
image_index = (
    load_json(IMAGE_INDEX_FILE)
    if IMAGE_INDEX_FILE.exists()
    else {}
)

profiles_by_name = {
    p["name"]: p
    for p in profiles
}

method_options = sorted(
    profiles_by_name.keys(),
    key=str.casefold,
)


# ============================================================
# Supabase Method Wiki
# ============================================================

@st.cache_resource(show_spinner=False)
def get_method_wiki_store(
    url,
    secret_key,
):
    if not url or not secret_key:
        return None

    try:
        return MethodWikiStore(
            url,
            secret_key,
        )
    except Exception:
        return None


supabase_url, supabase_secret = (
    get_supabase_credentials(
        st.secrets
    )
)

method_wiki_store = (
    get_method_wiki_store(
        supabase_url,
        supabase_secret,
    )
)

method_wiki_ready = False

if method_wiki_store is not None:
    try:
        method_wiki_ready = (
            method_wiki_store.ping()
        )
    except Exception as exc:
        st.session_state[
            "lal_method_wiki_error"
        ] = str(exc)


method_db_index = {}

if method_wiki_ready:
    try:
        method_db_index = {
            row.get("normalized_name", ""): row
            for row in method_wiki_store.list_entries()
            if row.get("normalized_name")
        }
    except Exception:
        method_db_index = {}


def facets_for_method(method_name):
    profile = profiles_by_name[
        method_name
    ]

    db_meta = method_db_index.get(
        normalize_method_name(
            method_name
        )
    )

    return merged_facets(
        profile,
        db_meta,
    )


# ============================================================
# Existing Figure cache helpers
# ============================================================

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
}


def paper_cache_dir(pmcid):
    folder = CACHE_DIR / pmcid
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )
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
        r = requests.get(
            url,
            timeout=90,
        )
        r.raise_for_status()

        if not zipfile.is_zipfile(
            io.BytesIO(r.content)
        ):
            return False, (
                "Europe PMC response is not a ZIP. "
                f"status={r.status_code}, "
                f"content-type={r.headers.get('content-type')}"
            )

        with zipfile.ZipFile(
            io.BytesIO(r.content)
        ) as z:
            image_count = 0

            for member in z.infolist():
                if member.is_dir():
                    continue

                name = Path(
                    member.filename
                ).name

                suffix = Path(
                    name
                ).suffix.lower()

                if suffix not in IMAGE_EXTENSIONS:
                    continue

                target = folder / name

                with z.open(member) as src, open(
                    target,
                    "wb",
                ) as dst:
                    dst.write(
                        src.read()
                    )

                image_count += 1

        marker.write_text(
            f"{image_count} images",
            encoding="utf-8",
        )

        return True, (
            f"{image_count} images cached"
        )

    except Exception as exc:
        return False, str(exc)


def find_cached_image(
    pmcid,
    href,
):
    if not href:
        return None

    folder = paper_cache_dir(
        pmcid
    )

    if not folder.exists():
        return None

    href_name = Path(
        href
    ).name

    href_stem = Path(
        href_name
    ).stem.lower()

    href_name_lower = (
        href_name.lower()
    )

    candidates = [
        p
        for p in folder.iterdir()
        if (
            p.is_file()
            and not p.name.startswith("_")
            and p.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    ]

    for p in candidates:
        if (
            p.name.lower()
            == href_name_lower
        ):
            return p

    for p in candidates:
        if (
            p.stem.lower()
            == href_stem
        ):
            return p

    for p in candidates:
        p_stem = p.stem.lower()

        if (
            href_stem in p_stem
            or p_stem in href_stem
        ):
            return p

    return None


# ============================================================
# Search / taxonomy helpers
# ============================================================

def profile_search_blob(profile):
    return " ".join(
        [
            profile.get(
                "name",
                "",
            ),
            " ".join(
                profile.get(
                    "aliases",
                    [],
                )
                or []
            ),
            profile.get(
                "category",
                "",
            )
            or "",
            profile.get(
                "parent_method",
                "",
            )
            or "",
        ]
    ).casefold()


def rank_method_matches(query):
    query = normalize_method_name(
        query
    )

    if not query:
        return []

    scored = []

    for name in method_options:
        profile = profiles_by_name[
            name
        ]

        norm_name = normalize_method_name(
            name
        )

        aliases = [
            normalize_method_name(
                alias
            )
            for alias in (
                profile.get(
                    "aliases",
                    [],
                )
                or []
            )
        ]

        blob = profile_search_blob(
            profile
        )

        score = None

        if norm_name == query:
            score = 0
        elif query in aliases:
            score = 1
        elif norm_name.startswith(
            query
        ):
            score = 2
        elif any(
            alias.startswith(query)
            for alias in aliases
        ):
            score = 3
        elif query in norm_name:
            score = 4
        elif query in blob:
            score = 5

        if score is not None:
            scored.append(
                (
                    score,
                    name.casefold(),
                    name,
                )
            )

    scored.sort()

    return [
        name
        for _score, _sort, name
        in scored
    ]


def merged_facets(
    profile,
    db_entry=None,
):
    local = infer_facets(
        profile
    )

    if not db_entry:
        return local

    db_facets = (
        db_entry.get(
            "facets",
            {},
        )
        or {}
    )

    output = {}

    for facet in (
        "purpose",
        "material",
        "principle",
        "output",
    ):
        values = db_facets.get(
            facet
        )

        output[facet] = (
            values
            if isinstance(
                values,
                list,
            )
            and values
            else local.get(
                facet,
                [],
            )
        )

    return output


def method_button(
    method_name,
    key,
    *,
    profile=None,
):
    profile = (
        profile
        or profiles_by_name[
            method_name
        ]
    )

    papers = int(
        profile.get(
            "paper_count",
            0,
        )
        or 0
    )

    label = (
        f"{method_name}  ·  "
        f"{papers} papers"
    )

    if st.button(
        label,
        key=key,
        use_container_width=True,
    ):
        st.session_state[
            "lal_method_wiki_selected"
        ] = method_name

        st.rerun()


# ============================================================
# Global sidebar
# ============================================================

lang = language_selector()

render_openai_usage_panel(
    lang=lang
)

render_knowledge_archive_widget(
    lang=lang
)

st.sidebar.caption(
    f"Method Wiki · {APP_VERSION}"
)

if method_wiki_ready:
    st.sidebar.caption(
        "🧬 Method DB · connected"
    )
else:
    st.sidebar.caption(
        "🧬 Method DB · migration needed"
    )


# Deep links from Learn a Paper / elsewhere remain compatible.
jump_method = st.session_state.pop(
    "lal_method_jump",
    None,
)

if (
    jump_method
    and jump_method
    in profiles_by_name
):
    st.session_state[
        "lal_method_wiki_selected"
    ] = jump_method


selected_method = (
    st.session_state.get(
        "lal_method_wiki_selected"
    )
)

if (
    selected_method
    not in profiles_by_name
):
    selected_method = None
    st.session_state.pop(
        "lal_method_wiki_selected",
        None,
    )


# ============================================================
# Wiki home
# ============================================================

if not selected_method:
    st.title(
        L(
            lang,
            "🧬 Method Wiki",
            "🧬 Method Wiki",
        )
    )

    st.caption(
        L(
            lang,
            "실험기법을 이름으로 검색하거나, 목적·대상·원리·결과 형태로 탐색하세요.",
            "Search an experimental method by name, or browse by purpose, material, principle, and output.",
        )
    )

    search_query = st.text_input(
        L(
            lang,
            "실험기법 검색",
            "Search methods",
        ),
        placeholder=L(
            lang,
            "예: Flow cytometry, qPCR, Western blotting, scRNA-seq",
            "e.g. Flow cytometry, qPCR, Western blotting, scRNA-seq",
        ),
        key="lal_method_wiki_search",
    ).strip()

    if search_query:
        matches = rank_method_matches(
            search_query
        )

        st.subheader(
            L(
                lang,
                "검색 결과",
                "Search results",
            )
        )

        if not matches:
            st.info(
                L(
                    lang,
                    "일치하는 실험기법을 찾지 못했습니다.",
                    "No matching experimental method was found.",
                )
            )
        else:
            for i, name in enumerate(
                matches[:20]
            ):
                method_button(
                    name,
                    key=(
                        "method_search_result_"
                        + str(i)
                        + "_"
                        + normalize_method_name(
                            name
                        )
                    ),
                )

    st.divider()

    st.subheader(
        L(
            lang,
            "카테고리로 찾아보기",
            "Browse by category",
        )
    )

    st.caption(
        L(
            lang,
            "여러 조건을 동시에 고를 수 있습니다. 같은 항목 안에서는 OR, 서로 다른 항목 사이는 AND로 검색합니다. 예: 목적=세포 증식·생존 + 대상=단백질/세포.",
            "Combine multiple filters. Values inside one facet use OR; different facets use AND. Example: purpose=proliferation/viability + material=protein/cell.",
        )
    )

    facet_order = [
        "purpose",
        "material",
        "principle",
        "output",
    ]

    # Count current methods per facet value.
    facet_counts = {
        facet: {}
        for facet in facet_order
    }

    method_facets_cache = {}

    for method_name in method_options:
        method_facets_cache[
            method_name
        ] = facets_for_method(
            method_name
        )

        for facet in facet_order:
            for value in method_facets_cache[
                method_name
            ].get(
                facet,
                [],
            ):
                facet_counts[
                    facet
                ][value] = (
                    facet_counts[
                        facet
                    ].get(
                        value,
                        0,
                    )
                    + 1
                )

    facet_cols = st.columns(2)
    selected_facets = {}

    for idx, facet in enumerate(
        facet_order
    ):
        values = (
            FACET_DEFINITIONS[
                facet
            ]["values"]
        )

        available = [
            key
            for key in values
            if facet_counts[
                facet
            ].get(
                key,
                0,
            )
            > 0
        ]

        with facet_cols[
            idx % 2
        ]:
            selected_facets[
                facet
            ] = st.multiselect(
                facet_title(
                    facet,
                    lang,
                ),
                available,
                format_func=lambda x, f=facet: (
                    f"{facet_label(f, x, lang)} "
                    f"({facet_counts[f].get(x, 0)})"
                ),
                key=(
                    "lal_method_facet_multi_"
                    + facet
                ),
                placeholder=L(
                    lang,
                    "전체",
                    "All",
                ),
            )

    has_facet_filter = any(
        selected_facets[
            facet
        ]
        for facet in facet_order
    )

    if has_facet_filter:
        matching_methods = []

        for method_name in method_options:
            facets = method_facets_cache[
                method_name
            ]

            include = True

            for facet in facet_order:
                selected_values = (
                    selected_facets[
                        facet
                    ]
                )

                if not selected_values:
                    continue

                method_values = set(
                    facets.get(
                        facet,
                        [],
                    )
                )

                # OR inside a facet.
                if not (
                    method_values
                    & set(
                        selected_values
                    )
                ):
                    include = False
                    break

            if include:
                matching_methods.append(
                    method_name
                )

        st.markdown(
            L(
                lang,
                f"**{len(matching_methods)}개 method**",
                f"**{len(matching_methods)} methods**",
            )
        )

        if not matching_methods:
            st.info(
                L(
                    lang,
                    "이 조건 조합에 해당하는 method가 없습니다.",
                    "No methods match this combination of filters.",
                )
            )
        else:
            for i, method_name in enumerate(
                matching_methods
            ):
                method_button(
                    method_name,
                    key=(
                        "facet_combo_method_"
                        + str(i)
                        + "_"
                        + normalize_method_name(
                            method_name
                        )
                    ),
                )

    else:
        st.caption(
            L(
                lang,
                "필터를 하나 이상 선택하면 해당 method 목록이 나타납니다.",
                "Choose at least one filter to see matching methods.",
            )
        )

    st.divider()

    st.caption(
        L(
            lang,
            f"현재 corpus에서 {len(method_options)}개 method를 탐색할 수 있습니다. 논문·Figure 연결 정보는 기존 corpus를 그대로 사용합니다.",
            f"{len(method_options)} methods are currently browsable. Paper/Figure links continue to use the existing corpus data.",
        )
    )

    st.stop()


# ============================================================
# Individual Method article
# ============================================================

profile = profiles_by_name[
    selected_method
]

if st.button(
    L(
        lang,
        "← Method Wiki 홈",
        "← Method Wiki home",
    ),
    key="lal_method_wiki_home",
):
    st.session_state.pop(
        "lal_method_wiki_selected",
        None,
    )
    st.rerun()


db_entry = None

if method_wiki_ready:
    try:
        db_entry = (
            method_wiki_store.get(
                selected_method
            )
        )
    except Exception as exc:
        st.session_state[
            "lal_method_wiki_error"
        ] = str(exc)


facets = (
    merged_facets(
        profile,
        db_entry,
    )
    if db_entry
    else facets_for_method(
        selected_method
    )
)


st.title(selected_method)

alias_text = ", ".join(
    profile.get(
        "aliases",
        [],
    )
    or []
)

if alias_text:
    st.caption(
        L(
            lang,
            f"Aliases · {alias_text}",
            f"Aliases · {alias_text}",
        )
    )


# Facet chips
chip_parts = []

for facet in (
    "purpose",
    "material",
    "principle",
    "output",
):
    for key in facets.get(
        facet,
        [],
    )[:3]:
        chip_parts.append(
            facet_label(
                facet,
                key,
                lang,
            )
        )

if chip_parts:
    st.caption(
        " · ".join(
            chip_parts
        )
    )


# ============================================================
# Encyclopedia description
# ============================================================

st.subheader(
    L(
        lang,
        "개요",
        "Overview",
    )
)

if db_entry:
    suffix = (
        "_ko"
        if lang == "ko"
        else "_en"
    )

    summary = db_entry.get(
        "summary" + suffix,
        "",
    )

    principle = db_entry.get(
        "principle" + suffix,
        "",
    )

    best_for = db_entry.get(
        "best_for" + suffix,
        "",
    )

    limitations = db_entry.get(
        "limitations" + suffix,
        "",
    )

    st.write(
        summary
        or "-"
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown(
            L(
                lang,
                "#### ⚙️ 핵심 원리",
                "#### ⚙️ Core principle",
            )
        )
        st.write(
            principle
            or "-"
        )

        st.markdown(
            L(
                lang,
                "#### 🎯 언제 쓰나",
                "#### 🎯 When to use it",
            )
        )
        st.write(
            best_for
            or "-"
        )

    with c2:
        st.markdown(
            L(
                lang,
                "#### ⚠️ 해석할 때 주의",
                "#### ⚠️ Interpretation caveats",
            )
        )
        st.write(
            limitations
            or "-"
        )

        quality = db_entry.get(
            "quality_status",
            "AI_GENERATED",
        )

        source_model = db_entry.get(
            "source_model",
            "",
        )

        st.caption(
            (
                f"Method DB · {quality}"
                + (
                    f" · {source_model}"
                    if source_model
                    else ""
                )
            )
        )

else:
    st.info(
        L(
            lang,
            "이 method의 encyclopedia 설명은 아직 DB에 없습니다. 아래 버튼으로 한 번 생성하면 이후 모든 사용자가 같은 설명을 재사용합니다.",
            "This method does not yet have an encyclopedia entry in the DB. Generate it once and future users will reuse the same entry.",
        )
    )

    if not method_wiki_ready:
        st.warning(
            L(
                lang,
                "`SUPABASE_METHOD_WIKI_MIGRATION.sql`을 먼저 실행해야 설명을 DB에 저장할 수 있습니다.",
                "Run `SUPABASE_METHOD_WIKI_MIGRATION.sql` before method descriptions can be stored.",
            )
        )

    can_generate = (
        method_wiki_ready
        and openai_ready()
    )

    if st.button(
        L(
            lang,
            "✨ 설명 생성하고 DB에 저장",
            "✨ Generate description and save to DB",
        ),
        type="primary",
        disabled=not can_generate,
        key=(
            "generate_method_wiki_"
            + normalize_method_name(
                selected_method
            )
        ),
    ):
        with st.spinner(
            L(
                lang,
                "재사용 가능한 method 설명 생성 중...",
                "Generating a reusable method entry...",
            )
        ):
            try:
                result, model, usage = (
                    generate_method_encyclopedia_entry(
                        canonical_name=selected_method,
                        aliases=(
                            profile.get(
                                "aliases",
                                [],
                            )
                            or []
                        ),
                        category=(
                            profile.get(
                                "category",
                                "",
                            )
                            or ""
                        ),
                        parent_method=(
                            profile.get(
                                "parent_method",
                                "",
                            )
                            or ""
                        ),
                        submethods=(
                            profile.get(
                                "submethods",
                                [],
                            )
                            or []
                        ),
                        api_key=(
                            get_openai_api_key()
                        ),
                    )
                )

                payload = (
                    result.model_dump()
                )

                payload.update(
                    {
                        "canonical_name": (
                            selected_method
                        ),
                        "facets": facets,
                        "quality_status": (
                            "AI_GENERATED"
                        ),
                        "source_model": (
                            model
                        ),
                    }
                )

                method_wiki_store.upsert(
                    payload
                )

                st.success(
                    L(
                        lang,
                        "Method DB에 저장했습니다.",
                        "Saved to the Method DB.",
                    )
                )

                st.rerun()

            except Exception as exc:
                st.error(
                    str(exc)
                )


# ============================================================
# Compact existing corpus metadata
# ============================================================

st.divider()

meta1, meta2, meta3 = st.columns(3)

with meta1:
    st.caption(
        L(
            lang,
            "Corpus 논문",
            "Corpus papers",
        )
    )
    st.markdown(
        f"**{profile.get('paper_count', 0)}**"
    )

with meta2:
    st.caption(
        L(
            lang,
            "연결 Figure",
            "Linked Figures",
        )
    )
    st.markdown(
        f"**{profile.get('figure_count', 0)}**"
    )

with meta3:
    st.caption(
        L(
            lang,
            "기존 ontology",
            "Existing ontology",
        )
    )
    st.markdown(
        f"**{profile.get('category') or '-'}**"
    )


parent = profile.get(
    "parent_method"
)

submethods = (
    profile.get(
        "submethods",
        [],
    )
    or []
)

if parent or submethods:
    with st.expander(
        L(
            lang,
            "Method 관계",
            "Method relationships",
        )
    ):
        if parent:
            st.write(
                "**Parent:**",
                parent,
            )

        if submethods:
            st.write(
                "**Submethods:**",
                ", ".join(
                    submethods
                ),
            )


# ============================================================
# Frequently co-used methods
# ============================================================

co_methods = (
    profile.get(
        "frequently_co_used_methods",
        [],
    )
    or []
)

if co_methods:
    st.subheader(
        L(
            lang,
            "함께 자주 사용되는 실험기법",
            "Frequently co-used methods",
        )
    )

    cols = st.columns(
        min(
            4,
            len(co_methods),
        )
    )

    for i, item in enumerate(
        co_methods[:4]
    ):
        with cols[i]:
            co_name = item.get(
                "method",
                "",
            )

            count = item.get(
                "paper_count",
                0,
            )

            if st.button(
                f"{co_name}\n\n{count} papers",
                key=(
                    "co_method_"
                    + str(i)
                    + "_"
                    + normalize_method_name(
                        co_name
                    )
                ),
                use_container_width=True,
            ):
                if (
                    co_name
                    in profiles_by_name
                ):
                    st.session_state[
                        "lal_method_wiki_selected"
                    ] = co_name

                    st.rerun()


# ============================================================
# Existing paper / Figure corpus view
# ============================================================

st.divider()

st.subheader(
    L(
        lang,
        "📚 이 실험이 쓰인 논문",
        "📚 Papers using this method",
    )
)

st.caption(
    L(
        lang,
        "이 영역은 기존 corpus 연결 정보를 그대로 사용합니다. Method 설명 DB와 논문/Figure corpus는 분리되어 있습니다.",
        "This section uses the existing corpus links. The method-description DB and the paper/Figure corpus remain separate.",
    )
)

filter_col1, filter_col2 = st.columns(
    [2, 1]
)

with filter_col1:
    keyword = st.text_input(
        L(
            lang,
            "논문 / Figure caption 검색",
            "Search papers / Figure captions",
        ),
        placeholder=L(
            lang,
            "예: Foxp3, T cell, IL-6, tumor",
            "e.g. Foxp3, T cell, IL-6, tumor",
        ),
        key=(
            "method_paper_keyword_"
            + normalize_method_name(
                selected_method
            )
        ),
    ).strip()

with filter_col2:
    search_scope = st.selectbox(
        L(
            lang,
            "검색 범위",
            "Search scope",
        ),
        [
            "both",
            "caption",
            "title",
        ],
        format_func=lambda x: {
            "both": L(
                lang,
                "제목 + Figure caption",
                "Title + Figure caption",
            ),
            "caption": L(
                lang,
                "Figure caption",
                "Figure caption",
            ),
            "title": L(
                lang,
                "논문 제목",
                "Paper title",
            ),
        }[x],
        key=(
            "method_paper_scope_"
            + normalize_method_name(
                selected_method
            )
        ),
    )

show_only_figures = st.checkbox(
    L(
        lang,
        "Figure가 연결된 논문만",
        "Only papers linked to Figures",
    ),
    value=False,
    key=(
        "method_papers_figures_only_"
        + normalize_method_name(
            selected_method
        )
    ),
)

max_results = st.slider(
    L(
        lang,
        "최대 표시 논문 수",
        "Maximum papers to display",
    ),
    10,
    200,
    30,
    10,
    key=(
        "method_paper_max_"
        + normalize_method_name(
            selected_method
        )
    ),
)


papers = profile.get(
    "papers",
    [],
)

keyword_lower = (
    keyword.casefold()
)

filtered_papers = []

for paper in papers:
    title = str(
        paper.get(
            "title",
            "",
        )
    )

    figures = (
        paper.get(
            "figures",
            [],
        )
        or []
    )

    title_match = (
        keyword_lower
        in title.casefold()
        if keyword_lower
        else True
    )

    matching_figures = []

    for fig in figures:
        caption = str(
            fig.get(
                "caption",
                "",
            )
        )

        if (
            not keyword_lower
            or keyword_lower
            in caption.casefold()
        ):
            matching_figures.append(
                fig
            )

    if not keyword_lower:
        include = True
    elif search_scope == "both":
        include = (
            title_match
            or bool(
                matching_figures
            )
        )
    elif search_scope == "caption":
        include = bool(
            matching_figures
        )
    else:
        include = title_match

    if (
        show_only_figures
        and not figures
    ):
        include = False

    if include:
        filtered_papers.append(
            {
                **paper,
                "_matching_figures": (
                    matching_figures
                ),
            }
        )


st.write(
    (
        f"검색 결과: **{len(filtered_papers)}편**"
        if keyword
        else f"관련 논문: **{len(filtered_papers)}편**"
    )
    if lang == "ko"
    else (
        f"Search results: **{len(filtered_papers)} papers**"
        if keyword
        else f"Related papers: **{len(filtered_papers)}**"
    )
)


for paper in filtered_papers[
    :max_results
]:
    title = paper.get(
        "title",
        "Untitled",
    )

    year = paper.get(
        "year",
        "",
    )

    doi = paper.get(
        "doi",
        "",
    )

    pmcid = paper.get(
        "pmcid",
        "",
    )

    all_figures = (
        paper.get(
            "figures",
            [],
        )
        or []
    )

    matching_figures = (
        paper.get(
            "_matching_figures",
            [],
        )
        or []
    )

    with st.expander(
        f"{title} ({year})"
    ):
        meta1, meta2 = (
            st.columns(2)
        )

        meta1.write(
            f"**PMCID:** {pmcid or '-'}"
        )

        meta2.write(
            f"**DOI:** {doi or '-'}"
        )

        link1, link2 = st.columns(2)

        with link1:
            if doi:
                st.link_button(
                    "DOI",
                    f"https://doi.org/{doi}",
                    use_container_width=True,
                )

        with link2:
            if pmcid:
                st.link_button(
                    "Europe PMC",
                    f"https://europepmc.org/articles/{pmcid}",
                    use_container_width=True,
                )

        if pmcid:
            cache_folder = (
                paper_cache_dir(
                    pmcid
                )
            )

            cached_marker = (
                cache_folder
                / "_download_complete.txt"
            )

            if not cached_marker.exists():
                if st.button(
                    L(
                        lang,
                        "📥 Figure 이미지 불러오기",
                        "📥 Load Figure images",
                    ),
                    key=(
                        f"load_{pmcid}_"
                        + normalize_method_name(
                            selected_method
                        )
                    ),
                ):
                    with st.spinner(
                        L(
                            lang,
                            "Europe PMC에서 Figure 파일 받는 중...",
                            "Fetching Figure files from Europe PMC...",
                        )
                    ):
                        ok, message = (
                            download_inline_images(
                                pmcid
                            )
                        )

                    if ok:
                        st.success(
                            message
                        )
                        st.rerun()
                    else:
                        st.error(
                            message
                        )
            else:
                st.caption(
                    L(
                        lang,
                        "Figure 이미지가 로컬 캐시에 있습니다.",
                        "Figure images are available in the local cache.",
                    )
                )

        figures_to_show = (
            matching_figures
            if (
                keyword
                and search_scope
                != "title"
            )
            else all_figures
        )

        if not figures_to_show:
            st.info(
                L(
                    lang,
                    "현재 이 method와 직접 연결된 Figure caption이 없습니다.",
                    "No Figure caption is directly linked to this method in the current data.",
                )
            )
            continue

        for fig in figures_to_show:
            fig_name = fig.get(
                "figure",
                "Figure",
            )

            caption = fig.get(
                "caption",
                "",
            )

            st.markdown(
                f"#### {fig_name}"
            )

            href = (
                image_index
                .get(
                    pmcid,
                    {},
                )
                .get(
                    fig_name,
                    {},
                )
                .get(
                    "href",
                    "",
                )
            )

            local_image = (
                find_cached_image(
                    pmcid,
                    href,
                )
            )

            if local_image:
                st.image(
                    str(
                        local_image
                    ),
                    caption=(
                        f"{fig_name} — "
                        "PMC OA figure"
                    ),
                    use_container_width=False,
                )

            elif (
                paper_cache_dir(
                    pmcid
                )
                / "_download_complete.txt"
            ).exists():
                st.warning(
                    L(
                        lang,
                        f"이미지는 받았지만 {fig_name}의 XML 파일명과 매칭하지 못했습니다.",
                        f"Images were downloaded, but no cached file matched {fig_name}.",
                    )
                )

            else:
                st.caption(
                    L(
                        lang,
                        "위 버튼으로 실제 Figure 이미지를 불러올 수 있습니다.",
                        "Use the button above to load the actual Figure images.",
                    )
                )

            if (
                keyword
                and keyword_lower
                in caption.casefold()
            ):
                pos = (
                    caption.casefold()
                    .find(
                        keyword_lower
                    )
                )

                start = max(
                    0,
                    pos - 250,
                )

                end = min(
                    len(caption),
                    pos
                    + len(keyword)
                    + 450,
                )

                st.info(
                    caption[
                        start:end
                    ]
                )
            else:
                st.write(
                    caption
                )


st.caption(
    L(
        lang,
        "Method 설명은 Supabase Method DB에, 논문·Figure 연결은 기존 Nature Communications OA corpus에 저장됩니다.",
        "Method explanations live in the Supabase Method DB; paper/Figure links remain in the existing Nature Communications OA corpus.",
    )
)
