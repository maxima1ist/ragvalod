"""Unit tests for Google Drive adapter."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ingestion.sources.google_drive import GoogleDriveDataSource, _build_reader


def test_build_reader_requires_credentials() -> None:
    with pytest.raises(ValueError, match="service_account_key"):
        _build_reader({})


def test_build_reader_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        _build_reader({"service_account_key": "{not-json"})


@pytest.mark.asyncio
async def test_fetch_requires_folder_or_files() -> None:
    source = GoogleDriveDataSource()
    with (
        patch("ingestion.sources.google_drive._build_reader", return_value=MagicMock()),
        pytest.raises(ValueError, match="folder_id"),
    ):
        await source.fetch(
            {"service_account_key": json.dumps({"type": "service_account"})},
            {},
        )


@pytest.mark.asyncio
async def test_fetch_maps_documents() -> None:
    reader = MagicMock()
    reader.load_data.return_value = [
        SimpleNamespace(
            doc_id="file-1",
            metadata={
                "file_id": "file-1",
                "file_name": "notes.md",
                "url": "https://drive.google.com/file/d/file-1/view",
            },
            get_content=lambda: "# Hello\n\nWorld",
        )
    ]
    source = GoogleDriveDataSource()
    with patch("ingestion.sources.google_drive._build_reader", return_value=reader):
        docs = await source.fetch(
            {"service_account_key": json.dumps({"type": "service_account", "project_id": "x"})},
            {"folder_id": "folder-abc"},
        )

    assert len(docs) == 1
    assert docs[0].doc_id == "file-1"
    assert docs[0].title == "notes.md"
    assert docs[0].content_type == "markdown"
    assert docs[0].source == "google_drive"
    assert "Hello" in docs[0].text
    reader.load_data.assert_called_once_with(
        folder_id="folder-abc",
        file_ids=None,
        query_string=None,
        drive_id=None,
    )


@pytest.mark.asyncio
async def test_fetch_file_ids_and_query() -> None:
    reader = MagicMock()
    reader.load_data.return_value = [
        SimpleNamespace(
            doc_id="a",
            metadata={"file_id": "a", "file_name": "a.txt"},
            get_content=lambda: "plain",
        )
    ]
    source = GoogleDriveDataSource()
    with patch("ingestion.sources.google_drive._build_reader", return_value=reader):
        docs = await source.fetch(
            {"authorized_user_info": json.dumps({"token": "x", "refresh_token": "y"})},
            {"file_ids": "a, b", "query": "name contains 'test'", "drive_id": "shared"},
        )

    assert len(docs) == 1
    assert docs[0].content_type == "text"
    reader.load_data.assert_called_once_with(
        folder_id=None,
        file_ids=["a", "b"],
        query_string="name contains 'test'",
        drive_id="shared",
    )


def test_build_reader_from_path(tmp_path) -> None:
    key_path = tmp_path / "sa.json"
    key_path.write_text(
        json.dumps({"type": "service_account", "client_email": "x@y"}),
        encoding="utf-8",
    )
    with patch("ingestion.sources.google_drive.GoogleDriveReader") as reader_cls:
        _build_reader({"service_account_key_path": str(key_path)})
    reader_cls.assert_called_once()
    kwargs = reader_cls.call_args.kwargs
    assert kwargs["service_account_key"]["client_email"] == "x@y"
    assert kwargs["is_cloud"] is True
