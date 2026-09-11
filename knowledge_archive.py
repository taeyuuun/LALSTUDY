import os
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

try:
    from supabase import create_client
except Exception:
    create_client = None


MAX_CONCEPT_LENGTH = 160


def normalize_concept(value: str) -> str:
    value = unicodedata.normalize(
        "NFKC",
        value or "",
    )

    value = value.strip()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    value = value.strip(
        " \t\r\n.,;:!?()[]{}\"'`"
    )

    return value.casefold()


def clean_concept(value: str) -> str:
    value = unicodedata.normalize(
        "NFKC",
        value or "",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value[
        :MAX_CONCEPT_LENGTH
    ]


def parse_concept_input(raw: str) -> List[str]:
    """
    Accept newline / comma / semicolon separated selections.
    Preserve order and remove exact-normalized duplicates.
    """
    chunks = re.split(
        r"[\n,;]+",
        raw or "",
    )

    output = []
    seen = set()

    for chunk in chunks:
        cleaned = clean_concept(
            chunk
        )

        normalized = normalize_concept(
            cleaned
        )

        if (
            not cleaned
            or not normalized
            or normalized in seen
        ):
            continue

        seen.add(
            normalized
        )

        output.append(
            cleaned
        )

    return output


def get_supabase_credentials(
    secrets=None,
) -> Tuple[str, str]:
    url = ""
    key = ""

    if secrets is not None:
        try:
            url = str(
                secrets.get(
                    "SUPABASE_URL",
                    "",
                )
            ).strip()

            # 2026 recommended backend key.
            key = str(
                secrets.get(
                    "SUPABASE_SECRET_KEY",
                    "",
                )
            ).strip()

            # Legacy compatibility only.
            if not key:
                key = str(
                    secrets.get(
                        "SUPABASE_SERVICE_ROLE_KEY",
                        "",
                    )
                ).strip()

        except Exception:
            pass

    if not url:
        url = os.getenv(
            "SUPABASE_URL",
            "",
        ).strip()

    if not key:
        key = os.getenv(
            "SUPABASE_SECRET_KEY",
            "",
        ).strip()

    if not key:
        key = os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY",
            "",
        ).strip()

    return url, key


