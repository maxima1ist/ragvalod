"""Unit tests for Notion adapter (Markdown formatting + mocked fetch)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from ingestion.sources.notion import (
    MarkdownNotionPageReader,
    NotionDataSource,
    _extract_token,
    _parse_concurrency,
    _parse_id_list,
)


def test_extract_token_aliases() -> None:
    assert _extract_token({"access_key": "ntn_x"}) == "ntn_x"
    assert _extract_token({"integration_token": "secret_y"}) == "secret_y"
    assert _extract_token({}) == ""


def test_parse_id_list() -> None:
    assert _parse_id_list("a, b;c\nd") == ["a", "b", "c", "d"]
    assert _parse_id_list("") == []


def test_parse_concurrency() -> None:
    assert _parse_concurrency("") == 3
    assert _parse_concurrency("5") == 5
    assert _parse_concurrency("99") == 8
    with pytest.raises(ValueError):
        _parse_concurrency("0")


def test_format_heading_and_list() -> None:
    reader = MarkdownNotionPageReader(integration_token="ntn_test")
    heading = reader._format_block(
        "heading_1",
        {"rich_text": [{"plain_text": "RAG basics"}]},
        "",
    )
    assert heading == "# RAG basics"
    bullet = reader._format_block(
        "bulleted_list_item",
        {"rich_text": [{"plain_text": "item"}]},
        "",
    )
    assert bullet == "- item"
    child = reader._format_block("child_page", {"title": "Nested"}, "")
    assert child == "[child page: Nested]"


@pytest.mark.asyncio
async def test_fetch_requires_token() -> None:
    source = NotionDataSource()
    with pytest.raises(ValueError, match="integration_token"):
        await source.fetch({}, {"page_ids": "abc"})


@pytest.mark.asyncio
async def test_fetch_by_page_ids_mocked() -> None:
    reader = MagicMock()
    reader.read_page.side_effect = lambda page_id: f"# Body {page_id}"
    reader.get_page_meta.side_effect = lambda page_id: (
        f"Title {page_id}",
        f"https://notion.so/{page_id}",
        datetime(2026, 1, 2, tzinfo=UTC),
    )

    source = NotionDataSource()
    with patch("ingestion.sources.notion.MarkdownNotionPageReader", return_value=reader):
        docs = await source.fetch(
            {"integration_token": "ntn_test"},
            {"page_ids": "page-a, page-b", "max_concurrency": "1"},
        )

    assert [d.doc_id for d in docs] == ["page-a", "page-b"]
    assert docs[0].title == "Title page-a"
    assert docs[0].content_type == "markdown"
    assert docs[0].source == "notion"
    assert "# Body page-a" in docs[0].text
    assert docs[0].uri.endswith("page-a")
    reader.search_pages.assert_not_called()
    assert reader.read_page.call_count == 2


@pytest.mark.asyncio
async def test_fetch_discovers_via_search_mocked() -> None:
    reader = MagicMock()
    reader.search_pages.return_value = [
        {
            "id": "discovered-1",
            "title": "Found page",
            "url": "https://notion.so/discovered-1",
        }
    ]
    reader.read_page.return_value = "# Discovered"

    source = NotionDataSource()
    progress_calls: list[tuple[int, int, str]] = []
    with patch("ingestion.sources.notion.MarkdownNotionPageReader", return_value=reader):
        docs = await source.fetch(
            {"access_key": "ntn_alias"},
            {"query": "RAG", "max_pages": "5"},
            progress=lambda done, total, detail: progress_calls.append((done, total, detail)),
        )

    assert len(docs) == 1
    assert docs[0].doc_id == "discovered-1"
    assert docs[0].title == "Found page"
    assert docs[0].text == "# Discovered"
    reader.search_pages.assert_called_once_with(query="RAG", max_pages=5)
    reader.get_page_meta.assert_not_called()
    assert progress_calls == [(1, 1, "Found page")]


@pytest.mark.asyncio
async def test_fetch_no_pages_raises() -> None:
    reader = MagicMock()
    reader.search_pages.return_value = []
    source = NotionDataSource()
    with (
        patch("ingestion.sources.notion.MarkdownNotionPageReader", return_value=reader),
        pytest.raises(ValueError, match="no pages"),
    ):
        await source.fetch({"token": "ntn_x"}, {"query": "nothing"})


@pytest.mark.asyncio
async def test_fetch_database_ids_extend_pages() -> None:
    reader = MagicMock()
    reader.query_database.return_value = ["db-page-1"]
    reader.read_page.return_value = "from db"
    reader.get_page_meta.return_value = ("DB page", "https://notion.so/db-page-1", None)

    source = NotionDataSource()
    with patch("ingestion.sources.notion.MarkdownNotionPageReader", return_value=reader):
        docs = await source.fetch(
            {"notion_token": "ntn_x"},
            {"database_ids": "db-1", "max_concurrency": "1"},
        )

    assert [d.doc_id for d in docs] == ["db-page-1"]
    reader.query_database.assert_called_once_with("db-1")
    reader.search_pages.assert_not_called()
