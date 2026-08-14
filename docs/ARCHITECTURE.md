# Architecture

## Event-stream DNA

The MR Event Graph is MRQLab's source of truth. `SequenceIR` contains timestamped values on `rf_amp`, `rf_phase`, `gx`, `gy`, `gz`, `adc_gate`, `nco_freq`, and `nco_phase`. SE, TSE, and GRE are teaching-friendly compilers into that representation; they are not alternate simulation paths. FID exists only as a demo/test helper.

The dependency direction is `sequence-ir → physics → recon → API → web`. The web may display an IR but does not own its semantics. Pydantic validates the wire model. The API caps matrix size and computational work through `SIM_MAX_MATRIX` (64) and `SIM_MAX_RUNTIME` (30 seconds) defaults.

## Engine plugin map

`SimulationEngine.simulate(SequenceIR, Phantom, ScannerModel, EngineOptions) → SimResult` is the stable seam. `SimResult` carries complex signal, optional M(t), k-trajectory, engine metadata, and timing. The registry defaults to the minimal single-isochromat `BlochEngine`. EPG and spectral engines are deliberately registered stubs with actionable errors, proving that selection does not require API/UI rewrites.

Future DPG, Bloch–McConnell, diffusion, ASL, CEST, and MRS engines plug into the same interface. The pulseq-zero PDG approach is useful inspiration, but MRQLab does not require pulseq-zero, torch, MRzero, SigPy, or PyPulseq in its MVP.

## MVP versus fidelity

MVP Bloch simulation demonstrates rotations, T1/T2 relaxation, off-resonance, ADC sampling, and simple k evolution. SE and GRE produce signals; TSE uses simplified repeated refocusing. It is educational and deliberately not a validated scanner or safety simulator. EPG is the planned model for efficient multi-echo trains. Cartesian FFT is implemented; non-Cartesian trajectories will use the NUFFT adapter seam later.
