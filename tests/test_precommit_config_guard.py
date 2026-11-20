"""Gate 1: commit-msg hook hard-isolates config changes behind an explicit marker.

Installs the hook in a scratch git repo exactly as scripts/git-hooks/README.md
documents (git config core.hooksPath) and runs real `git commit` calls.
"""
import subprocess
from pathlib import Path

HOOK_SRC = Path(__file__).resolve().parents[1] / "scripts" / "git-hooks"


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def _init_repo(tmp_path):
    repo = tmp_path / "scratch"
    repo.mkdir()
    _run(["git", "init", "-q"], repo)
    _run(["git", "config", "user.email", "t@t"], repo)
    _run(["git", "config", "user.name", "t"], repo)
    _run(["git", "config", "core.hooksPath", str(HOOK_SRC)], repo)
    (repo / "README.md").write_text("base\n")
    _run(["git", "add", "."], repo)
    r = _run(["git", "commit", "-q", "-m", "init"], repo)
    assert r.returncode == 0, r.stderr
    return repo


def _stage(repo, rel, content="x: 1\n"):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _run(["git", "add", rel], repo)


def test_config_change_without_marker_rejected(tmp_path):
    repo = _init_repo(tmp_path)
    _stage(repo, "config/settings.yaml")
    r = _run(["git", "commit", "-m", "test: no marker"], repo)
    assert r.returncode != 0
    assert "[config-change]" in r.stderr
    assert "init" in _run(["git", "log", "--oneline", "-1"], repo).stdout


def test_config_change_with_marker_allowed(tmp_path):
    repo = _init_repo(tmp_path)
    _stage(repo, "config/settings.yaml")
    r = _run(["git", "commit", "-m", "test: cfg [config-change]"], repo)
    assert r.returncode == 0, r.stderr


def test_normal_commit_without_config_allowed(tmp_path):
    repo = _init_repo(tmp_path)
    _stage(repo, "src.txt", "hi\n")
    r = _run(["git", "commit", "-m", "test: normal"], repo)
    assert r.returncode == 0, r.stderr


def test_config_delete_without_marker_rejected(tmp_path):
    repo = _init_repo(tmp_path)
    _stage(repo, "config/settings.yaml")
    _run(["git", "commit", "-q", "-m", "add cfg [config-change]"], repo)
    (repo / "config" / "settings.yaml").unlink()
    _run(["git", "add", "-A", "config/"], repo)
    r = _run(["git", "commit", "-m", "test: delete cfg no marker"], repo)
    assert r.returncode != 0


def test_rename_out_of_config_without_marker_rejected(tmp_path):
    # --name-only without --no-renames lists only the new path, letting a move out of config/ escape.
    repo = _init_repo(tmp_path)
    _stage(repo, "config/settings.yaml")
    _run(["git", "commit", "-q", "-m", "add cfg [config-change]"], repo)
    (repo / "config" / "settings.yaml").rename(repo / "settings.yaml")
    _run(["git", "add", "-A"], repo)
    r = _run(["git", "commit", "-m", "rename out no marker"], repo)
    assert r.returncode != 0


def test_non_ascii_config_name_without_marker_rejected(tmp_path):
    # core.quotePath=true would print "config/\344..." which does not match ^config/.
    repo = _init_repo(tmp_path)
    _stage(repo, "config/中文.yaml")
    r = _run(["git", "commit", "-m", "nonascii no marker"], repo)
    assert r.returncode != 0


def test_claude_settings_change_without_marker_rejected(tmp_path):
    # The review gates' own wiring lives in .claude/settings.json; weakening it must be declared.
    repo = _init_repo(tmp_path)
    _stage(repo, ".claude/settings.json", "{}\n")
    r = _run(["git", "commit", "-m", "loosen hooks"], repo)
    assert r.returncode != 0


def test_comment_line_marker_not_recognized(tmp_path):
    repo = _init_repo(tmp_path)
    _stage(repo, "config/settings.yaml")
    msg = repo / "msg.txt"
    msg.write_text("test: no marker\n#[config-change] in comment\n")
    r = _run(["git", "commit", "-F", str(msg)], repo)
    assert r.returncode != 0
    assert "[config-change]" in r.stderr


def test_merge_commit_is_not_blocked_by_hook(tmp_path):
    # Merge commits are exempt (rejecting them would strand the repo mid-merge); see README.
    hook = (HOOK_SRC / "commit-msg").read_text()
    assert "MERGE_HEAD" in hook


def test_hook_install_doc_matches_command():
    readme = (HOOK_SRC / "README.md").read_text()
    assert "git config core.hooksPath scripts/git-hooks" in readme
