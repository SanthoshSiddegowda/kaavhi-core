from __future__ import annotations

from typing import Any

import httpx

from app.config.app import settings

BUGZILLA_REST_BASE = "https://bugzilla.bizom.in/rest"

REGRESSION_COMPONENTS = [
    "API",
    "Aqua",
    "Backend",
    "Bizom IOS",
    "BizomNext",
    "Bourbon",
    "Cross Platform",
    "Custom Feature",
    "Distiman",
    "MDM (Changes)",
    "MDM (New)",
    "RetailerApp",
    "Sadafco",
    "Templates (Changes)",
    "Templates (New)",
    "UI",
    "Windows Phone",
]

REGRESSION_PRIORITIES = ["Highest", "High", "Normal", "Low", "Lowest", "---"]

REGRESSION_SEVERITIES = [
    "blocker",
    "critical",
    "major",
    "normal",
    "minor",
    "trivial",
    "enhancement",
]


def _build_regression_params(version: str, chfieldfrom: str, chfieldto: str) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [
        ("api_key", settings.BUGZILLA_API_KEY),
        ("bug_status", "RESOLVED"),
        ("bug_status", "VERIFIED"),
        ("resolution", "RELEASED"),
        ("resolution", "FIXED"),
        ("chfield", "[Bug creation]"),
        ("chfieldfrom", chfieldfrom),
        ("chfieldto", chfieldto),
        ("f1", "cf_type"),
        ("f2", "cf_isregression"),
        ("o1", "notequals"),
        ("o2", "equals"),
        ("v1", "internal"),
        ("v2", "Yes"),
        ("version", version),
        ("product", "BizomWeb"),
        ("product", "Mobile App"),
    ]

    for priority in REGRESSION_PRIORITIES:
        params.append(("priority", priority))
    for severity in REGRESSION_SEVERITIES:
        params.append(("bug_severity", severity))
    for component in REGRESSION_COMPONENTS:
        params.append(("component", component))

    return params


async def fetch_regression_bugs(version: str, chfieldfrom: str, chfieldto: str) -> dict[str, Any]:
    params = _build_regression_params(version, chfieldfrom, chfieldto)
    url = f"{BUGZILLA_REST_BASE}/bug"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
