"""Adapter registry / factory."""

from __future__ import annotations

from dataclasses import dataclass

from ingestion.config import Settings
from ingestion.sources.base import DataSource
from ingestion.sources.local_files import LocalFilesDataSource
from ingestion.sources.notion import NotionDataSource


@dataclass(frozen=True, slots=True)
class SourceInfo:
    name: str
    description: str
    requires_credentials: bool


class SourceFactory:
    def __init__(self, settings: Settings) -> None:
        self._adapters: dict[str, DataSource] = {
            LocalFilesDataSource.name: LocalFilesDataSource(settings.local_files_dir),
            NotionDataSource.name: NotionDataSource(),
        }

    def list_sources(self) -> list[SourceInfo]:
        return [
            SourceInfo(
                name=adapter.name,
                description=adapter.description,
                requires_credentials=adapter.requires_credentials,
            )
            for adapter in self._adapters.values()
        ]

    def get(self, name: str) -> DataSource:
        try:
            return self._adapters[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._adapters))
            raise KeyError(f"unknown source adapter '{name}'; known: {known}") from exc

    def resolve_job_sources(
        self,
        requested: list[tuple[str, dict[str, str], dict[str, str]]],
        all_with_credentials: bool,
    ) -> list[tuple[DataSource, dict[str, str], dict[str, str]]]:
        """Build concrete (adapter, credentials, options) list for a job.

        requested items are (name, credentials, options).
        """
        by_name = {name: (creds, opts) for name, creds, opts in requested}

        if all_with_credentials:
            selected: list[tuple[DataSource, dict[str, str], dict[str, str]]] = []
            for info in self.list_sources():
                adapter = self.get(info.name)
                creds, opts = by_name.get(info.name, ({}, {}))
                if info.requires_credentials and not creds:
                    continue
                selected.append((adapter, creds, opts))
            return selected

        selected = []
        for name, creds, opts in requested:
            adapter = self.get(name)
            if adapter.requires_credentials and not creds:
                raise ValueError(f"source '{name}' requires credentials")
            selected.append((adapter, creds, opts))
        return selected
