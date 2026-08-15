# Task 1 report: split physics engine layout

## RED

Command:

```text
python3.11 -m pytest tests/physics/test_layout.py -q
```

Result: collection failed as expected with `ModuleNotFoundError: No module named 'mrqlab_physics.engines.bloch_engine'; 'mrqlab_physics.engines' is not a package`.

## GREEN

Command:

```text
python3.11 -m pytest tests/physics/test_layout.py tests/test_physics.py -q
```

Result: `5 passed in 0.10s`.

## Files changed

- Replaced `mrqlab_physics/engines.py` with the recursively discoverable `engines/` package and split Bloch, EPG, and spectral engines into focused modules.
- Added empty `kernel`, `ops`, and `backends` package markers.
- Added `SimulationEngine.description` and `available` metadata.
- Switched setuptools configuration to package discovery across all package roots.
- Added `tests/physics/test_layout.py`.

## Self-review

- `git diff --check` passed.
- Recursive package discovery found all seven new physics package modules.
- Existing physics registry/template tests remained green.
- Unrelated `.hermes/` and `docs/research/` untracked changes were preserved.

## Concerns

- The prescribed transitional Bloch implementation returns a zero `k_trajectory`, whereas the former monolithic module integrated `gx`; this follows the task brief verbatim but is the one possible behavior compatibility concern.
- EPG/spectral errors retain the legacy word `future` for the current regression assertion while preserving the prescribed backend-specific messages.
