# Roadmap

## MVP — now

- SE, simplified TSE, and GRE compile to a validated event graph.
- Physics v1 is delivered: multi-isochromat Bloch, classic bounded-order EPG, and independent fat/water spectral pools behind one microkernel.
- Kernel-controlled backend descriptors support third-party state implementations without delegating scheduling, caps, ADC/NCO, or result assembly.
- Cartesian FFT reconstruction and FastAPI endpoints.
- Skeuomorphic learning bench with timeline, tissue/scanner controls, linked-view placeholders, modes, and Reality Slider.

## Next

- Next fidelity: physical gradient units and diffusion wiring, then Bloch–McConnell/MT, CEST saturation, richer MRS, and an optional PDG provider distribution.
- Progressive Beginner, Clinical, Physics, and Hardware *concept* curricula. “Hardware” remains a learning mode, never an acquisition connection.
- Fidelity layers driven by the Reality Slider, with explicit assumptions and error budgets.

## Delivery

After the local learning loop is stable, the static/web surface may deploy to Vercel or Cloudflare and the API to a separately bounded Python host. Codex Cloud is a development agent only; it is not runtime infrastructure, a simulator backend, or a deployment target. Real scanner hardware, MaRCoS, Red Pitaya, and acquisition services remain out of scope.
