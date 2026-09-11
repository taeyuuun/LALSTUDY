import os
from typing import Dict, List

import streamlit as st

from ai_engine import (
    explain_concepts_batch,
    sdk_available,
)
from knowledge_archive import (
    KnowledgeArchive,
    get_supabase_credentials,
    normalize_concept,
    parse_concept_input,
    safe_supabase_diagnostics,
)


def _L(
    lang: str,
    ko: str,
    en: str,
) -> str:
    return ko if lang == "ko" else en


def _gemini_key() -> str:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            value = str(
                st.secrets[
                    "GEMINI_API_KEY"
                ]
            ).strip()

            if value:
                return value
    except Exception:
        pass

    return os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()


@st.cache_resource(
    show_spinner=False
)
def _archive_client(
    url: str,
    secret_key: str,
):
    if not url or not secret_key:
        return None

    try:
        return KnowledgeArchive(
            url,
            secret_key,
        )
    except Exception:
        return None


def _display_concept(
    *,
    data: Dict,
    lang: str,
    source_label: str,
):
    canonical = (
        data.get(
            "canonical_name"
        )
        or "Concept"
    )

    st.markdown(
        f"### {canonical}"
    )

    st.caption(
        source_label
    )

    if lang == "ko":
        definition = data.get(
            "definition_ko",
            "",
        )
        mechanism = data.get(
            "mechanism_ko",
            "",
        )
        why = data.get(
            "why_it_matters_ko",
            "",
        )
    else:
        definition = data.get(
            "definition_en",
            "",
        )
        mechanism = data.get(
            "mechanism_en",
            "",
        )
        why = data.get(
            "why_it_matters_en",
            "",
        )

    if definition:
        st.markdown(
            "**"
            + _L(
                lang,
                "무엇인가",
                "What is it",
            )
            + "**"
        )
        st.write(
            definition
        )

    if mechanism:
        st.markdown(
            "**"
            + _L(
                lang,
                "어떻게 작동하나",
                "How it works",
            )
            + "**"
        )
        st.write(
            mechanism
        )

    if why:
        st.markdown(
            "**"
            + _L(
                lang,
                "왜 중요한가",
                "Why it matters",
            )
            + "**"
        )
        st.write(
            why
        )

    prerequisites = (
        data.get(
            "prerequisites",
            []
        )
        or []
    )

    if prerequisites:
        st.caption(
            _L(
                lang,
                "먼저 알면 좋은 개념: ",
                "Useful prerequisites: ",
            )
            + " → ".join(
                prerequisites
            )
        )

    quality = data.get(
        "quality_status"
    )

    if quality:
        st.caption(
            f"Archive quality: {quality}"
        )


