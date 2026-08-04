"""Unit tests for source factory."""

import pytest

from ingestion.config import Settings
from ingestion.sources.factory import SourceFactory


def test_list_includes_local_files_and_notion() -> None:
    factory = SourceFactory(Settings())
    names = {info.name for info in factory.list_sources()}
    assert "local_files" in names
    assert "notion" in names
    local = next(i for i in factory.list_sources() if i.name == "local_files")
    notion = next(i for i in factory.list_sources() if i.name == "notion")
    assert local.requires_credentials is False
    assert notion.requires_credentials is True


def test_resolve_explicit_local_files() -> None:
    factory = SourceFactory(Settings())
    items = factory.resolve_job_sources(
        [("local_files", {}, {"path": "/data"})],
        all_with_credentials=False,
    )
    assert len(items) == 1
    assert items[0][0].name == "local_files"


def test_unknown_source_raises() -> None:
    factory = SourceFactory(Settings())
    with pytest.raises(KeyError):
        factory.resolve_job_sources([("nope", {}, {})], all_with_credentials=False)


def test_all_with_credentials_includes_no_cred_adapters() -> None:
    factory = SourceFactory(Settings())
    items = factory.resolve_job_sources([], all_with_credentials=True)
    assert any(adapter.name == "local_files" for adapter, _, _ in items)
    assert not any(adapter.name == "notion" for adapter, _, _ in items)


def test_notion_requires_credentials() -> None:
    factory = SourceFactory(Settings())
    with pytest.raises(ValueError, match="requires credentials"):
        factory.resolve_job_sources([("notion", {}, {})], all_with_credentials=False)


def test_resolve_notion_with_token() -> None:
    factory = SourceFactory(Settings())
    items = factory.resolve_job_sources(
        [("notion", {"integration_token": "ntn_x"}, {"page_ids": "abc"})],
        all_with_credentials=False,
    )
    assert items[0][0].name == "notion"
    assert items[0][1]["integration_token"] == "ntn_x"
