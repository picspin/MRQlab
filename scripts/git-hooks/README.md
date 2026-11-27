# git hooks: config isolation gate

## Install (once per clone)

```bash
git config core.hooksPath scripts/git-hooks
```

This is per clone and is not applied automatically. Every clone that commits must run it.

## Verify

```bash
echo "# test" >> config/settings.yaml   # or any change to .claude/settings.json
git add config/settings.yaml
git commit -m "test: no marker"          # must be rejected (non-zero exit, stderr names [config-change])
git reset HEAD config/settings.yaml && git checkout -- config/settings.yaml
```

## Behavior (commit-msg hook)

- A staged path under `config/` or exactly `.claude/settings.json` (added, modified, renamed, or deleted) with no `[config-change]` in the message is rejected.
- Staged paths are read with `--no-renames -z`, so renames out of the guarded area and non-ASCII names are caught.
- Lines starting with `#` are ignored, because git strips them and a marker there would never reach the final message.
- No guarded path staged: allowed.
- Merge commits (`MERGE_HEAD` present) are allowed. Rejecting them would leave the repo mid-merge. **Accepted risk:** a merge can carry guarded changes without a marker. Those changes were already gated on their own branch.
- `--amend --no-edit` reuses the old message, so a marker from the old message satisfies new guarded changes. **Accepted limitation:** when amending guarded changes, write a new message.
- `[config-change]` is an explicit declaration only. It is **not** an exemption from review.
