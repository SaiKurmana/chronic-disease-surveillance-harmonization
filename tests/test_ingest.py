"""Unit tests for the ingestion layer (no network)."""

from __future__ import annotations

import json

import pandas as pd
import pytest
import requests

from ingest import storage
from ingest.pipeline import ingest_spec
from ingest.registry import DatasetSpec, load_sources
from ingest.socrata import SocrataClient, SocrataError


class FakeResponse:
    def __init__(self, status: int, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeSession:
    """Serves a fixed table through SODA-style $limit/$offset paging."""

    def __init__(self, rows, fail_first: int = 0, status_on_fail: int = 503):
        self.rows = rows
        self.fail_first = fail_first
        self.status_on_fail = status_on_fail
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if self.fail_first > 0:
            self.fail_first -= 1
            return FakeResponse(self.status_on_fail, {})
        if url.endswith(".json") and "/api/views/" in url:
            return FakeResponse(
                200,
                {
                    "name": "Fake",
                    "rowsUpdatedAt": 123,
                    "columns": [{"fieldName": "a"}, {"fieldName": "b"}, {"fieldName": ":id"}],
                },
            )
        params = params or {}
        if params.get("$select", "").startswith("count"):
            return FakeResponse(200, [{"n": str(len(self.rows))}])
        off, lim = int(params["$offset"]), int(params["$limit"])
        return FakeResponse(200, self.rows[off : off + lim])


def make_client(session, **kw):
    return SocrataClient(session=session, sleep=lambda s: None, **kw)


def test_paging_collects_all_rows():
    rows = [{"a": str(i)} for i in range(25)]
    client = make_client(FakeSession(rows))
    got = client.fetch_all("abcd-1234", page_size=10)
    assert [r["a"] for r in got] == [str(i) for i in range(25)]


def test_paging_orders_by_system_id():
    session = FakeSession([{"a": "1"}])
    make_client(session).fetch_all("abcd-1234", page_size=10)
    assert session.calls[0][1]["$order"] == ":id"


def test_retries_on_server_error_then_succeeds():
    session = FakeSession([{"a": "1"}], fail_first=2)
    rows = make_client(session, max_retries=3).fetch_all("abcd-1234")
    assert rows == [{"a": "1"}]
    assert len(session.calls) == 3


def test_gives_up_after_max_retries():
    session = FakeSession([], fail_first=10)
    with pytest.raises(SocrataError):
        make_client(session, max_retries=2).fetch_all("abcd-1234")


def test_client_error_is_not_retried():
    session = FakeSession([], fail_first=10, status_on_fail=400)
    with pytest.raises(SocrataError):
        make_client(session, max_retries=5).fetch_all("abcd-1234")
    assert len(session.calls) == 1


def test_snapshot_keeps_all_null_columns_and_provenance(tmp_path):
    out = storage.write_snapshot(
        "demo",
        [{"a": "x"}],
        dataset_id="abcd-1234",
        where=None,
        rows_updated_at=1,
        root=tmp_path,
        columns=["a", "b"],
    )
    df = pd.read_parquet(out)
    assert {"a", "b", "_source_key", "_dataset_id", "_loaded_at"} <= set(df.columns)
    assert df["b"].isna().all()
    manifest = json.loads((tmp_path / "_manifest.json").read_text())
    assert manifest["demo"]["rows"] == 1


def test_ingest_is_idempotent(tmp_path):
    spec = DatasetSpec(
        key="demo", domain="x", name="n", dataset_id="abcd-1234", url="u", publisher="p"
    )
    session = FakeSession([{"a": "1"}, {"a": "2"}])
    client = make_client(session)
    first = ingest_spec(spec, client, root=tmp_path)
    second = ingest_spec(spec, client, root=tmp_path)
    assert first is not None and first.exists()
    assert second is None  # unchanged upstream -> skipped
    forced = ingest_spec(spec, client, root=tmp_path, force=True)
    assert forced is not None


def test_sources_registry_is_complete():
    specs = load_sources()
    assert {s.domain for s in specs} == {"diabetes", "vision", "kidney"}
    for s in specs:
        assert s.url == f"https://data.cdc.gov/d/{s.dataset_id}"
        assert s.extra.get("access_date"), s.key
        assert s.publisher
