from typing import Dict, Optional

try:
    from supabase import create_client
except Exception:
    create_client = None


class PaperAnalysisCache:
    """
    Canonical paper-level shared cache.

    Paper identity is independent from the uploaded file whenever possible:
    DOI > PMCID > PMID > normalized title+year > exact SHA-256 fallback.

    Uploaded PDF bytes, full extracted text, and Figure image bytes are never
    stored in these tables.
    """

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
            .table("paper_analysis_cache_v2")
            .select("id")
            .limit(1)
            .execute()
        )

        return response is not None

    def register_paper(
        self,
        *,
        identity: Dict,
        file_hash: str,
        filename: str = "",
        file_size: int = 0,
    ):
        canonical_key = identity[
            "canonical_key"
        ]

        paper_payload = {
            "canonical_key": canonical_key,
            "identity_type": (
                identity.get(
                    "identity_type",
                    "sha256",
                )
            ),
            "identity_value": (
                identity.get(
                    "identity_value",
                    "",
                )
            ),
            "confidence": (
                identity.get(
                    "confidence",
                    "",
                )
            ),
            "document_kind": (
                identity.get(
                    "document_kind",
                    "main",
                )
            ),
            "doi": (
                identity.get(
                    "doi",
                    "",
                )
            ),
            "pmcid": (
                identity.get(
                    "pmcid",
                    "",
                )
            ),
            "pmid": (
                identity.get(
                    "pmid",
                    "",
                )
            ),
            "title": (
                identity.get(
                    "title",
                    "",
                )
            ),
            "normalized_title": (
                identity.get(
                    "normalized_title",
                    "",
                )
            ),
            "publication_year": (
                identity.get(
                    "publication_year"
                )
            ),
        }

        (
            self.client
            .table("lalstudy_papers_v2")
            .upsert(
                paper_payload,
                on_conflict="canonical_key",
            )
            .execute()
        )

        alias_payload = {
            "file_hash": file_hash,
            "canonical_key": canonical_key,
            "filename": filename or "",
            "file_size_bytes": int(
                file_size
                or 0
            ),
        }

        (
            self.client
            .table("paper_file_aliases_v2")
            .upsert(
                alias_payload,
                on_conflict="file_hash",
            )
            .execute()
        )

        try:
            (
                self.client
                .rpc(
                    "lalstudy_touch_paper_v2",
                    {
                        "p_canonical_key": (
                            canonical_key
                        )
                    },
                )
                .execute()
            )
        except Exception:
            pass

        # Preserve v0.4.2 exact-hash cache when possible.
        self._promote_legacy_exact_hash(
            file_hash=file_hash,
            canonical_key=canonical_key,
        )

    def _promote_legacy_exact_hash(
        self,
        *,
        file_hash: str,
        canonical_key: str,
    ):
        """
        If v0.4.2 tables exist, copy exact-file cached analyses into the
        new canonical-key table. Safe no-op if legacy tables do not exist.
        """

        try:
            response = (
                self.client
                .table(
                    "paper_analysis_cache"
                )
                .select("*")
                .eq(
                    "paper_hash",
                    file_hash,
                )
                .execute()
            )

            rows = response.data or []

        except Exception:
            return

        for row in rows:
            payload = {
                "canonical_key": (
                    canonical_key
                ),
                "depth": row.get(
                    "depth",
                    "undergraduate",
                ),
                "stage": row.get(
                    "stage",
                    "",
                ),
                "analysis_version": (
                    row.get(
                        "analysis_version",
                        "analysis-v1",
                    )
                ),
                "result_json": row.get(
                    "result_json",
                    {},
                ) or {},
                "provider": row.get(
                    "provider",
                    "openai",
                ),
                "model": row.get(
                    "model",
                    "",
                ),
                "usage_json": row.get(
                    "usage_json",
                    {},
                ) or {},
                "hit_count": int(
                    row.get(
                        "hit_count",
                        0,
                    )
                    or 0
                ),
            }

            try:
                (
                    self.client
                    .table(
                        "paper_analysis_cache_v2"
                    )
                    .upsert(
                        payload,
                        on_conflict=(
                            "canonical_key,"
                            "depth,"
                            "stage,"
                            "analysis_version"
                        ),
                    )
                    .execute()
                )
            except Exception:
                continue

    def get_stage(
        self,
        *,
        canonical_key: str,
        depth: str,
        stage: str,
        analysis_version: str,
        increment_hit: bool = True,
    ) -> Optional[Dict]:
        response = (
            self.client
            .table(
                "paper_analysis_cache_v2"
            )
            .select("*")
            .eq(
                "canonical_key",
                canonical_key,
            )
            .eq(
                "depth",
                depth,
            )
            .eq(
                "stage",
                stage,
            )
            .eq(
                "analysis_version",
                analysis_version,
            )
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return None

        row = rows[0]

        if (
            increment_hit
            and row.get("id")
        ):
            try:
                (
                    self.client
                    .rpc(
                        "paper_analysis_increment_hit_v2",
                        {
                            "p_cache_id": (
                                row["id"]
                            )
                        },
                    )
                    .execute()
                )
            except Exception:
                pass

        return row

    def save_stage(
        self,
        *,
        canonical_key: str,
        depth: str,
        stage: str,
        analysis_version: str,
        result_json: Dict,
        model: str = "",
        provider: str = "openai",
        usage_json: Optional[Dict] = None,
    ):
        payload = {
            "canonical_key": canonical_key,
            "depth": depth,
            "stage": stage,
            "analysis_version": analysis_version,
            "result_json": result_json or {},
            "model": model or "",
            "provider": (
                provider
                or "openai"
            ),
            "usage_json": usage_json or {},
        }

        return (
            self.client
            .table(
                "paper_analysis_cache_v2"
            )
            .upsert(
                payload,
                on_conflict=(
                    "canonical_key,"
                    "depth,"
                    "stage,"
                    "analysis_version"
                ),
            )
            .execute()
        )
