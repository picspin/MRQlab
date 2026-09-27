# Milestone A rulings

- Setup: Proceed past the pre-existing `tests/test_v0765_run_composed_ir.py::test_http_run_rejects_teaching_ir_with_diffusion` baseline failure. The fixture returns `tissue` as a list but the test indexes it as a mapping; Milestone A did not cause it, and final full-suite acceptance remains mandatory. Cost if wrong: the final gate will expose the attribution and the defect must be repaired before completion.
- Task 4: Replace the frozen plan in the existing provenance regression with `model_copy(update=...)` instead of mutating it. This preserves the test's source-of-truth assertion while honoring the locked immutable-plan contract. Cost if wrong: the test could stop detecting provenance sourced from the plan rather than simulation metadata.
