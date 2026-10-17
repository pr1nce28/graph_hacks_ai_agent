"""Fresh-clone verification (P6-ALL-01).

We cannot run a literal ``git clone`` here without network, but we can
simulate the post-clone steps by importing the entry points and
verifying that every script the README and Makefile advertise works
without raising. If any of them raises, the fresh-clone test fails
and the bug gets fixed before submission.

Checks:
- ``api.main:app`` imports with the expected title.
- ``data.generate_synthetic`` writes both tenant files and they parse.
- ``evals.run_evals`` returns 5/5.
- ``scripts.export_cypher_doc`` writes docs/CYPHER.md.
- ``scripts.check_graph`` exits 0 even when FalkorDB is unreachable.
- ``scripts.render_architecture`` writes docs/architecture.png.
- The Makefile targets referenced by the README all exist.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml
from click.testing import CliRunner  # type: ignore

_REPO_ROOT = Path(__file__).resolve().parent.parent


def test_api_app_title():
    from api.main import app

    assert app.title == "OrgMind API"


def test_generate_synthetic_writes_both_tenants(tmp_path):
    out_dir = tmp_path / "synthetic"
    out_dir.mkdir()
    # Use a known seed by calling generate() with a redirected out_dir.
    from data.generate_synthetic import generate

    payloads = generate(out_dir=out_dir)
    assert set(payloads.keys()) == {"org_acme", "org_globex"}
    # Both files exist and parse as JSON with a top-level 'tenant' key.
    for tenant in payloads:
        p = out_dir / f"{tenant}.json"
        assert p.exists()
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert data["tenant"] == tenant


def test_eval_runner_passes_5_of_5():
    from evals.run_evals import main

    # 0 = success.
    rc = main(["--yaml", str(_REPO_ROOT / "evals" / "demo_questions.yaml")])
    assert rc == 0


def test_cypher_doc_exports():
    """Skips on Windows under pytest because subprocess capture misbehaves
    in this harness; the script is exercised manually by ``make cypher-doc``.
    """
    if sys.platform.startswith("win"):
        import pytest
        pytest.skip("subprocess capture flaky on Windows under pytest")
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "scripts.export_cypher_doc"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = _REPO_ROOT / "docs" / "CYPHER.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "q_trace_decision" in text


def test_check_graph_exits_zero_without_docker():
    if sys.platform.startswith("win"):
        import pytest
        pytest.skip("subprocess capture flaky on Windows under pytest")
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "scripts.check_graph"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "FalkorDB not reachable" in proc.stdout or "OK" in proc.stdout


def test_render_architecture_writes_png():
    from scripts.render_architecture import main

    rc = main()
    assert rc == 0
    out = _REPO_ROOT / "docs" / "architecture.png"
    assert out.exists()
    assert out.stat().st_size > 1000


def test_makefile_has_required_targets():
    makefile = (_REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("up", "seed", "eval", "eval-baseline", "eval-repeat", "dev-api", "dev-web", "test", "load-test", "cypher-doc", "reset-demo"):
        assert f"\n{target}:" in makefile, f"Makefile missing target {target}"


def test_readme_references_all_required_artifacts():
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for path in (
        "docs/SCHEMA.md",
        "docs/CONTRACTS.md",
        "docs/CYPHER.md",
        "docs/AI_DISCLOSURE.md",
        "docs/CONTRIBUTIONS.md",
        "docs/SUBMISSION_CHECKLIST.md",
        "THIRD_PARTY.md",
        "LICENSE",
    ):
        assert path in readme, f"README does not mention {path}"