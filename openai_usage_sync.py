"""Official OpenAI organization usage sync for LALSTUDY.

Uses the OpenAI Admin API with a server-side Admin API key. The Admin key must
never be exposed in the browser or committed to Git.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


COMPLIMENTARY_LARGE_GROUP_PREFIXES = (
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.1-codex-mini",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o-mini",
    "o4-mini",
    "o3-mini",
    "o1-mini",
    "codex-mini",
)

INCENTIVE_TIER_MARKERS = (
    "data sharing",
    "data_sharing",
    "data-sharing",
    "incentive",
    "complimentary",
)


def _utc_start_of_day() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _to_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    raise TypeError(f"Unsupported OpenAI response type: {type(obj)!r}")


def _iter_usage_results(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for bucket in payload.get("data", []) or []:
        bucket = _to_dict(bucket) if not isinstance(bucket, dict) else bucket
        for result in bucket.get("results", []) or []:
            result = _to_dict(result) if not isinstance(result, dict) else result
            yield result


def _iter_cost_results(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for bucket in payload.get("data", []) or []:
        bucket = _to_dict(bucket) if not isinstance(bucket, dict) else bucket
        for result in bucket.get("results", []) or []:
            result = _to_dict(result) if not isinstance(result, dict) else result
            yield result


def _is_large_group_model(model: Optional[str]) -> bool:
    name = str(model or "").strip().lower()
    return any(name.startswith(prefix) for prefix in COMPLIMENTARY_LARGE_GROUP_PREFIXES)


def _is_incentive_tier(service_tier: Optional[str]) -> bool:
    tier = str(service_tier or "").strip().lower()
    return any(marker in tier for marker in INCENTIVE_TIER_MARKERS)


def parse_usage_payload(payload: Dict[str, Any], daily_budget: int) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = list(_iter_usage_results(payload))

    total_input = total_output = total_tokens = total_requests = 0
    incentive_tokens = 0
    eligible_group_tokens = 0
    eligible_group_requests = 0
    service_tiers = set()
    models = set()

    for row in rows:
        input_tokens = int(row.get("input_tokens", 0) or 0)
        output_tokens = int(row.get("output_tokens", 0) or 0)
        requests_count = int(row.get("num_model_requests", 0) or 0)
        row_total = input_tokens + output_tokens
        model = str(row.get("model") or "")
        service_tier = str(row.get("service_tier") or "")

        total_input += input_tokens
        total_output += output_tokens
        total_tokens += row_total
        total_requests += requests_count

        if model:
            models.add(model)
        if service_tier:
            service_tiers.add(service_tier)

        if _is_large_group_model(model):
            eligible_group_tokens += row_total
            eligible_group_requests += requests_count
            if _is_incentive_tier(service_tier):
                incentive_tokens += row_total

    incentive_tier_visible = any(_is_incentive_tier(x) for x in service_tiers)

    if incentive_tier_visible:
        complimentary_used = incentive_tokens
        complimentary_exact = True
        complimentary_source = "official incentive service tier"
    else:
        # This is official model usage, but not guaranteed to equal free-token
        # usage if some traffic was billed rather than data-sharing-incentive.
        complimentary_used = eligible_group_tokens
        complimentary_exact = False
        complimentary_source = "official eligible-model usage fallback"

    remaining = max(int(daily_budget) - complimentary_used, 0) if daily_budget > 0 else None

    return {
        "ok": True,
        "official": True,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "total_requests": total_requests,
        "eligible_group_tokens": eligible_group_tokens,
        "eligible_group_requests": eligible_group_requests,
        "complimentary_used_tokens": complimentary_used,
        "complimentary_remaining_tokens": remaining,
        "complimentary_exact": complimentary_exact,
        "complimentary_source": complimentary_source,
        "incentive_tier_visible": incentive_tier_visible,
        "service_tiers": sorted(service_tiers),
        "models": sorted(models),
        "daily_budget": int(daily_budget),
        "rows": len(rows),
    }


def parse_cost_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    total_usd = 0.0
    currencies = set()
    rows = 0

    for row in _iter_cost_results(payload):
        rows += 1
        amount = row.get("amount") or {}
        if not isinstance(amount, dict):
            amount = _to_dict(amount)
        currency = str(amount.get("currency") or "").lower()
        value = float(amount.get("value", 0) or 0)

        if currency:
            currencies.add(currency)
        if currency in ("", "usd"):
            total_usd += value

    return {
        "today_cost_usd": total_usd,
        "cost_rows": rows,
        "cost_currencies": sorted(currencies),
    }


@st.cache_data(ttl=60, show_spinner=False)
def fetch_openai_official_usage(
    admin_key: str,
    daily_budget: int = 2_500_000,
    refresh_nonce: int = 0,
) -> Dict[str, Any]:
    """Fetch today's official organization Usage + Costs.

    `refresh_nonce` lets the UI force refresh the otherwise 60-second cache.
    """
    del refresh_nonce

    if not admin_key:
        return {"ok": False, "official": False, "error": "OPENAI_ADMIN_KEY is not configured."}
    if OpenAI is None:
        return {"ok": False, "official": False, "error": "openai package is not installed."}

    start_time = int(_utc_start_of_day().timestamp())

    try:
        client = OpenAI(admin_api_key=admin_key)
        usage_response = client.admin.organization.usage.completions(
            start_time=start_time,
            bucket_width="1d",
            limit=1,
            group_by=["model", "service_tier", "project_id"],
        )
        parsed = parse_usage_payload(_to_dict(usage_response), daily_budget=daily_budget)
    except Exception as exc:
        return {"ok": False, "official": False, "error": f"OpenAI Usage API: {exc}"}

    try:
        cost_response = client.admin.organization.usage.costs(
            start_time=start_time,
            bucket_width="1d",
            limit=1,
        )
        parsed.update(parse_cost_payload(_to_dict(cost_response)))
        parsed["cost_ok"] = True
    except Exception as exc:
        parsed["cost_ok"] = False
        parsed["cost_error"] = f"OpenAI Costs API: {exc}"
        parsed["today_cost_usd"] = None

    parsed["synced_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return parsed
