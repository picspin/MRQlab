# Measurement-derived radial TSE: fixed-prior uncertainty evidence

This stage extends `3fdf6fc` with a real parameter dependency between a saved
measured-TSE study and a new radial pulse-design study. It does not merely attach
a background reference. The included parent data are **synthetic**; this is a
teaching/research demonstration, not scanner validation, clinical quality
certification or evidence of clinical transfer. B/C remain parked.

## Parent identity and applied parameters

The unchanged [complete parent](examples/calibrated-radial-parent-record.json)
is the preceding stage's saved measured-TSE record
`bf8102c5a1fb07660b3e36e08fbd249a4740bc65f76ea5017c798d4b91168d30`.
Its original source/runtime and lossless measurement request are retained. The
new workflow verifies its integrity, reruns its entire numerical lab study from
that original request, and requires the complete numerical result hash to match.
It also requires calibration and independent acquisition holdout to pass before
applying any T2 binding or executing a radial inverse.

This is **current numerical revalidation**, not full replay of the historical
parent's source/runtime envelope. `full_parent_record_replay` is explicitly false.
Full replay of that older envelope still requires its original code anchor.
The new child records both expected and actual parent numerical hashes without
relabelling or regenerating the older parent.

| Component | Parent tissue ID | T2 (s) | Standard uncertainty (s) | Stress interval (s) |
|---|---|---|---|---|
| 0 | white_matter | 0.04000000000000001 | 0.00013157458491211448 | [0.03973685083017578, 0.040263149169824236] |
| 1 | gray_matter | 0.12000000000000001 | 0.0006619951021615966 | [0.11867600979567682, 0.1213239902043232] |

Bindings retain tissue order, component IDs, units and calibration hashes. The
sample uses the nominal pair or one of the four inherited rectangular interval
corners. **Every inverse keeps the same nominal T2 pair as its temporal basis.**
Refitting the basis at each corner would conceal prior mismatch and is not done.
T1 and proton density remain authored parent priors. Laboratory nuisance amplitude
is not an image gain calibration. Labels generate/evaluate the sample; no label
map, reference image, gain fit or regularization is supplied to the inverse.

The parent example declares measurement sigma even though its synthetic observed
rows are noiseless. Its intervals use the parent local two-standard-uncertainty
construction. Four rectangular corners are stress samples, not joint confidence
coverage, a continuous worst-case guarantee, or clinical bounds.

## Executed design grid and failed targets

Both candidates use four echoes, 8 ms spacing, 400 ms TR, forward echo order,
96 spokes, 32 points, displayed echo 2, and the exact-DFT reference backend.
Each scenario allows 6,000 CGLS iterations and 20 billion work-proxy units.
Targets remain image/component NRMSE <=1e-6, data tolerance 1e-10, magnitude
contrast >=0.005, total RF proxy <=200 and prepared duration <=100 s.

| Pulse candidate | Scenario | Image NRMSE | Component NRMSE | All targets |
|---|---|---|---|---|
| 180 degrees | nominal | 2.84227e-8 | 4.92138e-7 | PASS |
| 180 degrees | corner-0 | 0.00617170 | 0.04375074 | FAIL |
| 180 degrees | corner-1 | 0.00339697 | 0.01378014 | FAIL |
| 180 degrees | corner-2 | 0.00326340 | 0.01350280 | FAIL |
| 180 degrees | corner-3 | 0.00600919 | 0.04298309 | FAIL |
| 140 to 110 degrees | nominal | 8.95659e-8 | 9.30564e-7 | PASS |
| 140 to 110 degrees | corner-0 | 0.00440314 | 0.02171317 | FAIL |
| 140 to 110 degrees | corner-1 | 0.00287158 | 0.01463551 | FAIL |
| 140 to 110 degrees | corner-2 | 0.00276195 | 0.01450789 | FAIL |
| 140 to 110 degrees | corner-3 | 0.00428387 | 0.02135522 | FAIL |

All ten scenarios executed. No candidate is eligible; `selected_index=null` and
`selected_design_passed=false`. The first nominal image is retained only as an
explicit preview. Its passing target report cannot stand for the uncertainty
study. Lower RF alone cannot make a failed candidate eligible.

This derived workflow includes periodic preparation trains in its RF proxy:
180 degrees totals **110.5** (acquisition 102 plus preparation 8.5); 140 to 110
degrees totals **57.05555555555556**. The standalone radial model's existing
acquisition-only RF field is unchanged. These are relative proxies, not SAR or
scanner hardware limits. Prepared duration is checked separately.

The complete grid reserves **201,000,000,000** work units, including the parent
revalidation allowance, before the first radial inverse. Reported work is
**190,780,643,022** under the 250 billion shared cap. An insufficient reservation
executes no partial inverse grid. A failed scenario is conservatively charged
its declared cap; failure is not a free retry. Budgets remain planning proxies,
not hard operating-system resource containment.

