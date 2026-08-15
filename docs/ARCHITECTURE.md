# Architecture

## Event-stream DNA

The MR Event Graph is MRQLab's source of truth. `SequenceIR` contains timestamped values on `rf_amp`, `rf_phase`, `gx`, `gy`, `gz`, `adc_gate`, `nco_freq`, and `nco_phase`. SE, TSE, and GRE are teaching-friendly compilers into that representation; they are not alternate simulation paths. FID exists only as a demo/test helper.

The dependency direction is `sequence-ir → physics → recon → API → web`. The web may display an IR but does not own its semantics. Pydantic validates the wire model. The API caps matrix size and computational work through `SIM_MAX_MATRIX` (64) and `SIM_MAX_WORK` (2000000) defaults.

## Physics microkernel

`SequenceIR → arithmetic preflight → scheduler → operators → state backend → SimResult` is the physics path. The kernel owns scheduling, radians/seconds/teaching-gradient units, work caps, ADC/NCO collection, k-trajectory, common result assembly, and the `mrqlab.physics_engines` registry. Built-ins and external `EnginePlugin` descriptors own state allocation and non-ADC operator application. Recon, API, and web never branch on a backend class.

Built-in routing is SE/GRE → Bloch and TSE → EPG through `preferred_engine` metadata; an API request may override it. Spectral simulation is explicitly selected with pool data. PDG is an optional provider seam, while exchange and MT remain explicit EPG-X boundaries.

## MVP versus fidelity

Physics v1 ships multi-isochromat Bloch rotations, T1/T2 relaxation, off-resonance and spatial phase for SE/GRE; classic bounded-order EPG for TSE/CPMG echo trains; and independent chemical-shift pools for fat/water teaching examples. It is educational and deliberately not a validated scanner or safety simulator. Cartesian FFT is implemented; non-Cartesian trajectories will use the NUFFT adapter seam later.
