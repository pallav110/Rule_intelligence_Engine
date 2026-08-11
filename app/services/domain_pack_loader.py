from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DomainPackNotFoundError(FileNotFoundError):
    pass


class DomainPackLoader:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]
        self.domain_packs_root = self.repo_root / "rie-ml" / "domain-packs"

    def list_available_packs(self) -> list[dict[str, Any]]:
        packs: list[dict[str, Any]] = []
        if not self.domain_packs_root.exists():
            return packs

        for pack_dir in sorted(path for path in self.domain_packs_root.iterdir() if path.is_dir()):
            config_path = pack_dir / "domain_config.json"
            if not config_path.exists():
                continue
            config = self._load_json(config_path)
            packs.append(
                {
                    "domain_pack_id": config.get("domain_pack_id", pack_dir.name),
                    "version": config.get("version"),
                    "display_name": config.get("display_name", pack_dir.name),
                    "description": config.get("description"),
                }
            )
        return packs

    def load_domain_config(self, pack_id: str) -> dict[str, Any]:
        return self._load_pack_file(pack_id, "domain_config.json")

    def load_schema(self, pack_id: str) -> dict[str, Any]:
        return self._load_pack_file(pack_id, "schema/schema.json")

    def load_relationships(self, pack_id: str) -> dict[str, Any]:
        return self._load_pack_file(pack_id, "schema/relationships.json")

    def load_taxonomy(self, pack_id: str) -> dict[str, Any]:
        return self._load_pack_file(pack_id, "taxonomy/labels.json")

    def load_glossary(self, pack_id: str) -> str:
        glossary_path = self._get_pack_path(pack_id) / "documentation" / "business_glossary.md"
        if not glossary_path.exists():
            raise DomainPackNotFoundError(f"Glossary not found for domain pack '{pack_id}'")
        return glossary_path.read_text(encoding="utf-8")

    def _load_pack_file(self, pack_id: str, relative_path: str) -> dict[str, Any]:
        file_path = self._get_pack_path(pack_id) / relative_path
        return self._load_json(file_path)

    def _get_pack_path(self, pack_id: str) -> Path:
        pack_path = self.domain_packs_root / pack_id
        if not pack_path.exists():
            raise DomainPackNotFoundError(f"Domain pack '{pack_id}' was not found")
        return pack_path

    def _load_json(self, file_path: Path) -> dict[str, Any]:
        if not file_path.exists():
            raise DomainPackNotFoundError(f"Domain pack file not found: {file_path}")
        with file_path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)