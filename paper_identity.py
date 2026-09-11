import hashlib
import io
import re
import unicodedata
from datetime import datetime
from typing import Dict

from pypdf import PdfReader


DOI_RE = re.compile(
    r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",
    re.IGNORECASE,
)

PMCID_RE = re.compile(
    r"\bPMC\d{5,10}\b",
    re.IGNORECASE,
)

PMID_CONTEXT_RE = re.compile(
    r"\bPMID\s*[:#]?\s*(\d{5,10})\b",
    re.IGNORECASE,
)


def _clean_doi(value: str) -> str:
    value = (value or "").strip()

    value = re.sub(
        r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = value.strip().rstrip(".,;:")

    # Remove unmatched closing punctuation occasionally captured from prose.
    while value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1]

    while value.endswith("]") and value.count("]") > value.count("["):
        value = value[:-1]

    return value.lower()


def normalize_title(value: str) -> str:
    value = unicodedata.normalize(
        "NFKC",
        value or "",
    )

    value = (
        value
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )

    value = value.casefold()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def _credible_title(value: str) -> bool:
    normalized = normalize_title(
        value
    )

    if len(normalized) < 35:
        return False

    # Reject common PDF-generator / placeholder metadata.
    bad = {
        "untitled",
        "document",
        "article",
        "manuscript",
        "pdf",
    }

    if normalized in bad:
        return False

    words = normalized.split()

    return len(words) >= 5


def _extract_metadata_title(
    pdf_bytes: bytes,
) -> str:
    try:
        reader = PdfReader(
            io.BytesIO(pdf_bytes)
        )

        metadata = reader.metadata or {}

        title = (
            metadata.get("/Title")
            or getattr(
                metadata,
                "title",
                "",
            )
            or ""
        )

        return str(title).strip()

    except Exception:
        return ""


def _extract_publication_year(
    *,
    front_text: str,
    metadata_title: str,
    filename: str,
) -> int | None:
    current_year = (
        datetime.utcnow().year
        + 1
    )

    combined = "\n".join(
        [
            front_text[:12000],
            metadata_title,
            filename,
        ]
    )

    candidates = re.findall(
        r"\b(19\d{2}|20\d{2})\b",
        combined,
    )

    for value in candidates:
        year = int(value)

        if 1900 <= year <= current_year:
            return year

    return None


def _document_kind(
    *,
    metadata_title: str,
    filename: str,
    front_text: str,
) -> str:
    blob = " ".join(
        [
            metadata_title,
            filename,
            front_text[:2500],
        ]
    ).casefold()

    supplement_markers = [
        "supplementary information",
        "supporting information",
        "supplementary material",
        "supplemental material",
        "supplemental information",
        "supporting materials",
    ]

    if any(
        marker in blob
        for marker in supplement_markers
    ):
        return "supplement"

    return "main"


