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
    MethodWikiStore,
    normalize_method_name,
)
from method_taxonomy_v2 import (
    FACET_DEFINITIONS,
    facet_label,
    facet_title,
    infer_facets,
    merged_facets,
)
from openai_sidebar import render_openai_usage_panel


APP_VERSION = "v0.6.0-open-beta"

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

    core_principle = [
        facet_label(
            "core_principle",
            key,
            lang,
        )
        for key in facets.get(
            "core_principle",
            [],
        )[:2]
    ]

    detection = [
        facet_label(
            "detection",
            key,
            lang,
        )
        for key in facets.get(
            "detection",
            [],
        )[:2]
    ]

    labeling = [
        facet_label(
            "labeling",
            key,
            lang,
        )
        for key in facets.get(
            "labeling",
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
            core_principle,
            "Core principle",
        )
    )

    p3 = html.escape(
        text_value(
            detection,
            "Detection",
        )
    )

    p4 = html.escape(
        text_value(
            output,
            "Readout",
        )
    )

    label_text = html.escape(
        text_value(
            labeling,
            "Labeling varies",
        )
    )

    purpose_text = html.escape(
        text_value(
            purpose,
            "Experimental question",
        )
    )

    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="780" height="470"
         viewBox="0 0 780 470">
      <rect width="780" height="470" rx="28" fill="#f7f9fc"/>
      <rect x="34" y="30" width="712" height="404" rx="22"
            fill="#ffffff" stroke="#dfe5ec"/>

      <text x="62" y="74" font-family="Arial, sans-serif"
            font-size="18" font-weight="700" fill="#172033">{title}</text>
      <text x="62" y="103" font-family="Arial, sans-serif"
            font-size="14" fill="#657083">{purpose_text}</text>

      <circle cx="115" cy="235" r="54" fill="#e8f2ff" stroke="#9fc3f4" stroke-width="2"/>
      <circle cx="300" cy="235" r="54" fill="#edf8ef" stroke="#a9d7b1" stroke-width="2"/>
      <circle cx="485" cy="235" r="54" fill="#f4efff" stroke="#c7b6ea" stroke-width="2"/>
      <circle cx="670" cy="235" r="54" fill="#fff4df" stroke="#edc97d" stroke-width="2"/>

      <path d="M173 235 L242 235" stroke="#8b97a8" stroke-width="5" stroke-linecap="round"/>
      <path d="M358 235 L427 235" stroke="#8b97a8" stroke-width="5" stroke-linecap="round"/>
      <path d="M543 235 L612 235" stroke="#8b97a8" stroke-width="5" stroke-linecap="round"/>

      <polygon points="242,235 228,227 228,243" fill="#8b97a8"/>
      <polygon points="427,235 413,227 413,243" fill="#8b97a8"/>
      <polygon points="612,235 598,227 598,243" fill="#8b97a8"/>

      <text x="115" y="228" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="13"
            font-weight="700" fill="#253044">TARGET</text>
      <text x="115" y="250" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="12"
            fill="#455268">{p1}</text>

      <text x="300" y="228" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="13"
            font-weight="700" fill="#253044">CORE</text>
      <text x="300" y="250" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="12"
            fill="#455268">{p2}</text>

      <text x="485" y="228" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="13"
            font-weight="700" fill="#253044">DETECTION</text>
      <text x="485" y="250" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="12"
            fill="#455268">{p3}</text>

      <text x="670" y="228" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="13"
            font-weight="700" fill="#253044">OUTPUT</text>
      <text x="670" y="250" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="12"
            fill="#455268">{p4}</text>

      <rect x="205" y="325" width="370" height="52" rx="14"
            fill="#fbfcfe" stroke="#e0e5eb"/>
      <text x="390" y="347" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="12"
            font-weight="700" fill="#657083">LABELING / RECOGNITION</text>
      <text x="390" y="366" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="12"
            fill="#455268">{label_text}</text>

      <text x="62" y="407" font-family="Arial, sans-serif"
            font-size="12" fill="#8a94a3">LALSTUDY Method Map · Taxonomy V2</text>
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
    """
    Reconstruct the readable Method Wiki article from the original v0.5.0
    columns only. No `article_json` column is required.
    """

    suffix = (
        "_ko"
        if lang == "ko"
        else "_en"
    )

    summary = (
        db_entry.get(
            "summary" + suffix,
            "",
        )
        if db_entry
        else ""
    )

    principle = (
        db_entry.get(
            "principle" + suffix,
            "",
        )
        if db_entry
        else ""
    )

    best_for = (
        db_entry.get(
            "best_for" + suffix,
            "",
        )
        if db_entry
        else ""
    )

    limitations = (
        db_entry.get(
            "limitations" + suffix,
            "",
        )
        if db_entry
        else ""
    )

    method_name = (
        db_entry.get(
            "canonical_name",
            "",
        )
        if db_entry
        else ""
    )

    if lang == "ko":
        key_question = (
            f"{method_name}은 어떤 생물학적 질문에 답하는 실험인가?"
            if method_name
            else "이 실험은 어떤 생물학적 질문에 답하는가?"
        )
        interpretation_tip = (
            "측정값 자체와 그 값에서 추론한 생물학적 의미를 구분해서 읽는다."
        )
    else:
        key_question = (
            f"What biological question does {method_name} answer?"
            if method_name
            else "What biological question does this method answer?"
        )
        interpretation_tip = (
            "Separate what the assay directly measures from the biological interpretation inferred from it."
        )

    return {
        "key_question": key_question,
        "one_liner": summary,
        "principle_steps": sentence_points(
            principle,
            max_points=5,
        ),
        "best_for_points": sentence_points(
            best_for,
            max_points=5,
        ),
        "limitation_points": sentence_points(
            limitations,
            max_points=5,
        ),
        "interpretation_tip": interpretation_tip,
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
    "METHOD WIKI · OPEN BETA"
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
            "실험기법을 이름으로 검색하거나, 목적·대상·핵심 원리·검출·표지·결과로 탐색하세요.",
            "Search an experimental method by name, or browse by purpose, material, core principle, detection, labeling, and output.",
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
            "핵심 원리는 실험의 본질, 검출 방식은 신호를 읽는 법, 표지 방식은 target을 표시하는 대표적 방법입니다. 같은 항목 안에서는 OR, 서로 다른 항목 사이는 AND입니다.",
            "Core principle describes what fundamentally defines the assay; detection describes how the signal is read; labeling describes common ways the target is marked. OR within a facet, AND across facets.",
        )
    )

    facet_order = [
        "purpose",
        "material",
        "core_principle",
        "detection",
        "labeling",
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

    facet_cols = st.columns(3)
    selected_facets = {}

    for idx, facet in enumerate(
        facet_order
    ):
        facet_spec = (
            FACET_DEFINITIONS.get(
                facet,
                {}
            )
        )

        values = (
            facet_spec.get(
                "values",
                {}
            )
        )

        if not values:
            # Defensive compatibility guard for mixed-version deployments.
            continue

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
            idx % 3
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
    "core_principle",
    "detection",
    "labeling",
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


st.caption(
    L(
        lang,
        "분류 기준: 핵심 원리는 실험의 본질, 검출 방식은 신호를 읽는 법, 표지 방식은 선택적/대표적 target 표시법입니다.",
        "Taxonomy: core principle defines the assay; detection is how the signal is read; labeling is an optional/common way to mark the target.",
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
        quick_cols = st.columns(3)

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
                L(lang, "핵심 원리", "Core principle"),
                ", ".join(
                    facet_label(
                        "core_principle",
                        key,
                        lang,
                    )
                    for key in facets.get(
                        "core_principle",
                        [],
                    )[:3]
                )
                or "-",
            ),
            (
                L(lang, "검출 방식", "Detection"),
                ", ".join(
                    facet_label(
                        "detection",
                        key,
                        lang,
                    )
                    for key in facets.get(
                        "detection",
                        [],
                    )[:3]
                )
                or "-",
            ),
            (
                L(lang, "표지 방식", "Labeling"),
                ", ".join(
                    facet_label(
                        "labeling",
                        key,
                        lang,
                    )
                    for key in facets.get(
                        "labeling",
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
                i % 3
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
                  "Method map · 대상 → 핵심 원리 → 검출 방식 → 결과, 표지 방식은 별도 표시",
                  "Method map · target → core principle → detection → output, with labeling shown separately",
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
                "`SUPABASE_METHOD_WIKI_MIGRATION.sql`을 먼저 실행해야 DB에 저장할 수 있습니다.",
                "Run `SUPABASE_METHOD_WIKI_MIGRATION.sql` before descriptions can be saved.",
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
                st.error(str(exc))


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



def normalize_figure_label(value):
    """
    Human-readable Figure label for paper cards.

    Existing corpus values are usually already `Fig. 1`, `Fig. 2`, etc.
    This helper keeps those intact and safely normalizes shorter variants.
    """
    value = str(value or "").strip()

    if not value:
        return ""

    lower = value.casefold()

    if lower.startswith("fig."):
        return value

    if lower.startswith("figure"):
        suffix = value[len("figure"):].strip(" .")
        return f"Fig. {suffix}" if suffix else value

    if lower.startswith("fig"):
        suffix = value[len("fig"):].strip(" .")
        return f"Fig. {suffix}" if suffix else value

    return value


def paper_figure_labels(paper, figures=None):
    """
    Return unique Figure labels linked to the selected method in this paper.

    If `figures` is supplied, use that subset (e.g. keyword-matched figures).
    Otherwise use every Figure linked to this method in the paper.
    """
    source = (
        figures
        if figures is not None
        else (
            paper.get(
                "figures",
                [],
            )
            or []
        )
    )

    labels = []

    for fig in source:
        label = normalize_figure_label(
            fig.get(
                "figure",
                "",
            )
        )

        if label and label not in labels:
            labels.append(label)

    return labels


def figure_index_text(labels, lang):
    if not labels:
        return (
            "연결 Figure 없음"
            if lang == "ko"
            else "No linked Figures"
        )

    if len(labels) <= 5:
        return ", ".join(labels)

    visible = ", ".join(labels[:5])
    remainder = len(labels) - 5

    return (
        f"{visible} 외 {remainder}개"
        if lang == "ko"
        else f"{visible} +{remainder} more"
    )


def paper_panel_index(
    figures,
    profile,
    lang,
):
    labels = []

    for figure in (
        figures
        or []
    ):
        value = figure_panel_index_text(
            figure,
            profile,
        )

        if (
            value
            and value
            not in labels
        ):
            labels.append(
                value
            )

    return figure_index_text(
        labels,
        lang,
    )



# ============================================================
# Panel-level method usage map
# ============================================================

PANEL_MARKER_RE = re.compile(
    r"""
    \(
        (?P<labels>
            [A-Z]
            (?:
                \s*(?:[-–—]|to|and|,|&)\s*[A-Z]
            )*
        )
    \)
    """,
    re.VERBOSE,
)


def expand_panel_labels(raw_labels):
    """
    Examples:
    A -> ["A"]
    A-C -> ["A", "B", "C"]
    A–C -> ["A", "B", "C"]
    A and B -> ["A", "B"]
    A, C -> ["A", "C"]
    """

    raw = str(
        raw_labels
        or ""
    ).strip().upper()

    if not raw:
        return []

    range_match = re.fullmatch(
        r"([A-Z])\s*(?:[-–—]|TO)\s*([A-Z])",
        raw,
        flags=re.IGNORECASE,
    )

    if range_match:
        start = ord(
            range_match.group(1).upper()
        )
        end = ord(
            range_match.group(2).upper()
        )

        if start <= end:
            return [
                chr(code)
                for code in range(
                    start,
                    end + 1,
                )
            ]

    tokens = re.split(
        r"\s*(?:,|AND|&)\s*",
        raw,
        flags=re.IGNORECASE,
    )

    labels = []

    for token in tokens:
        token = token.strip()

        nested_range = re.fullmatch(
            r"([A-Z])\s*(?:[-–—]|TO)\s*([A-Z])",
            token,
            flags=re.IGNORECASE,
        )

        if nested_range:
            a = ord(
                nested_range.group(1).upper()
            )
            b = ord(
                nested_range.group(2).upper()
            )

            if a <= b:
                labels.extend(
                    chr(code)
                    for code in range(
                        a,
                        b + 1,
                    )
                )

        elif re.fullmatch(
            r"[A-Z]",
            token,
        ):
            labels.append(
                token
            )

    # Preserve order, remove duplicates.
    output = []

    for label in labels:
        if label not in output:
            output.append(
                label
            )

    return output


def normalize_match_text(value):
    value = str(
        value
        or ""
    ).casefold()

    value = re.sub(
        r"[^a-z0-9가-힣]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def method_match_terms(profile):
    """
    Use the canonical name and curated aliases only.
    This keeps panel assignment grounded in the Figure caption rather than
    inventing method-specific synonyms on the fly.
    """

    raw_terms = [
        profile.get(
            "name",
            "",
        ),
        *(
            profile.get(
                "aliases",
                [],
            )
            or []
        ),
    ]

    terms = []

    for term in raw_terms:
        normalized = normalize_match_text(
            term
        )

        if (
            normalized
            and normalized
            not in terms
        ):
            terms.append(
                normalized
            )

    return terms


def caption_mentions_method(
    text,
    profile,
):
    normalized_text = normalize_match_text(
        text
    )

    if not normalized_text:
        return False

    for term in method_match_terms(
        profile
    ):
        if term in normalized_text:
            return True

    return False


def split_caption_into_panels(
    caption,
):
    """
    Split a Figure legend into:
    - preamble before first panel marker
    - panel chunks keyed by A/B/C...

    A range marker like (A-C) is attached to A, B and C using the same caption
    chunk because the source caption itself groups those panels together.
    """

    caption = str(
        caption
        or ""
    ).strip()

    matches = list(
        PANEL_MARKER_RE.finditer(
            caption
        )
    )

    if not matches:
        return {
            "preamble": caption,
            "panels": [],
        }

    preamble = caption[
        :matches[0].start()
    ].strip()

    panels = []

    for index, match in enumerate(
        matches
    ):
        end = (
            matches[
                index + 1
            ].start()
            if index + 1
            < len(matches)
            else len(caption)
        )

        body = caption[
            match.end():end
        ].strip(
            " .;:-"
        )

        labels = expand_panel_labels(
            match.group(
                "labels"
            )
        )

        if not labels:
            continue

        panels.append(
            {
                "labels": labels,
                "raw_label": match.group(
                    "labels"
                ).strip(),
                "text": body,
            }
        )

    return {
        "preamble": preamble,
        "panels": panels,
    }


def concise_panel_text(
    text,
    max_chars=360,
):
    text = re.sub(
        r"\s+",
        " ",
        str(
            text
            or ""
        ),
    ).strip()

    if len(text) <= max_chars:
        return text

    shortened = text[
        :max_chars
    ].rsplit(
        " ",
        1,
    )[0]

    return shortened + "…"


def panel_method_usage(
    figure,
    profile,
):
    """
    Caption-grounded panel map.

    status:
    - explicit: method name/alias occurs in this panel chunk
    - figure_context: method is named in the legend preamble and the panel
      receives its description from that shared Figure-level context
    - linked_only: the corpus links the Figure to the method, but the caption
      does not explicitly assign the method to a specific panel
    """

    caption = str(
        figure.get(
            "caption",
            "",
        )
        or ""
    )

    parsed = split_caption_into_panels(
        caption
    )

    preamble = parsed[
        "preamble"
    ]

    panels = parsed[
        "panels"
    ]

    preamble_mentions = (
        caption_mentions_method(
            preamble,
            profile,
        )
    )

    usages = []

    for panel in panels:
        explicit = (
            caption_mentions_method(
                panel[
                    "text"
                ],
                profile,
            )
        )

        if explicit:
            status = "explicit"
        elif preamble_mentions:
            status = "figure_context"
        else:
            continue

        usages.append(
            {
                "labels": panel[
                    "labels"
                ],
                "raw_label": panel[
                    "raw_label"
                ],
                "status": status,
                "text": concise_panel_text(
                    panel[
                        "text"
                    ]
                ),
            }
        )

    # If the legend has panels but none explicitly maps the method,
    # do not falsely claim a panel. Return linked_only and show the user that
    # the evidence is Figure-level only.
    if not usages:
        return {
            "mode": (
                "linked_only"
            ),
            "preamble": concise_panel_text(
                preamble,
            ),
            "usages": [],
            "all_panels": [
                label
                for panel in panels
                for label in panel[
                    "labels"
                ]
            ],
        }

    return {
        "mode": "panel_map",
        "preamble": concise_panel_text(
            preamble,
        ),
        "usages": usages,
        "all_panels": [
            label
            for panel in panels
            for label in panel[
                "labels"
            ]
        ],
    }


def panel_usage_labels(
    figure,
    profile,
):
    mapping = panel_method_usage(
        figure,
        profile,
    )

    labels = []

    for usage in mapping.get(
        "usages",
        [],
    ):
        for label in usage.get(
            "labels",
            [],
        ):
            if label not in labels:
                labels.append(
                    label
                )

    return labels


def compact_panel_range(
    labels,
):
    """
    ["A","B","C"] -> "A-C"
    ["A","C","F"] -> "A,C,F"
    """

    labels = [
        label
        for label in labels
        if re.fullmatch(
            r"[A-Z]",
            str(label),
        )
    ]

    if not labels:
        return ""

    codes = [
        ord(label)
        for label in labels
    ]

    if (
        len(codes) >= 2
        and codes
        == list(
            range(
                codes[0],
                codes[-1] + 1,
            )
        )
    ):
        return (
            labels[0]
            + "-"
            + labels[-1]
        )

    return ",".join(
        labels
    )


def figure_panel_index_text(
    figure,
    profile,
):
    fig_label = normalize_figure_label(
        figure.get(
            "figure",
            "Figure",
        )
    )

    panel_labels = (
        panel_usage_labels(
            figure,
            profile,
        )
    )

    if not panel_labels:
        return fig_label

    suffix = compact_panel_range(
        panel_labels
    )

    return (
        f"{fig_label}{suffix}"
        if suffix
        else fig_label
    )


def render_panel_method_usage(
    figure,
    profile,
    lang,
):
    mapping = panel_method_usage(
        figure,
        profile,
    )

    usages = mapping.get(
        "usages",
        [],
    )

    if usages:
        st.markdown(
            L(
                lang,
                "##### 🔎 이 method가 쓰인 panel",
                "##### 🔎 Panels using this method",
            )
        )

        for usage in usages:
            labels = ", ".join(
                usage.get(
                    "labels",
                    [],
                )
            )

            status = usage.get(
                "status"
            )

            if status == "explicit":
                evidence = L(
                    lang,
                    "caption에 method가 직접 명시됨",
                    "method explicitly named in caption",
                )
            else:
                evidence = L(
                    lang,
                    "Figure-level method 문맥",
                    "Figure-level method context",
                )

            st.markdown(
                f"**{labels}** · {evidence}"
            )

            text = usage.get(
                "text",
                "",
            )

            if text:
                st.caption(
                    text
                )

    else:
        all_panels = mapping.get(
            "all_panels",
            [],
        )

        if all_panels:
            st.caption(
                L(
                    lang,
                    "이 Figure는 method와 연결되어 있지만 legend만으로 특정 panel을 확정할 수 없습니다. "
                    "따라서 Figure-level 연결로만 표시합니다.",
                    "This Figure is linked to the method, but the legend does not support a reliable panel-level assignment. "
                    "It is therefore shown as a Figure-level link only.",
                )
            )


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
        "각 논문에서 이 실험기법이 연결된 Figure와 가능한 경우 panel(A–F)까지 caption 근거로 표시합니다.",
        "Each paper shows linked Figures and, when supported by the caption, the specific panels (A–F).",
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

    # When the user searches Figure captions, show the matching Figure
    # numbers in the paper header. Otherwise show every Figure linked
    # to this method in the paper.
    header_figures = (
        matching_figures
        if (
            keyword
            and search_scope
            in {"both", "caption"}
            and matching_figures
        )
        else all_figures
    )

    linked_figure_labels = (
        paper_figure_labels(
            paper,
            figures=header_figures,
        )
    )

    linked_figure_text = (
        paper_panel_index(
            header_figures,
            profile,
            lang,
        )
    )

    with st.expander(
        f"{title} ({year}) · {linked_figure_text}"
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

        if linked_figure_labels:
            linked_panel_items = [
                figure_panel_index_text(
                    figure,
                    profile,
                )
                for figure in header_figures
            ]

            linked_panel_items = [
                item
                for item in linked_panel_items
                if item
            ]

            st.markdown(
                (
                    "**이 method가 연결된 Figure / panel:** "
                    if lang == "ko"
                    else "**Figures / panels linked to this method:** "
                )
                + " · ".join(
                    linked_panel_items
                )
            )
        else:
            st.caption(
                L(
                    lang,
                    "이 논문에는 현재 직접 연결된 Figure 번호가 없습니다.",
                    "No Figure number is directly linked to this method in the current corpus.",
                )
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
                f"#### 🧬 {normalize_figure_label(fig_name)}"
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

            render_panel_method_usage(
                fig,
                profile,
                lang,
            )


st.caption(
    L(
        lang,
        "Method 설명은 Supabase Method DB에, 논문·Figure 연결은 기존 Nature Communications OA corpus에 저장됩니다.",
        "Method explanations live in the Supabase Method DB; paper/Figure links remain in the existing Nature Communications OA corpus.",
    )
)
