"""Gate 2: deep_review_from_main.sh takes the reviewer rules from main, never the worktree.

Runs the real wrapper in a scratch git repo with a fake `claude` on PATH.
"""
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "deep_review_from_main.sh"
RULE_PATH = ".claude/agents/deep-reviewer.md"

MAIN_RULES = "# Deep Reviewer (main)\n\n5. Validator review: MAIN-MARKER\n"
WORK_RULES = "# Deep Reviewer (worktree)\n\n5. Validator review: WORK-MARKER (relaxed)\n"
CLEAN_VARS = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY")


def _git(repo, *args, input_=None):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, input=input_
    ).stdout


def _clean_env():
    env = os.environ.copy()
    for var in CLEAN_VARS:
        env.pop(var, None)
    return env


def _make_scratch(tmp_path, with_main_rules=True):
    repo = tmp_path / "scratch"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    rule = repo / RULE_PATH
    rule.parent.mkdir(parents=True)
    if with_main_rules:
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


@pytest.fixture()
def fake_claude(tmp_path):
    """Stand-in for `claude -p`: archives stdin, then writes findings per FAKE_MODE."""
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
        '  badjson) printf \'not json\' > "reviews/review-$sha.json" ;;\n'
        '  badstruct) printf \'{"review_sha":"WRONG","findings":1}\' > "reviews/review-$sha.json" ;;\n'
        '  *) printf \'{"review_sha":"%s","findings":[]}\' "$sha" > "reviews/review-$sha.json" ;;\n'
        "esac\n"
    )
    fake.chmod(0o755)
    return bindir, stdin_path


def _run_script(repo, bindir, stdin_path, *args, fake_mode="write"):
    env = _clean_env()
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FAKE_STDIN"] = str(stdin_path)
    env["FAKE_MODE"] = fake_mode
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=repo, env=env, capture_output=True, text=True
    )


def test_injects_main_version_not_worktree(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude

    r = _run_script(repo, bindir, stdin_path)

    assert r.returncode == 0, r.stderr
    prompt = stdin_path.read_text()
    assert "MAIN-MARKER" in prompt
    assert "WORK-MARKER" not in prompt, "worktree rules must never be injected"


def test_missing_main_rules_fails_closed(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path, with_main_rules=False)
    _add_work_branch(repo)  # rules exist only on the work branch
    bindir, stdin_path = fake_claude

    r = _run_script(repo, bindir, stdin_path)

    assert r.returncode != 0
    assert RULE_PATH in r.stderr
    assert not stdin_path.exists(), "must not fall back to calling claude"


def test_review_sha_and_json_output(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude

    r = _run_script(repo, bindir, stdin_path)

    assert r.returncode == 0, r.stderr
    head = _git(repo, "rev-parse", "HEAD").strip()
    assert f"review_sha={head}" in r.stdout
    data = __import__("json").loads((repo / "reviews" / f"review-{head}.json").read_text())
    assert data["review_sha"] == head
    assert data["findings"] == []


def test_prompt_carries_base_sha(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude

    _run_script(repo, bindir, stdin_path)

    head = _git(repo, "rev-parse", "HEAD").strip()
    assert head in stdin_path.read_text(), "dispatch prompt must state the base sha"


def test_no_stale_findings_reuse(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude
    r1 = _run_script(repo, bindir, stdin_path)
    assert r1.returncode == 0, r1.stderr
    head = _git(repo, "rev-parse", "HEAD").strip()
    out = repo / "reviews" / f"review-{head}.json"
    assert out.exists()

    r2 = _run_script(repo, bindir, stdin_path, fake_mode="nowrite")

    assert r2.returncode != 0
    assert "not generated or empty" in r2.stderr
    assert not out.exists(), "wrapper must delete the leftover report before dispatch"


def test_bad_json_fails(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude

    r = _run_script(repo, bindir, stdin_path, fake_mode="badjson")

    assert r.returncode != 0
    assert "validation failed" in r.stderr


def test_bad_structure_fails(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    bindir, stdin_path = fake_claude

    r = _run_script(repo, bindir, stdin_path, fake_mode="badstruct")

    assert r.returncode != 0
    assert "validation failed" in r.stderr


def _add_origin_main(repo, rule_text):
    blob = _git(repo, "hash-object", "-w", "--stdin", input_=rule_text).strip()
    inner = _git(repo, "mktree", input_=f"100644 blob {blob}\tdeep-reviewer.md\n").strip()
    agents = _git(repo, "mktree", input_=f"040000 tree {inner}\tagents\n").strip()
    root = _git(repo, "mktree", input_=f"040000 tree {agents}\t.claude\n").strip()
    commit = _git(repo, "commit-tree", root, "-m", "origin rules", "-p", "HEAD").strip()
    _git(repo, "update-ref", "refs/remotes/origin/main", commit)


def test_origin_rule_divergence_fails(tmp_path, fake_claude):
    repo = _make_scratch(tmp_path)
    _add_work_branch(repo)
    _add_origin_main(repo, WORK_RULES)
    bindir, stdin_path = fake_claude

    r = _run_script(repo, bindir, stdin_path)

    assert r.returncode != 0
    assert "differ" in r.stderr
    assert not stdin_path.exists()
