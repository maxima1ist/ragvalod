"""Unit tests for Notion Markdown block formatting."""

import pytest

from ingestion.sources.notion import (
    MarkdownNotionPageReader,
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
