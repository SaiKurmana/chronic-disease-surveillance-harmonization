"""Minimal Socrata (SODA 2.x) client with paging and retries.

Only public endpoints on data.cdc.gov are used. An optional app token can be
supplied with the SOCRATA_APP_TOKEN environment variable to raise rate limits.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from typing import Any

import requests

log = logging.getLogger(__name__)

DEFAULT_DOMAIN = "data.cdc.gov"
CATALOG_URL = "https://api.us.socrata.com/api/catalog/v1"
USER_AGENT = "chronic-disease-surveillance-harmonization/1.0 (portfolio project)"


class SocrataError(RuntimeError):
    """Raised when a request keeps failing after all retries."""


class SocrataClient:
    def __init__(
        self,
        domain: str = DEFAULT_DOMAIN,
        *,
        timeout: float = 60.0,
        max_retries: int = 5,
        backoff_base: float = 2.0,
        session: requests.Session | None = None,
        sleep=time.sleep,
    ) -> None:
        self.domain = domain
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = sleep
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        token = os.environ.get("SOCRATA_APP_TOKEN")
        if token:
            self.session.headers["X-App-Token"] = token

    # -- low level -------------------------------------------------------
    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(
                        f"HTTP {resp.status_code} from {url}", response=resp
                    )
                resp.raise_for_status()
                return resp.json()
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                # 4xx other than 429 is a caller error -> do not retry
                if status is not None and 400 <= status < 500 and status != 429:
                    raise SocrataError(f"{url} failed with HTTP {status}: {exc}") from exc
                last_exc = exc
                wait = self.backoff_base ** attempt
                log.warning(
                    "request failed (attempt %d/%d): %s; retrying in %.0fs",
                    attempt, self.max_retries, exc, wait,
                )
                if attempt < self.max_retries:
                    self._sleep(wait)
        raise SocrataError(f"{url} failed after {self.max_retries} attempts") from last_exc

    # -- public API ------------------------------------------------------
    def metadata(self, dataset_id: str) -> dict[str, Any]:
        """View metadata (name, columns, rowsUpdatedAt, license, ...)."""
        return self._get(f"https://{self.domain}/api/views/{dataset_id}.json")

    def count(self, dataset_id: str, where: str | None = None) -> int:
        params: dict[str, Any] = {"$select": "count(*) AS n"}
        if where:
            params["$where"] = where
        rows = self._get(self._resource(dataset_id), params)
        return int(rows[0]["n"])

    def iter_pages(
        self,
        dataset_id: str,
        *,
        where: str | None = None,
        select: str | None = None,
        page_size: int = 50_000,
    ) -> Iterator[list[dict[str, Any]]]:
        """Yield pages of rows ordered by the system :id column (stable paging)."""
        offset = 0
        while True:
            params: dict[str, Any] = {
                "$limit": page_size,
                "$offset": offset,
                "$order": ":id",
            }
            if where:
                params["$where"] = where
            if select:
                params["$select"] = select
            page = self._get(self._resource(dataset_id), params)
            if not page:
                return
            log.info("%s: fetched %d rows (offset %d)", dataset_id, len(page), offset)
            yield page
            if len(page) < page_size:
                return
            offset += page_size

    def fetch_all(self, dataset_id: str, **kwargs) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in self.iter_pages(dataset_id, **kwargs):
            rows.extend(page)
        return rows

    def search_catalog(self, query: str, limit: int = 25) -> list[dict[str, Any]]:
        data = self._get(
            CATALOG_URL,
            {"domains": self.domain, "q": query, "limit": limit, "only": "dataset"},
        )
        return data.get("results", [])

    def _resource(self, dataset_id: str) -> str:
        return f"https://{self.domain}/resource/{dataset_id}.json"