def render_knowledge_archive_widget(
    *,
    lang: str = "ko",
    depth: str = "undergraduate",
    paper_context: str = "",
):
    """
    Render a global, top-right Knowledge Archive popover.

    Search is always API-free.
    Gemini is called only after an explicit MISS-generation click.
    Session state is global so the query/results survive page navigation.
    """

    supabase_url, supabase_secret = (
        get_supabase_credentials(
            st.secrets
        )
    )

    client = _archive_client(
        supabase_url,
        supabase_secret,
    )

    diag = safe_supabase_diagnostics(
        url=supabase_url,
        secret_key=supabase_secret,
        client=client,
    )

    connected = bool(
        diag.get(
            "db_ping"
        )
    )

    # The right column acts like a lightweight top-bar action.
    _, action_col = st.columns(
        [7.6, 2.4]
    )

    with action_col:
        label = (
            "🧠 Knowledge Archive"
            if connected
            else "🧠 Archive ⚠"
        )

        with st.popover(
            label,
            use_container_width=True,
        ):
            st.caption(
                _L(
                    lang,
                    "어느 페이지에서든 scientific concept을 검색할 수 있습니다. 검색 자체는 Gemini API를 사용하지 않습니다.",
                    "Search scientific concepts from any page. Archive search itself never calls Gemini.",
                )
            )

            query = st.text_area(
                _L(
                    lang,
                    "Concept 검색",
                    "Search concepts",
                ),
                placeholder=_L(
                    lang,
                    "zinc homeostasis\np53 conformational change",
                    "zinc homeostasis\np53 conformational change",
                ),
                height=90,
                key=(
                    "lal_global_archive_query"
                ),
                label_visibility=(
                    "collapsed"
                ),
            )

            concepts = (
                parse_concept_input(
                    query
                )[:8]
            )

            search_clicked = st.button(
                _L(
                    lang,
                    "🔎 Archive 검색",
                    "🔎 Search Archive",
                ),
                use_container_width=True,
                disabled=(
                    not concepts
                    or not connected
                ),
                key=(
                    "lal_global_archive_search"
                ),
            )

            result_key = (
                "lal_global_archive_result"
            )

            if search_clicked:
                try:
                    lookup = (
                        client.lookup_many(
                            concepts
                        )
                    )

                    st.session_state[
                        result_key
                    ] = {
                        "requested": (
                            concepts
                        ),
                        "hits": (
                            lookup.get(
                                "hits",
                                {},
                            )
                        ),
                        "misses": (
                            lookup.get(
                                "misses",
                                [],
                            )
                        ),
                        "error": "",
                    }

                except Exception as exc:
                    st.session_state[
                        result_key
                    ] = {
                        "requested": (
                            concepts
                        ),
                        "hits": {},
                        "misses": (
                            concepts
                        ),
                        "error": str(
                            exc
                        ),
                    }

            if not connected:
                st.warning(
                    _L(
                        lang,
                        "Knowledge Archive가 연결되지 않았습니다.",
                        "Knowledge Archive is not connected.",
                    )
                )

                with st.expander(
                    _L(
                        lang,
                        "연결 진단",
                        "Connection diagnostics",
                    ),
                    expanded=False,
                ):
                    st.write(
                        {
                            "SUPABASE_URL": (
                                "✅"
                                if diag.get(
                                    "url_present"
                                )
                                else "❌"
                            ),
                            "SUPABASE_SECRET_KEY": (
                                "✅"
                                if diag.get(
                                    "secret_present"
                                )
                                else "❌"
                            ),
                            "client": (
                                "✅"
                                if diag.get(
                                    "client_created"
                                )
                                else "❌"
                            ),
                            "DB ping": (
                                "✅"
                                if diag.get(
                                    "db_ping"
                                )
                                else "❌"
                            ),
                        }
                    )

                    if diag.get(
                        "error"
                    ):
                        st.code(
                            diag[
                                "error"
                            ]
                        )

                return

            result = (
                st.session_state.get(
                    result_key
                )
            )

            if not result:
                st.caption(
                    _L(
                        lang,
                        "Archive HIT은 즉시 표시되고, MISS는 AI 생성 여부를 직접 선택할 수 있습니다.",
                        "Archive HITs appear immediately; you choose whether MISSes should be generated by AI.",
                    )
                )

                return

            if result.get(
                "error"
            ):
                st.error(
                    result[
                        "error"
                    ]
                )

            requested = (
                result.get(
                    "requested",
                    []
                )
            )

            hits = (
                result.get(
                    "hits",
                    {}
                )
            )

            misses = (
                result.get(
                    "misses",
                    []
                )
            )

            hit_count = sum(
                1
                for requested_term
                in requested
                if normalize_concept(
                    requested_term
                )
                in hits
            )

            st.caption(
                f"⚡ HIT {hit_count} · "
                f"MISS {len(misses)}"
            )

            # Show archive hits first.
            for requested_term in (
                requested
            ):
                normalized = (
                    normalize_concept(
                        requested_term
                    )
                )

                data = hits.get(
                    normalized
                )

                if not data:
                    continue

                _display_concept(
                    data=data,
                    lang=lang,
                    source_label=(
                        "⚡ Archive HIT"
                    ),
                )

                st.divider()

            if misses:
                st.warning(
                    _L(
                        lang,
                        "Archive에 없는 concept: ",
                        "Not yet in Archive: ",
                    )
                    + ", ".join(
                        misses
                    )
                )

                gemini_key = (
                    _gemini_key()
                )

                generate_clicked = (
                    st.button(
                        _L(
                            lang,
                            f"✨ MISS {len(misses)}개 AI로 생성 + 저장",
                            f"✨ Generate {len(misses)} MISSes + archive",
                        ),
                        type="primary",
                        use_container_width=True,
                        disabled=(
                            not gemini_key
                            or not sdk_available()
                        ),
                        key=(
                            "lal_global_archive_generate"
                        ),
                    )
                )

                st.caption(
                    _L(
                        lang,
                        "이 버튼을 누를 때만 Gemini request 1회가 발생합니다.",
                        "Gemini is called once only when this button is clicked.",
                    )
                )

                if generate_clicked:
                    with st.spinner(
                        _L(
                            lang,
                            "MISS concept을 한 번에 생성 중...",
                            "Generating missing concepts in one batch...",
                        )
                    ):
                        try:
                            batch, model = (
                                explain_concepts_batch(
                                    concepts=(
                                        misses
                                    ),
                                    api_key=(
                                        gemini_key
                                    ),
                                    depth=depth,
                                    paper_context=(
                                        paper_context
                                    ),
                                )
                            )

                            generated = []

                            for item in (
                                batch.concepts
                            ):
                                payload = (
                                    item.model_dump()
                                )

                                generated.append(
                                    payload
                                )

                                try:
                                    client.save_explanation(
                                        payload,
                                        source_model=(
                                            model
                                        ),
                                    )
                                except Exception:
                                    # Displaying generated knowledge is more
                                    # important than one persistence failure.
                                    pass

                            # Re-query after insertion so the global widget
                            # immediately enters the same Archive-HIT state
                            # another user would see.
                            refreshed = (
                                client.lookup_many(
                                    requested
                                )
                            )

                            st.session_state[
                                result_key
                            ] = {
                                "requested": (
                                    requested
                                ),
                                "hits": (
                                    refreshed.get(
                                        "hits",
                                        {},
                                    )
                                ),
                                "misses": (
                                    refreshed.get(
                                        "misses",
                                        [],
                                    )
                                ),
                                "error": "",
                            }

                            st.success(
                                _L(
                                    lang,
                                    f"{len(generated)}개 concept 생성 및 Archive 저장 완료",
                                    f"Generated and archived {len(generated)} concepts",
                                )
                            )

                            st.rerun()

                        except Exception as exc:
                            st.error(
                                str(exc)
                            )
