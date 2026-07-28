"""Thin HTTP client for Cliniko REST API — auth, pagination, retry (Docs/07)."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ClinikoClientError(Exception):
    """Raised when Cliniko HTTP calls fail after retries."""


class ClinikoClient:
    """HTTP only — no mapping / business logic."""

    def __init__(self) -> None:
        self.base_url = settings.CLINIKO_BASE_URL.rstrip("/")
        self.api_key = settings.CLINIKO_API_KEY
        self.session = requests.Session()
        self.session.auth = (self.api_key, "")
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "ClinicBook (appointment-booking-eval)",
            }
        )

    def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(self, path: str, payload: dict) -> dict[str, Any]:
        return self._request("POST", path, json=payload)

    def delete(self, path: str) -> None:
        self._request("DELETE", path, expect_json=False)

    def list_all(self, collection_key: str, path: str, params: dict | None = None) -> list[dict]:
        """Follow Cliniko pagination via links.next."""
        params = dict(params or {})
        params.setdefault("per_page", 100)
        items: list[dict] = []
        data = self.get(path, params=params)
        items.extend(data.get(collection_key) or [])
        next_url = (data.get("links") or {}).get("next")
        while next_url:
            data = self._request_absolute("GET", next_url)
            items.extend(data.get(collection_key) or [])
            next_url = (data.get("links") or {}).get("next")
        return items

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return self._request_absolute(
            method, url, params=params, json=json, expect_json=expect_json
        )

    def _request_absolute(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise ClinikoClientError("CLINIKO_API_KEY is not configured.")

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.request(
                    method, url, params=params, json=json, timeout=30
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    time.sleep(0.5 * (attempt + 1))
                    last_error = ClinikoClientError(
                        f"Cliniko {response.status_code}: {response.text[:200]}"
                    )
                    continue
                if response.status_code >= 400:
                    raise ClinikoClientError(
                        f"Cliniko {response.status_code}: {response.text[:300]}"
                    )
                if not expect_json or response.status_code == 204 or not response.content:
                    return {}
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(0.5 * (attempt + 1))
        raise ClinikoClientError(str(last_error) if last_error else "Cliniko request failed")
