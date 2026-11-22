# Coding validation workflow

For each coding change, select checks from the changed behavior and record their
results: write a failing regression first, exercise properties or invariants over
varied inputs, compare against an independent reference or a frozen baseline when
applicable, and walk through failure paths and compatibility as a shadow review.
Use the staged-diff checklist to identify additional areas for review. A checklist
is a prompt, not evidence that the review or tests occurred.

`python3 scripts/check_staged.py` checks the staged diff for whitespace errors
and prints area-specific review prompts. `.githooks/pre-commit` invokes the same
check when present and also runs the base branch's diff-triggered validation.
Run a commit with `git -c core.hooksPath=.githooks commit ...` to use it
without changing shared Git configuration; integrate it with any existing hook
before configuring it persistently. The staged-diff script itself does not run
tests or invoke a PR reviewer; the combined hook executes the base validation checks.
`tests/test_staged_validation_hook.py` exercises actual commits in an isolated Git
repository, including a rejected whitespace error.

The catalog fixture was exported from the code at `337cd8a`, not generated from
the implementation under test. The differential test protects the complete
serialized values of both existing entries while permitting explicitly added
entries. An intentional change to an existing entry requires review and a
deliberate baseline update. The seeded invariant test uses Python's standard
library, not Hypothesis; it is repeatable but does not shrink failing cases.

## Shadow walkthrough for this slice

- New duplicate identifiers: checked target, reference and confounder lists,
  recipe constraint and robustness IDs, and scanner-default names. Each is
  checked within its own collection; names in separate scopes may coincide.
- Baseline comparison: the two old recipes must remain present and match all
  serialized fields. The fixture does not independently validate clinical or
  physical correctness, and a coordinated fixture change can alter the baseline.
- Hook failure paths: an invalid staged diff rejects a commit; the A-line
  checklist's area prompts are not test results. The combined hook also runs the
  base branch's validation gate. The smoke test does not install or replace the user's
  actual hooks, and does not exercise Codex's PR automation.
- Coverage limits: the generated cases cover these catalog contracts, not all
  MRI algorithms or every future change. Independent physical references and
  area-appropriate tests remain necessary for other code.