## Portable derivation and replay

`calibrated_radial_tse` is a strict scientific execution type. A parent ID resolves
from local storage, or a full embedded parent may be supplied. Only a verified
`measured_tse` parent is accepted. The saved child's lossless request embeds that
entire parent, so importing/replaying the child does not need an external parent
database. Import also retains the unchanged parent as a separately openable
record. A new provenance stage links its immutable identity; inner stages retain
parent numerical revalidation, parameter bindings, complete uncertainty search
and target validation. Every scenario includes its full run and complex data.

The [plan](examples/calibrated-radial-plan.json) and
[compact evidence](examples/calibrated-radial-evidence.json) retain exact hashes,
targets, bindings, all scenario outcomes and their sample/basis/run hashes.
The complete child identity is
`756477f83ae0080a7886f5ea5df215ad7461c3e6c5baa748d69e900af9b304e7`;
its payload hash is
`9ece677b093c5df9da70baa1ba0823d064478603991e00fd1b7e98c28a97f121`.
The 8,802,180-byte portable child is saved in local storage and outside source at
`/private/tmp/mrqlab-calibrated-radial-3fdf6fc-20261030/complete-record.json`.
The repository retains the original parent and compact evidence rather than a
second large derived-data copy. Reproduction generates the complete child.

With the locked environment installed, use new output paths:

```sh
.venv/bin/python -m mrqlab_api.scientific_records --store /tmp/derived-radial.sqlite3 \
  import docs/research/examples/calibrated-radial-parent-record.json
.venv/bin/python -m mrqlab_api.scientific_records --store /tmp/derived-radial.sqlite3 \
  run docs/research/examples/calibrated-radial-plan.json --output /tmp/derived-radial.json
.venv/bin/python -m mrqlab_api.scientific_records verify /tmp/derived-radial.json
.venv/bin/python -m mrqlab_api.scientific_records --store /tmp/derived-radial.sqlite3 \
  replay /tmp/derived-radial.json --output /tmp/derived-radial-replayed.json
.venv/bin/python scripts/verify_calibrated_radial.py \
  --verify docs/research/examples/calibrated-radial-evidence.json \
  --output /tmp/derived-radial-evidence.json --record-output /tmp/derived-radial-complete.json
```

`import`/`verify` perform integrity checks only. `run`, `replay` and the independent
evidence script perform actual computation. Full replay requires matching child
source/runtime. Importing the child into an empty independent SQLite store retained
exactly its parent and child; a new CLI process fully recomputed the child to
byte-identical JSON. The independent evidence recomputation also matched every
scenario and complete-record hash. Actual HTTP create/read/parent lookup and
full replay through port 8007 produced the same child and payload hashes,
retaining the failed master result and passing nominal preview separately.

## Frontend and verification limits

The measured-parent record pane now offers a derived radial-study form, requiring
a research question/rationale and allowing bounded candidate/numerical/target
inputs. Parent T2 and tissue bindings cannot be overridden through that form or
strict execution schema. The child pane links the parent, shows parameter units,
fixed reconstruction basis, scenario errors, reservation and failed selection.
Display T2 is in ms while stored bindings remain in seconds. The nominal plot's
report is explicitly labelled as nominal, separate from the full study outcome.

Full regression: **842 Python passed**, one existing Starlette/httpx warning;
**111 frontend passed** in 16 files; TypeScript and production build passed.
Tests include independent 180-degree decay ratios, holdout failure blocking,
consistently rehashed parent-result tampering, budget rejection/partial failures,
strict override rejection, portable import/full replay, API parent validation,
and component evidence/form states. Build artifacts are outside source under
the same temporary directory; generated tracked files were restored without
`git clean`. Original handoff notes and `.pi/` remain untouched.

A fresh browser inventory still reports **The browser access host is
unavailable**. Actual rendered clicking, visual inspection and native file-picker/
download flows remain unverified. HTTP, component tests and static builds do not
close that boundary. No Safari/control workaround or service/lock change was made.

## Remaining platform gaps

Fixed-prior mismatch fails the original strict targets. A useful uncertainty-aware
inverse, independently validated T2 inference and/or better measured priors remain
needed; targets were not relaxed to manufacture a selection. This pilot does not
provide measured T1/PD, coils/noise/trajectory calibration, full echo-window
readout physics, a continuous robust optimizer or clinical target translation.
Measured flow, CEST/NOE and MRS calibration, raw-data authenticity/archive,
general uncertainty/unit conventions, durable replay receipts, cross-platform
numeric replay, hard resource containment and browser verification remain open.
Earlier physics coverage reports continue to apply. The full goal remains active;
no push, PR, merge, B/C unlock, submission import or project-folder relocation
was performed.