class KnowledgeArchive:
    def __init__(
        self,
        url: str,
        secret_key: str,
    ):
        if create_client is None:
            raise RuntimeError(
                "The `supabase` Python package is not installed."
            )

        if not url or not secret_key:
            raise ValueError(
                "Supabase URL/secret key is missing."
            )

        self.client = create_client(
            url,
            secret_key,
        )

    def ping(self) -> bool:
        response = (
            self.client
            .table(
                "knowledge_concepts"
            )
            .select(
                "id"
            )
            .limit(
                1
            )
            .execute()
        )

        return response is not None

    def lookup_many(
        self,
        requested_terms: List[str],
        increment_hits: bool = True,
    ):
        """
        Returns:
        {
          "hits": {normalized_requested_term: concept_row},
          "misses": [original requested term]
        }
        """
        cleaned_terms = [
            clean_concept(
                x
            )
            for x in requested_terms
            if clean_concept(
                x
            )
        ]

        normalized_to_original = {
            normalize_concept(term): term
            for term in cleaned_terms
        }

        wanted = list(
            normalized_to_original.keys()
        )

        if not wanted:
            return {
                "hits": {},
                "misses": [],
            }

        hits = {}

        # 1) direct canonical-name match
        response = (
            self.client
            .table(
                "knowledge_concepts"
            )
            .select(
                "*"
            )
            .in_(
                "normalized_name",
                wanted,
            )
            .execute()
        )

        direct_rows = (
            response.data
            or []
        )

        by_id = {}

        for row in direct_rows:
            normalized = row.get(
                "normalized_name",
                "",
            )

            if normalized:
                hits[
                    normalized
                ] = row

            if row.get(
                "id"
            ):
                by_id[
                    row["id"]
                ] = row

        remaining = [
            item
            for item in wanted
            if item not in hits
        ]

        # 2) alias match
        if remaining:
            alias_response = (
                self.client
                .table(
                    "knowledge_aliases"
                )
                .select(
                    "alias_normalized,concept_id"
                )
                .in_(
                    "alias_normalized",
                    remaining,
                )
                .execute()
            )

            alias_rows = (
                alias_response.data
                or []
            )

            concept_ids = list(
                {
                    row.get(
                        "concept_id"
                    )
                    for row in alias_rows
                    if row.get(
                        "concept_id"
                    )
                }
            )

            missing_ids = [
                concept_id
                for concept_id in concept_ids
                if concept_id not in by_id
            ]

            if missing_ids:
                concept_response = (
                    self.client
                    .table(
                        "knowledge_concepts"
                    )
                    .select(
                        "*"
                    )
                    .in_(
                        "id",
                        missing_ids,
                    )
                    .execute()
                )

                for row in (
                    concept_response.data
                    or []
                ):
                    if row.get(
                        "id"
                    ):
                        by_id[
                            row["id"]
                        ] = row

            for alias_row in alias_rows:
                alias = alias_row.get(
                    "alias_normalized"
                )

                concept = by_id.get(
                    alias_row.get(
                        "concept_id"
                    )
                )

                if (
                    alias
                    and concept
                ):
                    hits[
                        alias
                    ] = concept

        if increment_hits:
            hit_ids = {
                row.get(
                    "id"
                )
                for row in hits.values()
                if row.get(
                    "id"
                )
            }

            for concept_id in hit_ids:
                try:
                    (
                        self.client
                        .rpc(
                            "archive_increment_hit",
                            {
                                "p_concept_id": (
                                    concept_id
                                )
                            },
                        )
                        .execute()
                    )
                except Exception:
                    # Hit statistics should never break learning UX.
                    pass

        misses = [
            normalized_to_original[
                normalized
            ]
            for normalized in wanted
            if normalized not in hits
        ]

        return {
            "hits": hits,
            "misses": misses,
        }

    def _get_existing_by_normalized(
        self,
        normalized_name: str,
    ) -> Optional[Dict]:
        response = (
            self.client
            .table(
                "knowledge_concepts"
            )
            .select(
                "*"
            )
            .eq(
                "normalized_name",
                normalized_name,
            )
            .limit(
                1
            )
            .execute()
        )

        rows = (
            response.data
            or []
        )

        return (
            rows[0]
            if rows
            else None
        )

    def save_explanation(
        self,
        explanation: Dict,
        source_model: str,
    ) -> Dict:
        canonical_name = clean_concept(
            explanation.get(
                "canonical_name",
                "",
            )
        )

        normalized_name = normalize_concept(
            canonical_name
        )

        if not normalized_name:
            raise ValueError(
                "AI explanation has no canonical concept name."
            )

        existing = (
            self._get_existing_by_normalized(
                normalized_name
            )
        )

        # Never silently overwrite previously archived knowledge.
        # REVIEWED / CURATED records are especially protected.
        if existing:
            concept_row = existing

        else:
            payload = {
                "canonical_name": (
                    canonical_name
                ),
                "normalized_name": (
                    normalized_name
                ),
                "definition_ko": (
                    explanation.get(
                        "definition_ko",
                        "",
                    )
                ),
                "definition_en": (
                    explanation.get(
                        "definition_en",
                        "",
                    )
                ),
                "mechanism_ko": (
                    explanation.get(
                        "mechanism_ko",
                        "",
                    )
                ),
                "mechanism_en": (
                    explanation.get(
                        "mechanism_en",
                        "",
                    )
                ),
                "why_it_matters_ko": (
                    explanation.get(
                        "why_it_matters_ko",
                        "",
                    )
                ),
                "why_it_matters_en": (
                    explanation.get(
                        "why_it_matters_en",
                        "",
                    )
                ),
                "prerequisites": (
                    explanation.get(
                        "prerequisites",
                        [],
                    )
                ),
                "difficulty": (
                    explanation.get(
                        "difficulty",
                        "intermediate",
                    )
                ),
                "quality_status": (
                    "AI_GENERATED"
                ),
                "source_model": (
                    source_model
                ),
            }

            try:
                response = (
                    self.client
                    .table(
                        "knowledge_concepts"
                    )
                    .insert(
                        payload
                    )
                    .execute()
                )

                rows = (
                    response.data
                    or []
                )

                concept_row = (
                    rows[0]
                    if rows
                    else payload
                )

            except Exception:
                # A simultaneous user may have inserted the same concept.
                concept_row = (
                    self._get_existing_by_normalized(
                        normalized_name
                    )
                )

                if not concept_row:
                    raise

        concept_id = concept_row.get(
            "id"
        )

        if concept_id:
            aliases = [
                explanation.get(
                    "requested_term",
                    ""
                ),
                canonical_name,
            ] + list(
                explanation.get(
                    "aliases",
                    []
                )
                or []
            )

            seen = set()

            for alias in aliases:
                alias_display = clean_concept(
                    alias
                )

                alias_normalized = normalize_concept(
                    alias_display
                )

                if (
                    not alias_normalized
                    or alias_normalized in seen
                ):
                    continue

                seen.add(
                    alias_normalized
                )

                # Canonical lookup already covers normalized_name.
                # Still storing it as an alias is harmless but unnecessary.
                if (
                    alias_normalized
                    == normalized_name
                ):
                    continue

                try:
                    (
                        self.client
                        .table(
                            "knowledge_aliases"
                        )
                        .insert(
                            {
                                "concept_id": (
                                    concept_id
                                ),
                                "alias_display": (
                                    alias_display
                                ),
                                "alias_normalized": (
                                    alias_normalized
                                ),
                            }
                        )
                        .execute()
                    )

                except Exception:
                    # Unique alias already exists: keep the existing mapping.
                    pass

        return concept_row

    def count(self) -> int:
        response = (
            self.client
            .table(
                "knowledge_concepts"
            )
            .select(
                "id",
                count="exact",
            )
            .limit(
                1
            )
            .execute()
        )

        return int(
            response.count
            or 0
        )
