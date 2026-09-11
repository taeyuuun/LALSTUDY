import base64
import html
import io
import json
import re
import zipfile
from pathlib import Path

import requests
import streamlit as st

from ai_provider import (
    get_openai_api_key,
    openai_ready,
)
from method_wiki_ai_v2 import (
    build_method_db_payload,
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


APP_VERSION = "v0.5.1.1-beta"

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
# Readability-first Method article helpers
# ============================================================

st.markdown(
    """
    <style>
    .mw-kicker {
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
        opacity: .58;
        margin-bottom: .35rem;
    }

    .mw-hero {
        border: 1px solid rgba(49, 51, 63, .14);
        border-radius: 18px;
        padding: 1.15rem 1.25rem;
        background: rgba(248, 249, 251, .82);
        margin: .2rem 0 .85rem 0;
    }

    .mw-question {
        font-size: 1.22rem;
        line-height: 1.45;
        font-weight: 700;
        margin: .15rem 0 .8rem 0;
    }

    .mw-summary {
        font-size: 1.03rem;
        line-height: 1.75;
        margin: 0;
    }

    .mw-card {
        border: 1px solid rgba(49, 51, 63, .13);
        border-radius: 16px;
        padding: 1rem 1.05rem .9rem 1.05rem;
        height: 100%;
        background: rgba(255,255,255,.78);
    }

    .mw-card-title {
        font-size: 1rem;
        font-weight: 800;
        margin-bottom: .6rem;
    }

    .mw-card ul {
        margin: .2rem 0 0 1.1rem;
        padding: 0;
    }

    .mw-card li {
        line-height: 1.58;
        margin-bottom: .45rem;
    }

    .mw-tip {
        border-left: 4px solid #ffb000;
        border-radius: 8px;
        padding: .8rem 1rem;
        background: rgba(255, 246, 218, .72);
        line-height: 1.6;
        margin: .8rem 0 1rem 0;
    }

    .mw-meta {
        border: 1px solid rgba(49, 51, 63, .10);
        border-radius: 14px;
        padding: .75rem .9rem;
        background: rgba(248,249,251,.70);
    }

    .mw-meta-label {
        font-size: .75rem;
        opacity: .62;
        margin-bottom: .15rem;
    }

    .mw-meta-value {
        font-size: .92rem;
        font-weight: 700;
        line-height: 1.35;
    }

    .mw-visual-caption {
        font-size: .76rem;
        opacity: .64;
        line-height: 1.4;
        margin-top: .3rem;
    }

    div[data-testid="stVerticalBlock"] > div:has(.mw-card) {
        height: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def sentence_points(text, max_points=4):
    """
    Backward-compatible readability fallback for old DB rows.
    Turns a long paragraph into short bullets without changing its meaning.
    """
    text = (text or "").strip()

    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?。])\s+|;\s+",
        text,
    )

    points = [
        part.strip()
        for part in parts
        if part.strip()
    ]

    if len(points) <= 1 and len(text) > 90:
        # Conservative clause split for legacy Korean/English mixed prose.
        points = [
            part.strip()
            for part in re.split(
                r",\s+(?=[A-Za-z가-힣])",
                text,
            )
            if part.strip()
        ]

    return points[:max_points]


def render_bullet_card(
    title,
    icon,
    points,
):
    safe_points = [
        html.escape(str(point))
        for point in points
        if str(point).strip()
    ]

    if not safe_points:
        safe_points = ["-"]

    bullets = "".join(
        f"<li>{point}</li>"
        for point in safe_points
    )

    st.markdown(
        f"""
        <div class="mw-card">
          <div class="mw-card-title">{icon} {html.escape(title)}</div>
          <ul>{bullets}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def method_visual_svg(
    *,
    method_name,
    facets,
    lang,
):
    """
    Lightweight infographic-style visual generated locally.
    No image API, no cloud storage, no copyright dependency.
    """

    purpose = [
        facet_label(
            "purpose",
            key,
            lang,
        )
        for key in facets.get(
            "purpose",
            [],
        )[:2]
    ]

    material = [
        facet_label(
            "material",
            key,
            lang,
        )
        for key in facets.get(
            "material",
            [],
        )[:2]
    ]

    principle = [
        facet_label(
            "principle",
            key,
            lang,
        )
        for key in facets.get(
            "principle",
            [],
        )[:2]
    ]

    output = [
        facet_label(
            "output",
            key,
            lang,
        )
        for key in facets.get(
            "output",
            [],
        )[:2]
    ]

    def text_value(values, fallback):
        return " · ".join(values) if values else fallback

    title = html.escape(
        method_name
    )

    p1 = html.escape(
        text_value(
            material,
            "Sample",
        )
    )

    p2 = html.escape(
        text_value(
            principle,
            "Measurement",
        )
    )

    p3 = html.escape(
        text_value(
            output,
            "Readout",
        )
    )

    purpose_text = html.escape(
        text_value(
            purpose,
            "Experimental question",
        )
    )

    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="720" height="430"
         viewBox="0 0 720 430">
      <rect width="720" height="430" rx="28" fill="#f7f9fc"/>
      <rect x="34" y="32" width="652" height="366" rx="22"
            fill="#ffffff" stroke="#dfe5ec"/>

      <text x="62" y="78" font-family="Arial, sans-serif"
            font-size="18" font-weight="700" fill="#172033">{title}</text>
      <text x="62" y="107" font-family="Arial, sans-serif"
            font-size="14" fill="#657083">{purpose_text}</text>

      <circle cx="132" cy="225" r="62" fill="#e8f2ff" stroke="#9fc3f4" stroke-width="2"/>
      <circle cx="360" cy="225" r="62" fill="#edf8ef" stroke="#a9d7b1" stroke-width="2"/>
      <circle cx="588" cy="225" r="62" fill="#fff4df" stroke="#edc97d" stroke-width="2"/>

      <path d="M200 225 L286 225" stroke="#8b97a8" stroke-width="5"
            stroke-linecap="round"/>
      <path d="M428 225 L514 225" stroke="#8b97a8" stroke-width="5"
            stroke-linecap="round"/>

      <polygon points="286,225 270,216 270,234" fill="#8b97a8"/>
      <polygon points="514,225 498,216 498,234" fill="#8b97a8"/>

      <text x="132" y="218" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="14"
            font-weight="700" fill="#253044">INPUT</text>
      <text x="132" y="242" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="13"
            fill="#455268">{p1}</text>

      <text x="360" y="218" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="14"
            font-weight="700" fill="#253044">PRINCIPLE</text>
      <text x="360" y="242" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="13"
            fill="#455268">{p2}</text>

      <text x="588" y="218" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="14"
            font-weight="700" fill="#253044">OUTPUT</text>
      <text x="588" y="242" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="13"
            fill="#455268">{p3}</text>

      <text x="62" y="352" font-family="Arial, sans-serif"
            font-size="12" fill="#8a94a3">LALSTUDY Method Map</text>
    </svg>
    """

    return svg.encode(
        "utf-8"
    )


def render_method_visual(
    visual_bytes,
):
    encoded = base64.b64encode(
        visual_bytes
    ).decode("ascii")

    st.markdown(
        f"""
        <img
          src="data:image/svg+xml;base64,{encoded}"
          alt="Method concept map"
          style="
            width:100%;
            display:block;
            border-radius:18px;
            margin:0;
          "
        />
        """,
        unsafe_allow_html=True,
    )


def representative_figure_candidate(
    profile,
):
    """
    Find a real corpus Figure linked to this method.
    Prefer a cached image. If none is cached, return one candidate that the
    user can load without storing anything in Supabase.
    """

    fallback = None

    for paper in (
        profile.get(
            "papers",
            [],
        )
        or []
    ):
        pmcid = paper.get(
            "pmcid",
            "",
        )

        figures = (
            paper.get(
                "figures",
                [],
            )
            or []
        )

        if not pmcid or not figures:
            continue

        for fig in figures:
            fig_name = fig.get(
                "figure",
                "Figure",
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

            candidate = {
                "paper": paper,
                "figure": fig,
                "pmcid": pmcid,
                "href": href,
            }

            local_image = (
                find_cached_image(
                    pmcid,
                    href,
                )
            )

            if local_image:
                candidate[
                    "local_image"
                ] = local_image

                return candidate

            if fallback is None:
                fallback = candidate

    return fallback


def structured_method_article(
    db_entry,
    lang,
):
    suffix = (
        "_ko"
        if lang == "ko"
        else "_en"
    )

    article = (
        db_entry.get(
            "article_json",
            {},
        )
        if db_entry
        else {}
    ) or {}

    def article_text(base, fallback=""):
        value = article.get(
            base + suffix
        )

        if value:
            return value

        return (
            db_entry.get(
                fallback + suffix,
                "",
            )
            if db_entry and fallback
            else ""
        )

    def article_list(base, fallback_field):
        value = article.get(
            base + suffix
        )

        if isinstance(
            value,
            list,
        ) and value:
            return value

        fallback = (
            db_entry.get(
                fallback_field + suffix,
                "",
            )
            if db_entry
            else ""
        )

        return sentence_points(
            fallback,
            max_points=4,
        )

    return {
        "key_question": article_text(
            "key_question",
        ),
        "one_liner": article_text(
            "one_liner",
            "summary",
        ),
        "principle_steps": article_list(
            "principle_steps",
            "principle",
        ),
        "best_for_points": article_list(
            "best_for_points",
            "best_for",
        ),
        "limitation_points": article_list(
            "limitation_points",
            "limitations",
        ),
        "interpretation_tip": article_text(
            "interpretation_tip",
        ),
    }


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
# Readability-first Method article
# ============================================================

if db_entry:
    article_data = (
        structured_method_article(
            db_entry,
            lang,
        )
    )

    hero_left, hero_right = st.columns(
        [1.55, 1],
        gap="large",
        vertical_alignment="top",
    )

    with hero_left:
        key_question = (
            article_data.get(
                "key_question",
                "",
            )
            or L(
                lang,
                "이 실험으로 무엇을 알 수 있을까?",
                "What can this method tell us?",
            )
        )

        one_liner = (
            article_data.get(
                "one_liner",
                "",
            )
            or "-"
        )

        st.markdown(
            f"""
            <div class="mw-hero">
              <div class="mw-kicker">{html.escape(L(lang, "한눈에 보기", "At a glance"))}</div>
              <div class="mw-question">{html.escape(key_question)}</div>
              <p class="mw-summary">{html.escape(one_liner)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Quick taxonomy, separated from prose.
        quick_cols = st.columns(2)

        quick_items = [
            (
                L(lang, "목적", "Purpose"),
                ", ".join(
                    facet_label(
                        "purpose",
                        key,
                        lang,
                    )
                    for key in facets.get(
                        "purpose",
                        [],
                    )[:3]
                )
                or "-",
            ),
            (
                L(lang, "대상", "Material"),
                ", ".join(
                    facet_label(
                        "material",
                        key,
                        lang,
                    )
                    for key in facets.get(
                        "material",
                        [],
                    )[:3]
                )
                or "-",
            ),
            (
                L(lang, "원리", "Principle"),
                ", ".join(
                    facet_label(
                        "principle",
                        key,
                        lang,
                    )
                    for key in facets.get(
                        "principle",
                        [],
                    )[:3]
                )
                or "-",
            ),
            (
                L(lang, "결과", "Output"),
                ", ".join(
                    facet_label(
                        "output",
                        key,
                        lang,
                    )
                    for key in facets.get(
                        "output",
                        [],
                    )[:3]
                )
                or "-",
            ),
        ]

        for i, (
            label,
            value,
        ) in enumerate(
            quick_items
        ):
            with quick_cols[
                i % 2
            ]:
                st.markdown(
                    f"""
                    <div class="mw-meta">
                      <div class="mw-meta-label">{html.escape(label)}</div>
                      <div class="mw-meta-value">{html.escape(value)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with hero_right:
        visual_bytes = method_visual_svg(
            method_name=selected_method,
            facets=facets,
            lang=lang,
        )

        render_method_visual(
            visual_bytes
        )

        st.markdown(
            f"""
            <div class="mw-visual-caption">
              {html.escape(L(
                  lang,
                  "Method map · 대상 → 핵심 원리 → 결과를 단순화한 개념도",
                  "Method map · simplified input → principle → output view",
              ))}
            </div>
            """,
            unsafe_allow_html=True,
        )

        representative = (
            representative_figure_candidate(
                profile
            )
        )

        if representative:
            local_image = (
                representative.get(
                    "local_image"
                )
            )

            if local_image:
                with st.expander(
                    L(
                        lang,
                        "🖼 실제 논문 Figure 보기",
                        "🖼 View a real paper Figure",
                    )
                ):
                    st.image(
                        str(local_image),
                        use_container_width=True,
                    )

                    paper = representative[
                        "paper"
                    ]

                    fig = representative[
                        "figure"
                    ]

                    st.caption(
                        f"{fig.get('figure','Figure')} · "
                        f"{paper.get('title','')}"
                    )

                    st.caption(
                        L(
                            lang,
                            "현재 corpus의 실제 OA Figure입니다. 이 기법의 표준 개념도가 아니라 실제 사용 예시입니다.",
                            "Real OA Figure from the corpus; it is an example of use, not a canonical diagram of the method.",
                        )
                    )

            else:
                if st.button(
                    L(
                        lang,
                        "🖼 실제 논문 Figure 1개 불러오기",
                        "🖼 Load one real paper Figure",
                    ),
                    key=(
                        "load_representative_method_figure_"
                        + normalize_method_name(
                            selected_method
                        )
                    ),
                    use_container_width=True,
                ):
                    with st.spinner(
                        L(
                            lang,
                            "Europe PMC에서 실제 Figure를 가져오는 중...",
                            "Loading a real Figure from Europe PMC...",
                        )
                    ):
                        ok, message = (
                            download_inline_images(
                                representative[
                                    "pmcid"
                                ]
                            )
                        )

                    if ok:
                        st.rerun()
                    else:
                        st.warning(
                            message
                        )

    st.markdown(
        "### "
        + L(
            lang,
            "실험을 이해하는 핵심",
            "How to understand the experiment",
        )
    )

    c1, c2, c3 = st.columns(
        3,
        gap="medium",
    )

    with c1:
        render_bullet_card(
            L(
                lang,
                "핵심 원리",
                "Core principle",
            ),
            "⚙️",
            article_data.get(
                "principle_steps",
                [],
            ),
        )

    with c2:
        render_bullet_card(
            L(
                lang,
                "언제 쓰나",
                "When to use it",
            ),
            "🎯",
            article_data.get(
                "best_for_points",
                [],
            ),
        )

    with c3:
        render_bullet_card(
            L(
                lang,
                "해석할 때 주의",
                "Interpretation caveats",
            ),
            "⚠️",
            article_data.get(
                "limitation_points",
                [],
            ),
        )

    interpretation_tip = (
        article_data.get(
            "interpretation_tip",
            "",
        )
    )

    if interpretation_tip:
        st.markdown(
            f"""
            <div class="mw-tip">
              <strong>{html.escape(L(lang, "읽을 때 한 가지 팁", "One interpretation tip"))}</strong><br/>
              {html.escape(interpretation_tip)}
            </div>
            """,
            unsafe_allow_html=True,
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

    # Existing v0.5.0 entries can be upgraded once to the structured format.
    if not (
        db_entry.get(
            "article_json",
            {},
        )
        or {}
    ):
        with st.expander(
            L(
                lang,
                "✨ 이 설명을 새 가독성 포맷으로 업그레이드",
                "✨ Upgrade this entry to the new readable format",
            )
        ):
            st.caption(
                L(
                    lang,
                    "기존 설명은 유지하면서 structured article만 추가합니다. 한 번만 생성하면 이후 모든 사용자가 재사용합니다.",
                    "The existing entry is preserved; only the structured article is added. It is generated once and then reused.",
                )
            )

            if st.button(
                L(
                    lang,
                    "업그레이드 생성",
                    "Generate upgrade",
                ),
                type="primary",
                disabled=not openai_ready(),
                key=(
                    "upgrade_method_wiki_"
                    + normalize_method_name(
                        selected_method
                    )
                ),
            ):
                with st.spinner(
                    L(
                        lang,
                        "가독성 높은 Method article 생성 중...",
                        "Generating the structured Method article...",
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

                        payload = build_method_db_payload(
                            result,
                            canonical_name=selected_method,
                            facets=facets,
                            model=model,
                        )

                        method_wiki_store.upsert(
                            payload
                        )

                        st.success(
                            L(
                                lang,
                                "가독성 포맷으로 업그레이드했습니다.",
                                "Upgraded to the structured readable format.",
                            )
                        )

                        st.rerun()

                    except Exception as exc:
                        error_text = str(exc)

                        if "article_json" in error_text:
                            st.error(
                                L(
                                    lang,
                                    "Supabase의 `article_json` 컬럼이 아직 없습니다. "
                                    "`SUPABASE_METHOD_WIKI_READABILITY_MIGRATION.sql`을 한 번 실행한 뒤 다시 눌러주세요.",
                                    "The Supabase `article_json` column is missing. "
                                    "Run `SUPABASE_METHOD_WIKI_READABILITY_MIGRATION.sql` once, then retry.",
                                )
                            )
                        else:
                            st.error(
                                error_text
                            )

else:
    st.info(
        L(
            lang,
            "이 method의 encyclopedia 설명은 아직 DB에 없습니다. 한 번 생성하면 이후 모든 사용자가 같은 설명을 재사용합니다.",
            "This method does not yet have an encyclopedia entry in the DB. Generate it once and future users will reuse the same entry.",
        )
    )

    # Always show a useful visual even before the DB entry exists.
    visual_bytes = method_visual_svg(
        method_name=selected_method,
        facets=facets,
        lang=lang,
    )

    visual_col, _ = st.columns(
        [1.2, 1]
    )

    with visual_col:
        render_method_visual(
            visual_bytes
        )

    if not method_wiki_ready:
        st.warning(
            L(
                lang,
                "`SUPABASE_METHOD_WIKI_MIGRATION.sql`과 v0.5.1 readability migration을 먼저 실행해야 DB에 저장할 수 있습니다.",
                "Run the Method Wiki SQL migrations before descriptions can be saved.",
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
                "재사용 가능한 Method article 생성 중...",
                "Generating a reusable Method article...",
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

                payload = build_method_db_payload(
                    result,
                    canonical_name=selected_method,
                    facets=facets,
                    model=model,
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
                error_text = str(exc)

                if "article_json" in error_text:
                    st.error(
                        L(
                            lang,
                            "Supabase의 `article_json` 컬럼이 아직 없습니다. "
                            "`SUPABASE_METHOD_WIKI_READABILITY_MIGRATION.sql`을 한 번 실행한 뒤 다시 눌러주세요.",
                            "The Supabase `article_json` column is missing. "
                            "Run `SUPABASE_METHOD_WIKI_READABILITY_MIGRATION.sql` once, then retry.",
                        )
                    )
                else:
                    st.error(
                        error_text
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
