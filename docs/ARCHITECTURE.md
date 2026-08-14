# Architecture

## Event-stream DNA

The MR Event Graph is MRQLab's source of truth. `SequenceIR` contains timestamped values on `rf_amp`, `rf_phase`, `gx`, `gy`, `gz`, `adc_gate`, `nco_freq`, and `nco_phase`. SE, TSE, and GRE are teaching-friendly compilers into that representation; they are not alternate simulation paths. FID exists only as a demo/test helper.

The dependency direction is `sequence-ir → physics → recon → API → web`. The web may display an IR but does not own its semantics. Pydantic validates the wire model. The API caps matrix size and computational work through `SIM_MAX_MATRIX` (64) and `SIM_MAX_WORK` (2000000) defaults.

## Physics microkernel

`SequenceIR → scheduler → operators → state backend → SimResult` is the physics path. The kernel owns scheduling, radians/seconds/teaching-gradient units, work caps, ADC/NCO collection, k-trajectory, and the `mrqlab.physics_engines` registry. Bloch, classic EPG, and spectral plugins own state and operator application. Recon, API, and web never branch on a backend class.

Built-in routing is SE/GRE → Bloch and TSE → EPG through `preferred_engine` metadata; an API request may override it. Spectral simulation is explicitly selected with pool data. PDG is an optional provider seam, while exchange and MT remain explicit EPG-X boundaries.

## MVP versus fidelity

MVP Bloch simulation demonstrates rotations, T1/T2 relaxation, off-resonance, ADC sampling, and simple k evolution. SE and GRE produce signals; TSE uses simplified repeated refocusing. It is educational and deliberately not a validated scanner or safety simulator. EPG is the planned model for efficient multi-echo trains. Cartesian FFT is implemented; non-Cartesian trajectories will use the NUFFT adapter seam later.
