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


def _clean_one_term(
    value: str,
) -> str:
    """
    Treat the entire input as ONE concept/phrase.

    Important UX rule:
    "apoptotic stress" remains exactly one queue item.
    We intentionally do NOT split on spaces, commas, or semicolons here.
    """
    value = (
        value
        or ""
    ).strip()

    value = " ".join(
        value.split()
    )

    return value[:160]


def _queue_key() -> str:
    return (
        "lal_global_archive_queue_v2"
    )


def _input_key() -> str:
    return (
        "lal_global_archive_single_input_v2"
    )


def _result_key() -> str:
    return (
        "lal_global_archive_result_v2"
    )


def _get_queue() -> List[str]:
    queue = st.session_state.get(
        _queue_key(),
        [],
    )

    if not isinstance(
        queue,
        list,
    ):
        queue = []

    return queue


def _set_queue(
    queue: List[str],
):
    st.session_state[
        _queue_key()
    ] = queue


def _add_term(
    value: str,
):
    term = _clean_one_term(
        value
    )

    if not term:
        return

    queue = _get_queue()

    normalized = {
        normalize_concept(
            item
        )
        for item in queue
    }

    if normalize_concept(
        term
    ) not in normalized:
        queue.append(
            term
        )

    _set_queue(
        queue
    )

    # A changed queue invalidates the previous result.
    st.session_state.pop(
        _result_key(),
        None,
    )


