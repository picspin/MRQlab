"""Gate 3: every deep-review report is bound to the commit it reviewed.

Covers the read side (scripts/check_review_fresh.py) and the write side
(the wrapper stamps review_sha / region / stale into the JSON).
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "scripts" / "deep_review_from_main.sh"
FRESH_CHECK = REPO_ROOT / "scripts" / "check_review_fresh.py"
RULE_PATH = ".claude/agents/deep-reviewer.md"
MAIN_RULES = "# Deep Reviewer (main)\n\n5. Validator review: MAIN-MARKER\n"
WORK_RULES = "# Deep Reviewer (worktree)\n\n5. Validator review: WORK-MARKER\n"


def _git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def _clean_env():
    env = os.environ.copy()
    for var in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY"):
        env.pop(var, None)
    return env


def _make_scratch(tmp_path):
    repo = tmp_path / "scratch"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    rule = repo / RULE_PATH
    rule.parent.mkdir(parents=True)
    rule.write_text(MAIN_RULES)
    (repo / "f.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "main base")
    return repo


def _add_work_branch(repo):
    _git(repo, "checkout", "-b", "work")
    (repo / RULE_PATH).write_text(WORK_RULES)
    (repo / "g.txt").write_text("y\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "worktree-relaxed")


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture()
def fake_claude(tmp_path):
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    stdin_path = tmp_path / "fake-claude-stdin.md"
    fake = bindir / "claude"
    fake.write_text(
        "#!/bin/sh\n"
        'cat > "${FAKE_STDIN:?FAKE_STDIN required}"\n'
        'sha=$(git rev-parse HEAD)\n'
        'mkdir -p reviews\n'
        'case "${FAKE_MODE:-write}" in\n'
        "  nowrite) exit 0 ;;\n"
        '  movelate) printf \'{"review_sha":"%s","findings":[]}\' "$sha" > "reviews/review-$sha.json" &&'
        ' git -c user.email=t@example.com -c user.name=t commit -q --allow-empty -m "moved";;\n'
        '  missingfield) printf \'{"review_sha":"%s","findings":[{"severity":"major",'
        '"file":"src/x.py","line":12}]}\' "$sha" > "reviews/review-$sha.json" ;;\n'
        '  nullfield) printf \'{"review_sha":"%s","findings":[{"severity":"major",'
        '"file":"src/x.py","line":12,"evidence":null,"suggestion":"s"}]}\' "$sha" > "reviews/review-$sha.json" ;;\n'
        '  *) printf \'{"review_sha":"%s","findings":[{"severity":"major",'
        '"file":"src/x.py","line":12,"evidence":"e","suggestion":"s"}]}\' "$sha" > "reviews/review-$sha.json" ;;\n'
        "esac\n"
    )
    fake.chmod(0o755)
    return bindir, stdin_path


def _run_wrapper(repo, bindir, stdin_path, *args, fake_mode="write"):
    env = _clean_env()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FAKE_STDIN"] = str(stdin_path)
    env["FAKE_MODE"] = fake_mode
    return subprocess.run(
        ["bash", str(WRAPPER), *args], cwd=repo, env=env, capture_output=True, text=True, check=False
    )


def _fresh(repo, report):
    return subprocess.run(
        ["python3", str(FRESH_CHECK), str(report)], cwd=repo, capture_output=True, text=True, check=False
    )


# --- check_review_fresh.py (read side) --------------------------------------


def test_fresh_report_exits_zero(tmp_path):
    repo = _make_scratch(tmp_path)
    head = _head(repo)
    report = repo / "reviews" / f"review-{head}.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"review_sha": head, "findings": [], "stale": False}))

    r = _fresh(repo, report)

    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "FRESH"


def test_head_moved_is_stale_and_prints_both_shas(tmp_path):
    repo = _make_scratch(tmp_path)
    old = _head(repo)
    report = repo / "reviews" / f"review-{old}.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"review_sha": old, "findings": [], "stale": False}))
    _git(repo, "commit", "--allow-empty", "-m", "moved after review")

    r = _fresh(repo, report)

    assert r.returncode != 0
    assert "STALE" in r.stdout
    assert old in r.stdout and _head(repo) in r.stdout


def test_stale_flag_wins_even_if_sha_matches(tmp_path):
    repo = _make_scratch(tmp_path)
    head = _head(repo)
    report = repo / "reviews" / f"review-{head}.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"review_sha": head, "findings": [], "stale": True}))

    r = _fresh(repo, report)

    assert r.returncode != 0
    assert "STALE" in r.stdout


def test_missing_report_is_stale(tmp_path):
    repo = _make_scratch(tmp_path)
    r = _fresh(repo, repo / "reviews" / "review-none.json")
    assert r.returncode != 0
    assert "STALE" in r.stdout


def test_invalid_json_is_stale(tmp_path):
    repo = _make_scratch(tmp_path)
    report = repo / "reviews" / "review-bad.json"
    report.parent.mkdir()
    report.write_text("not json")
    r = _fresh(repo, report)
    assert r.returncode != 0
    assert "STALE" in r.stdout


def test_non_object_json_is_stale_without_traceback(tmp_path):
    repo = _make_scratch(tmp_path)
    report = repo / "reviews" / "review-arr.json"
    report.parent.mkdir()
    report.write_text("[]")
    r = _fresh(repo, report)
    assert r.returncode != 0
    assert "STALE" in r.stdout
    assert "Traceback" not in r.stderr


# --- wrapper output (write side) --------------------------------------------


def test_wrapper_writes_full_schema(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude

    r = _run_wrapper(repo, bindir, stdin_path, "work")

    assert r.returncode == 0, r.stdout + r.stderr
    head = _head(repo)
    data = json.loads((repo / "reviews" / f"review-{head}.json").read_text())
    assert data["review_sha"] == head
    assert data["region"] == "work"
    assert data["stale"] is False
    findings = data["findings"]
    assert len(findings) == 1
    for key in ("severity", "file", "line", "evidence", "suggestion"):
        assert key in findings[0], f"missing finding field: {key}"
    assert findings[0]["resolved_in_commit"] is None


def test_wrapper_marks_stale_when_head_moves_during_review(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    review_head = _head(repo)
    bindir, stdin_path = fake_claude

    r = _run_wrapper(repo, bindir, stdin_path, "work", fake_mode="movelate")

    assert r.returncode == 0, r.stdout + r.stderr
    assert "STALE" in r.stdout
    data = json.loads((repo / "reviews" / f"review-{review_head}.json").read_text())
    assert data["stale"] is True
    assert data["review_sha"] == review_head


def test_wrapper_fresh_when_head_unchanged(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    review_head = _head(repo)
    bindir, stdin_path = fake_claude

    r = _run_wrapper(repo, bindir, stdin_path, "work")

    assert r.returncode == 0, r.stdout + r.stderr
    assert "STALE" not in r.stdout
    data = json.loads((repo / "reviews" / f"review-{review_head}.json").read_text())
    assert data["stale"] is False


def test_wrapper_rejects_finding_missing_field(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude

    r = _run_wrapper(repo, bindir, stdin_path, "work", fake_mode="missingfield")

    assert r.returncode != 0
    assert "validation failed" in r.stderr


def test_wrapper_rejects_finding_null_field(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude

    r = _run_wrapper(repo, bindir, stdin_path, "work", fake_mode="nullfield")

    assert r.returncode != 0
    assert "validation failed" in r.stderr


def test_reviews_dir_is_gitignored():
    r = subprocess.run(
        ["git", "check-ignore", "-q", "reviews/review-x.json"],
        cwd=REPO_ROOT, capture_output=True, check=False,
    )
    assert r.returncode == 0, "reviews/ must be ignored as run output"
