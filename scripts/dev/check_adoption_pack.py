#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nornyx.adoption import adoption_status, adoption_summary, validate_adoption_pack, write_lite_nyx  # noqa: E402
from nornyx.checker import check_document, has_errors  # noqa: E402


def validate_clean_downstream_repo() -> list[str]:
    issues: list[str] = []
    with tempfile.TemporaryDirectory(prefix="nornyx-adoption-clean-") as tmp:
        repo = Path(tmp)
        (repo / "README.md").write_text("# Downstream Demo\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")
        out = repo / "nornyx.project.nyx"
        write_lite_nyx("Downstream Demo", out, repo_root=repo)

        data = yaml.safe_load(out.read_text(encoding="utf-8"))
        diagnostics = check_document(data)
        if has_errors(diagnostics):
            issues.append("generated Lite .nyx failed checker in clean downstream repo")

        try:
            write_lite_nyx("Downstream Demo", out, repo_root=repo)
        except FileExistsError:
            pass
        else:
            issues.append("init-lite overwrote an existing file without --force")

    return issues


def main() -> int:
    path = ROOT / "docs" / "backlog" / "nornyx-zero-friction-adoption-pack.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    issues = validate_adoption_pack(data)
    status = adoption_status(ROOT)
    downstream_issues = validate_clean_downstream_repo()
    print(adoption_summary(status))
    print("clean_downstream_lite=passed" if not downstream_issues else "clean_downstream_lite=failed")
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.message}")
    for issue in downstream_issues:
        print(f"ERROR: {issue}")
    return 1 if any(issue.severity == "error" for issue in issues) or downstream_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