def _remove_term(
    index: int,
):
    queue = _get_queue()

    if (
        0 <= index < len(queue)
    ):
        queue.pop(
            index
        )

    _set_queue(
        queue
    )

    st.session_state.pop(
        _result_key(),
        None,
    )


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
        f"**{canonical}**"
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
    Global left-sidebar Knowledge Archive.

    Users add EXACTLY one term/phrase at a time to a queue.
    Archive search is API-free.
    Gemini is called only after an explicit MISS-generation click.
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

    with st.sidebar:
        st.divider()

        with st.expander(
            (
                "🧠 Knowledge Archive"
                if connected
                else "🧠 Knowledge Archive ⚠"
            ),
            expanded=True,
        ):
            st.caption(
                _L(
                    lang,
                    "모르는 scientific term/phrase를 하나씩 추가하세요. 띄어쓰기가 포함된 표현도 하나의 용어로 유지됩니다.",
                    "Add unfamiliar scientific terms/phrases one at a time. Multi-word phrases stay as one concept.",
                )
            )

            # ------------------------------------------------
            # ONE TERM / PHRASE INPUT
            # ------------------------------------------------
            with st.form(
                "lal_archive_add_term_form_v2",
                clear_on_submit=True,
            ):
                raw_term = st.text_input(
                    _L(
                        lang,
                        "용어 / 구절",
                        "Term / phrase",
                    ),
                    placeholder=(
                        "apoptotic stress"
                    ),
                    key=_input_key(),
                )

                add_clicked = (
                    st.form_submit_button(
                        _L(
                            lang,
                            "➕ 용어 추가",
                            "➕ Add term",
                        ),
                        use_container_width=True,
                    )
                )

                if add_clicked:
                    _add_term(
                        raw_term
                    )

            queue = _get_queue()

            # ------------------------------------------------
            # QUEUE
            # ------------------------------------------------
            if queue:
                st.markdown(
                    "**"
                    + _L(
                        lang,
                        f"추가한 용어 · {len(queue)}",
                        f"Queued terms · {len(queue)}",
                    )
                    + "**"
                )

                for index, term in enumerate(
                    queue
                ):
                    text_col, remove_col = (
                        st.columns(
                            [5.7, 1.0]
                        )
                    )

                    with text_col:
                        st.write(
                            term
                        )

                    with remove_col:
                        if st.button(
                            "×",
                            key=(
                                f"lal_archive_remove_"
                                f"{index}_"
                                f"{normalize_concept(term)}"
                            ),
                            help=_L(
                                lang,
                                "이 용어 제거",
                                "Remove this term",
                            ),
                            use_container_width=True,
                        ):
                            _remove_term(
                                index
                            )
                            st.rerun()

                queue_actions = (
                    st.columns(2)
                )

                with queue_actions[0]:
                    search_clicked = (
                        st.button(
                            _L(
                                lang,
                                "🔎 Archive 검색",
                                "🔎 Search",
                            ),
                            type="primary",
                            use_container_width=True,
                            disabled=(
                                not connected
                            ),
                            key=(
                                "lal_archive_search_queue_v2"
                            ),
                        )
                    )

                with queue_actions[1]:
                    if st.button(
                        _L(
                            lang,
                            "비우기",
                            "Clear",
                        ),
                        use_container_width=True,
                        key=(
                            "lal_archive_clear_queue_v2"
                        ),
                    ):
                        _set_queue(
                            []
                        )

                        st.session_state.pop(
                            _result_key(),
                            None,
                        )

                        st.rerun()

            else:
                search_clicked = False

                st.caption(
                    _L(
                        lang,
                        "예: `apoptotic stress` 전체를 한 번에 추가하면 하나의 concept으로 검색됩니다.",
                        "Example: adding `apoptotic stress` keeps the full phrase as one concept.",
                    )
                )

            # ------------------------------------------------
            # CONNECTION DIAGNOSTICS
            # ------------------------------------------------
            if not connected:
                st.warning(
                    _L(
                        lang,
                        "Archive DB 미연결",
                        "Archive DB not connected",
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

            # ------------------------------------------------
            # ARCHIVE LOOKUP
            # ------------------------------------------------
            if search_clicked:
                try:
                    lookup = (
                        client.lookup_many(
                            queue
                        )
                    )

                    st.session_state[
                        _result_key()
                    ] = {
                        "requested": list(
                            queue
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
                        _result_key()
                    ] = {
                        "requested": list(
                            queue
                        ),
                        "hits": {},
                        "misses": list(
                            queue
                        ),
                        "error": str(
                            exc
                        ),
                    }

            result = (
                st.session_state.get(
                    _result_key()
                )
            )

            if not result:
                st.caption(
                    _L(
                        lang,
                        "검색은 API를 사용하지 않습니다. Archive MISS만 원할 때 AI로 생성할 수 있습니다.",
                        "Search uses no AI API. Only Archive MISSes can be generated on demand.",
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

            # ------------------------------------------------
            # DISPLAY HITS
            # ------------------------------------------------
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

            # ------------------------------------------------
            # GENERATE MISSES
            # ------------------------------------------------
            if misses:
                st.warning(
                    _L(
                        lang,
                        "Archive에 없음: ",
                        "Not in Archive: ",
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
                            f"✨ MISS {len(misses)}개 AI 생성 + 저장",
                            f"✨ Generate {len(misses)} MISSes + save",
                        ),
                        use_container_width=True,
                        disabled=(
                            not gemini_key
                            or not sdk_available()
                        ),
                        key=(
                            "lal_archive_generate_queue_v2"
                        ),
                    )
                )

                st.caption(
                    _L(
                        lang,
                        "이 버튼을 눌렀을 때만 Gemini request 1회가 발생합니다.",
                        "Gemini is called once only when this button is clicked.",
                    )
                )

                if generate_clicked:
                    with st.spinner(
                        _L(
                            lang,
                            "없는 개념을 한 번에 생성 중...",
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
                                    pass

                            refreshed = (
                                client.lookup_many(
                                    requested
                                )
                            )

                            st.session_state[
                                _result_key()
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
                                    f"{len(generated)}개 생성 및 Archive 저장 완료",
                                    f"Generated and archived {len(generated)} concepts",
                                )
                            )

                            st.rerun()

                        except Exception as exc:
                            st.error(
                                str(exc)
                            )