def identify_paper(
    *,
    pdf_bytes: bytes,
    paper_text: str,
    filename: str,
    file_hash: str,
) -> Dict:
    """
    Canonical identity hierarchy:

    DOI
      > PMCID
      > PMID
      > normalized title + year
      > exact PDF SHA-256 fallback

    Main article and supplementary documents are intentionally separated.

    Returns a dict safe to persist in Supabase.
    """

    front_text = (
        paper_text
        or ""
    )[:50000]

    metadata_title = (
        _extract_metadata_title(
            pdf_bytes
        )
    )

    kind = _document_kind(
        metadata_title=metadata_title,
        filename=filename,
        front_text=front_text,
    )

    # --------------------------------------------------------
    # 1) DOI
    # --------------------------------------------------------
    doi_matches = DOI_RE.findall(
        front_text
    )

    if doi_matches:
        doi = _clean_doi(
            doi_matches[0]
        )

        if doi:
            key = f"doi:{doi}"

            if kind != "main":
                key += f":{kind}"

            return {
                "canonical_key": key,
                "identity_type": "doi",
                "identity_value": doi,
                "confidence": "high",
                "document_kind": kind,
                "doi": doi,
                "pmcid": "",
                "pmid": "",
                "title": metadata_title,
                "normalized_title": normalize_title(
                    metadata_title
                ),
                "publication_year": (
                    _extract_publication_year(
                        front_text=front_text,
                        metadata_title=metadata_title,
                        filename=filename,
                    )
                ),
            }

    # --------------------------------------------------------
    # 2) PMCID
    # --------------------------------------------------------
    pmcid_match = PMCID_RE.search(
        front_text[:30000]
    )

    if pmcid_match:
        pmcid = (
            pmcid_match
            .group(0)
            .upper()
        )

        key = f"pmcid:{pmcid}"

        if kind != "main":
            key += f":{kind}"

        return {
            "canonical_key": key,
            "identity_type": "pmcid",
            "identity_value": pmcid,
            "confidence": "high",
            "document_kind": kind,
            "doi": "",
            "pmcid": pmcid,
            "pmid": "",
            "title": metadata_title,
            "normalized_title": normalize_title(
                metadata_title
            ),
            "publication_year": (
                _extract_publication_year(
                    front_text=front_text,
                    metadata_title=metadata_title,
                    filename=filename,
                )
            ),
        }

    # --------------------------------------------------------
    # 3) PMID
    # --------------------------------------------------------
    pmid_match = PMID_CONTEXT_RE.search(
        front_text[:30000]
    )

    if pmid_match:
        pmid = pmid_match.group(1)

        key = f"pmid:{pmid}"

        if kind != "main":
            key += f":{kind}"

        return {
            "canonical_key": key,
            "identity_type": "pmid",
            "identity_value": pmid,
            "confidence": "high",
            "document_kind": kind,
            "doi": "",
            "pmcid": "",
            "pmid": pmid,
            "title": metadata_title,
            "normalized_title": normalize_title(
                metadata_title
            ),
            "publication_year": (
                _extract_publication_year(
                    front_text=front_text,
                    metadata_title=metadata_title,
                    filename=filename,
                )
            ),
        }

    # --------------------------------------------------------
    # 4) Normalized title + year
    # --------------------------------------------------------
    year = _extract_publication_year(
        front_text=front_text,
        metadata_title=metadata_title,
        filename=filename,
    )

    if (
        _credible_title(
            metadata_title
        )
        and year is not None
    ):
        normalized_title = normalize_title(
            metadata_title
        )

        title_digest = hashlib.sha256(
            normalized_title.encode(
                "utf-8"
            )
        ).hexdigest()[:24]

        key = (
            f"titleyear:{year}:"
            f"{title_digest}"
        )

        if kind != "main":
            key += f":{kind}"

        return {
            "canonical_key": key,
            "identity_type": "title_year",
            "identity_value": (
                f"{metadata_title} ({year})"
            ),
            "confidence": "medium",
            "document_kind": kind,
            "doi": "",
            "pmcid": "",
            "pmid": "",
            "title": metadata_title,
            "normalized_title": normalized_title,
            "publication_year": year,
        }

    # --------------------------------------------------------
    # 5) Exact file fallback
    # --------------------------------------------------------
    return {
        "canonical_key": (
            f"sha256:{file_hash}"
        ),
        "identity_type": "sha256",
        "identity_value": file_hash,
        "confidence": "exact_file_only",
        "document_kind": kind,
        "doi": "",
        "pmcid": "",
        "pmid": "",
        "title": metadata_title,
        "normalized_title": normalize_title(
            metadata_title
        ),
        "publication_year": year,
    }


def figure_cache_stage(
    *,
    figure_label: str,
    legend: str,
) -> str:
    """
    Figure cache identity:
    canonical paper identity is handled separately.
    Within that paper, use Figure label + normalized source legend hash.

    This prevents a changed Figure / renumbered version from silently reusing
    an incompatible Figure analysis.
    """

    label = re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        str(
            figure_label
            or "figure"
        ),
    ).strip("_")

    normalized_legend = re.sub(
        r"\s+",
        " ",
        (legend or "").strip().casefold(),
    )

    digest = hashlib.sha256(
        normalized_legend.encode(
            "utf-8"
        )
    ).hexdigest()[:16]

    return (
        f"single_figure:"
        f"{label}:legend_{digest}"
    )
