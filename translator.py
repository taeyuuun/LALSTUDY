import re
import time
import random
import streamlit as st

try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator
except ImportError:
    GoogleTranslator = None
    MyMemoryTranslator = None


ERROR_MARKERS = (
    "error 500",
    "server error",
    "that's an error",
    "that’s an error",
    "that's all we know",
    "that’s all we know",
    "<html",
    "<!doctype html",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
)


def _looks_like_error_page(text):
    if not text:
        return True

    lowered = str(text).strip().lower()

    return any(
        marker in lowered
        for marker in ERROR_MARKERS
    )


def _mostly_korean(text):
    if not text:
        return True

    letters = re.findall(r"[A-Za-z가-힣]", text)

    if not letters:
        return False

    ko = len(
        re.findall(r"[가-힣]", text)
    )

    return (
        ko / max(len(letters), 1)
        > 0.55
    )


def _sentence_chunks(
    text,
    max_chars=4200
):
    """
    Larger chunks = fewer requests.
    Stay below typical web-translator length limits.
    """
    text = re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    sents = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    chunks = []
    current = ""

    for sent in sents:
        sent = sent.strip()

        if not sent:
            continue

        if (
            len(current)
            + len(sent)
            + 1
            <= max_chars
        ):
            current = (
                current
                + " "
                + sent
            ).strip()

        else:
            if current:
                chunks.append(
                    current
                )

            if len(sent) <= max_chars:
                current = sent

            else:
                for i in range(
                    0,
                    len(sent),
                    max_chars
                ):
                    piece = sent[
                        i:i + max_chars
                    ]

                    if len(piece) == max_chars:
                        chunks.append(
                            piece
                        )
                    else:
                        current = piece

    if current:
        chunks.append(
            current
        )

    return chunks


def _protect_terms(
    text,
    terms
):
    """
    Protect canonical scientific names from being unnecessarily translated.
    """
    protected = {}
    output = text

    cleaned_terms = sorted(
        {
            t for t in (terms or [])
            if t and len(t) >= 2
        },
        key=len,
        reverse=True
    )

    symbols = re.findall(
        r"(?<![A-Za-z0-9])"
        r"(?:"
        r"[A-Z]{2,}[A-Z0-9]*"
        r"|[A-Z]{1,4}-\d+[A-Z0-9-]*"
        r"|pSTAT\d+"
        r")"
        r"(?![A-Za-z0-9])",
        output
    )

    cleaned_terms.extend(
        symbols
    )

    idx = 0

    for term in cleaned_terms:

        pattern = re.compile(
            re.escape(term),
            re.IGNORECASE
        )

        while True:

            match = pattern.search(
                output
            )

            if not match:
                break

            # Plain token tends to survive translators better than nested brackets.
            token = (
                f"LALTERMXYZ{idx}XYZ"
            )

            protected[
                token
            ] = match.group(0)

            output = (
                output[:match.start()]
                + token
                + output[match.end():]
            )

            idx += 1

            if idx > 250:
                break

        if idx > 250:
            break

    return (
        output,
        protected
    )


def _restore_terms(
    text,
    protected
):
    output = text

    for token, original in (
        protected.items()
    ):
        # Exact restore
        output = output.replace(
            token,
            original
        )

        # Translators sometimes insert spaces.
        loose = re.sub(
            r"XYZ(\d+)XYZ",
            r"XYZ\s*\1\s*XYZ",
            re.escape(token)
        )

        try:
            output = re.sub(
                loose,
                original,
                output,
                flags=re.IGNORECASE
            )
        except Exception:
            pass

    return output


def _google_translate(
    text
):
    if GoogleTranslator is None:
        raise RuntimeError(
            "GoogleTranslator unavailable"
        )

    result = GoogleTranslator(
        source="auto",
        target="ko"
    ).translate(text)

    if _looks_like_error_page(
        result
    ):
        raise RuntimeError(
            "Google translator returned an error page"
        )

    return result


def _mymemory_translate(
    text
):
    if MyMemoryTranslator is None:
        raise RuntimeError(
            "MyMemoryTranslator unavailable"
        )

    result = MyMemoryTranslator(
        source="en",
        target="ko"
    ).translate(text)

    if _looks_like_error_page(
        result
    ):
        raise RuntimeError(
            "MyMemory returned an error page"
        )

    return result


@st.cache_data(
    show_spinner=False,
    ttl=60 * 60 * 24 * 30,
    max_entries=5000
)
def _translate_chunk_cached(
    text
):
    """
    Try Google first.
    If transient failures occur, retry with short exponential backoff.
    If Google still fails, attempt MyMemory for shorter chunks.
    """

    # Google: 3 attempts
    last_error = None

    for attempt in range(3):
        try:
            result = _google_translate(
                text
            )

            if result:
                return {
                    "text": result,
                    "backend": "google",
                    "ok": True,
                }

        except Exception as exc:
            last_error = exc

        time.sleep(
            0.6
            * (2 ** attempt)
            + random.uniform(
                0.0,
                0.35
            )
        )

    # MyMemory is safer with short input.
    # Split this failed chunk further to reduce size.
    try:
        smaller = _sentence_chunks(
            text,
            max_chars=450
        )

        translated = []

        for piece in smaller:

            result = _mymemory_translate(
                piece
            )

            if (
                not result
                or _looks_like_error_page(
                    result
                )
            ):
                raise RuntimeError(
                    "MyMemory fallback failed"
                )

            translated.append(
                result
            )

            # Avoid hammering public free endpoint.
            time.sleep(0.15)

        if translated:
            return {
                "text": " ".join(
                    translated
                ),
                "backend": "mymemory",
                "ok": True,
            }

    except Exception as exc:
        last_error = exc

    return {
        "text": text,
        "backend": "source",
        "ok": False,
        "error": str(
            last_error or "translation failed"
        ),
    }


def translate_text(
    text,
    lang,
    preserve_terms=None
):
    """
    Translate source text into Korean when Korean mode is selected.

    Important:
    - Never display an HTML/500 error page as translated content.
    - Failed translations fall back to original source text.
    - Scientific terms are restored after translation.
    """

    if not text:
        return text

    if lang != "ko":
        return text

    if _mostly_korean(
        text
    ):
        return text

    protected_text, protected = (
        _protect_terms(
            text,
            preserve_terms or []
        )
    )

    results = []

    for chunk in _sentence_chunks(
        protected_text,
        max_chars=4200
    ):

        payload = (
            _translate_chunk_cached(
                chunk
            )
        )

        value = payload.get(
            "text",
            chunk
        )

        # Final safety net.
        if _looks_like_error_page(
            value
        ):
            value = chunk

        results.append(
            value
        )

    translated = " ".join(
        results
    )

    return _restore_terms(
        translated,
        protected
    )


def translation_backend_available():
    return (
        GoogleTranslator is not None
        or MyMemoryTranslator is not None
    )
