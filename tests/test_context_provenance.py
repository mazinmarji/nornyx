from __future__ import annotations

from pathlib import Path

from nornyx.context_builder import build_context_pack


def test_context_pack_records_provenance_and_trust_boundaries(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "spec.md").write_text("authoritative spec\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("working notes\n", encoding="utf-8")
    doc = {
        "contexts": [
            {
                "name": "RepoContext",
                "include": ["docs/**/*.md", "notes.md"],
                "authority": ["docs/spec.md"],
                "taint": {
                    "repo": "trusted_repo_file",
                    "authoritative_repo": "authoritative_repo_file",
                },
            }
        ]
    }

    pack = build_context_pack(doc, tmp_path)
    by_path = {entry["path"]: entry for entry in pack["entries"]}

    assert pack["schema"] == "nornyx.context_pack.v0.1"
    assert pack["trust_models"][0]["authority_order"] == ["docs/spec.md"]
    assert "Untrusted channels cannot override policy" in pack["rules"][1]
    assert by_path["docs/spec.md"]["channel"] == "authoritative_repo"
    assert by_path["docs/spec.md"]["authority_rank"] == 1
    assert by_path["docs/spec.md"]["may_define_policy"] is True
    assert by_path["docs/spec.md"]["provenance"]["source_uri"] == "repo://docs/spec.md"
    assert by_path["notes.md"]["channel"] == "repo"
    assert by_path["notes.md"]["may_define_policy"] is False


def test_context_pack_content_keeps_provenance_for_text_and_binary(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_bytes(b"hello\n")
    (tmp_path / "blob.bin").write_bytes(b"\xff\xfe")
    doc = {"contexts": [{"name": "All", "include": ["README.md", "blob.bin"]}]}

    pack = build_context_pack(doc, tmp_path, include_content=True)
    by_path = {entry["path"]: entry for entry in pack["entries"]}

    assert by_path["README.md"]["content"] == "hello\n"
    assert by_path["blob.bin"]["content"] == "<binary omitted>"
    assert by_path["blob.bin"]["provenance"]["bytes"] == 2
