import Link from "next/link";

export default function LabsPage() {
  const labModules = [
    {
      id: "signal-lab",
      title: "TSE Signal Lab & Teaching Chain",
      category: "Physics & Sequence",
      desc: "Deep-dive into TSE refocusing flip angle, EPG coherence states, echo trains, and relative SAR thermal deposition.",
      link: "/signal-lab",
      badge: "Interactive",
      icon: "⚡"
    },
    {
      id: "editor",
      title: "Linked Lens Experiment Editor",
      category: "Experiment Synthesis",
      desc: "Four-panel multi-modal editor linking Sequence timeline, EPG states, k-space trajectories, and reconstructed observations.",
      link: "/editor",
      badge: "Multi-Lens",
      icon: "🔬"
    },
    {
      id: "bloch-sandbox",
      title: "Bloch Isochromat Sandbox",
      category: "Nuclear Magnetic Resonance",
      desc: "Vector magnetization dynamics M(t), precession, T1 recovery, T2 dephasing, and off-resonance slice profiles.",
      link: "/workbench",
      badge: "Core Physics",
      icon: "🧲"
    }
  ];

  return (
    <div style={{ padding: "24px", maxWidth: "1400px", margin: "0 auto", width: "100%" }}>
      <header style={{ marginBottom: "24px", borderBottom: ".5px solid var(--border)", paddingBottom: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1 style={{ fontSize: "20px", color: "var(--text)", margin: 0, fontWeight: 800, letterSpacing: "1px" }}>
              PHYSICS & CLINICAL LABS
            </h1>
            <p style={{ color: "var(--text-muted)", margin: "6px 0 0 0", fontSize: "14px" }}>
              Curated interactive MRI simulation modules, teaching laboratories, and sequence sandboxes.
            </p>
          </div>
          <span style={{ fontSize: "12px", background: "var(--surface)", border: ".5px solid var(--border)", padding: "4px 10px", borderRadius: "4px", color: "var(--cyan)", fontFamily: "monospace" }}>
            MODULES READY: 3
          </span>
        </div>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "20px" }}>
        {labModules.map((m) => (
          <div
            key={m.id}
            style={{
              background: "linear-gradient(170deg, var(--surface) 0%, var(--surface) 100%)",
              border: ".5px solid var(--border)",
              borderRadius: "4px",
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxShadow: "none",
            }}
          >
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <span style={{ fontSize: "12px", color: "var(--amber)", textTransform: "uppercase", letterSpacing: "1px", fontWeight: 800 }}>
                  {m.category}
                </span>
                <span style={{ fontSize: "12px", background: "var(--surface-sunken)", border: ".5px solid var(--border)", color: "var(--cyan)", padding: "2px 6px", borderRadius: "4px" }}>
                  {m.badge}
                </span>
              </div>
              <h2 style={{ fontSize: "16px", color: "var(--text)", margin: "0 0 8px 0", fontWeight: 700 }}>
                {m.icon} {m.title}
              </h2>
              <p style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: 1.5, margin: "0 0 16px 0" }}>
                {m.desc}
              </p>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", borderTop: ".5px solid var(--border)", paddingTop: "14px" }}>
              <Link
                href={m.link}
                style={{
                  background: "linear-gradient(180deg, var(--surface-raised) 0%, var(--surface) 100%)",
                  border: ".5px solid var(--border)",
                  color: "var(--cyan)",
                  textDecoration: "none",
                  fontSize: "12px",
                  fontWeight: 700,
                  padding: "8px 18px",
                  borderRadius: "4px",
                  boxShadow: "none",
                }}
              >
                Launch Lab →
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
