"use client";

import React, { useState } from "react";
import Link from "next/link";

interface ClinicalCase {
  id: string;
  title: string;
  anatomy: string;
  clinicalQuestion: string;
  keyPhysics: string;
  sequence: string;
  parameters: { fa: number; te: number; tr: number };
  difficulty: "Fundamental" | "Intermediate" | "Advanced";
}

const CASE_TAXONOMY: Record<string, ClinicalCase[]> = {
  "Brain & Neuro": [
    {
      id: "ms-lesion-t2",
      title: "Multiple Sclerosis (MS) Plaque Contrast",
      anatomy: "Brain / White Matter",
      clinicalQuestion: "Why do demyelinating MS plaques appear hyperintense on T2 TSE while minimizing CSF partial volume artifacts?",
      keyPhysics: "T2 transverse relaxation differentiation + EPG stimulated echo preservation in TSE echo train",
      sequence: "Brain T2 Turbo Spin Echo (TSE)",
      parameters: { fa: 150, te: 100, tr: 3000 },
      difficulty: "Fundamental",
    },
    {
      id: "brain-flair",
      title: "FLAIR Free-Water Attenuation",
      anatomy: "Brain / Ventricles",
      clinicalQuestion: "How does Inversion Recovery null CSF signal to reveal periventricular lesions?",
      keyPhysics: "180° Inversion Recovery null-crossing timing $TI = T1 \\ln(2)$",
      sequence: "T2 Fluid Attenuated Inversion Recovery",
      parameters: { fa: 180, te: 120, tr: 8000 },
      difficulty: "Intermediate",
    },
  ],
  "Cardiovascular": [
    {
      id: "dark-blood-tse",
      title: "Dark Blood Vessel Wall Separation",
      anatomy: "Heart / Carotid Artery",
      clinicalQuestion: "How to completely suppress flowing luminal blood signal while preserving high SNR for carotid plaque wall?",
      keyPhysics: "Double Inversion Recovery (DIR) flow dephasing + slice selective re-inversion",
      sequence: "Dark Blood Turbo Spin Echo (Uses: TSE)",
      parameters: { fa: 140, te: 60, tr: 1200 },
      difficulty: "Advanced",
    },
    {
      id: "myocardial-t1-map",
      title: "Myocardial Fibrosis MOLLI T1 Mapping",
      anatomy: "Myocardium",
      clinicalQuestion: "How to quantify diffuse interstitial fibrosis via pixel-wise T1 relaxation fitting?",
      keyPhysics: "Look-Locker readout modification with modified EPG steady-state correction",
      sequence: "Modified Look-Locker Inversion (MOLLI)",
      parameters: { fa: 35, te: 1.5, tr: 3.0 },
      difficulty: "Advanced",
    },
  ],
  "Body & Musculoskeletal": [
    {
      id: "dixon-fat-water",
      title: "Dixon Two-Point Water-Fat Separation",
      anatomy: "Abdomen / Liver",
      clinicalQuestion: "How does chemical shift phase cycling separate fat from water parenchymal signals?",
      keyPhysics: "3.5 ppm chemical shift $\\Delta f$ phase modulation between in-phase and out-of-phase echoes",
      sequence: "Dual-Echo Fast Gradient Echo (GRE)",
      parameters: { fa: 12, te: 2.3, tr: 150 },
      difficulty: "Intermediate",
    },
    {
      id: "knee-cartilage-t2",
      title: "Knee Articular Cartilage T2 Mapping",
      anatomy: "Musculoskeletal / Knee",
      clinicalQuestion: "How does collagen matrix degradation correlate with multi-echo T2 prolongation?",
      keyPhysics: "Multi-echo Spin Echo CPMG decay curve exponential non-linear regression",
      sequence: "Multi-Echo Spin Echo (MESE)",
      parameters: { fa: 180, te: 80, tr: 2000 },
      difficulty: "Fundamental",
    },
  ],
};

export default function Home() {
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const categories = ["All", ...Object.keys(CASE_TAXONOMY)];

  const filteredCases = Object.entries(CASE_TAXONOMY).flatMap(([cat, cases]) => {
    if (selectedCategory !== "All" && selectedCategory !== cat) return [];
    return cases.filter(
      (c) =>
        c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.clinicalQuestion.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.sequence.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.anatomy.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  return (
    <div style={{ padding: "24px", maxWidth: "1400px", margin: "0 auto", width: "100%" }}>
      {/* Header Banner */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          borderBottom: "2px solid #38444a",
          paddingBottom: "18px",
          marginBottom: "24px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <span
            style={{
              fontSize: "0.75rem",
              color: "var(--amber)",
              textTransform: "uppercase",
              letterSpacing: "1.5px",
              fontWeight: 800,
            }}
          >
            MRQLAB EXPLORATION MATRIX
          </span>
          <h1
            style={{
              fontSize: "1.8rem",
              color: "#ffffff",
              margin: "4px 0 0 0",
              fontWeight: 900,
              letterSpacing: "1px",
            }}
          >
            Clinical Intent ➔ Physics Execution
          </h1>
          <p style={{ color: "#8da1aa", margin: "6px 0 0 0", fontSize: "0.9rem" }}>
            Select a verified clinical pathology case to launch the Retromorphic Workbench instrument.
          </p>
        </div>

        {/* Search & Filter Bar */}
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="text"
            placeholder="🔍 Search cases, anatomy, physics..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              backgroundColor: "#101618",
              border: "1px solid #3d4a50",
              borderRadius: "6px",
              padding: "8px 14px",
              color: "#fff",
              fontSize: "0.85rem",
              minWidth: "260px",
              outline: "none",
            }}
          />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            style={{
              backgroundColor: "#182023",
              border: "1px solid #4a5a62",
              borderRadius: "6px",
              padding: "8px 12px",
              color: "var(--cyan)",
              fontWeight: 700,
              fontSize: "0.85rem",
              cursor: "pointer",
            }}
          >
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat === "All" ? "📂 All Anatomical Trees" : `📁 ${cat}`}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Case Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: "20px" }}>
        {filteredCases.map((item) => (
          <article
            key={item.id}
            style={{
              background: "linear-gradient(170deg, #2a3236 0%, #181d1f 100%)",
              border: "2px solid #435157",
              borderRadius: "10px",
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxShadow: "inset 1px 1px 0 #5b6e76, 0 6px 16px rgba(0,0,0,0.5)",
              transition: "transform 0.2s, border-color 0.2s",
            }}
          >
            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "8px",
                }}
              >
                <span
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--amber)",
                    fontWeight: 800,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}
                >
                  📍 {item.anatomy}
                </span>
                <span
                  style={{
                    fontSize: "0.7rem",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontFamily: "monospace",
                    fontWeight: 700,
                    backgroundColor:
                      item.difficulty === "Fundamental"
                        ? "rgba(59, 244, 141, 0.15)"
                        : item.difficulty === "Intermediate"
                        ? "rgba(255, 184, 52, 0.15)"
                        : "rgba(255, 126, 51, 0.15)",
                    color:
                      item.difficulty === "Fundamental"
                        ? "var(--green-neon)"
                        : item.difficulty === "Intermediate"
                        ? "var(--amber)"
                        : "var(--orange-neon)",
                    border: "1px solid #334247",
                  }}
                >
                  {item.difficulty}
                </span>
              </div>

              <h2 style={{ fontSize: "1.2rem", color: "#ffffff", margin: "0 0 10px 0", fontWeight: 800 }}>
                {item.id === "dark-blood-tse" ? "Dark Blood" : item.title}
              </h2>

              <div
                style={{
                  backgroundColor: "#0f1416",
                  borderLeft: "3px solid var(--cyan)",
                  padding: "8px 12px",
                  borderRadius: "0 4px 4px 0",
                  marginBottom: "12px",
                  fontSize: "0.85rem",
                  color: "#d1dde2",
                  lineHeight: 1.4,
                }}
              >
                <b>Clinical Question:</b> {item.clinicalQuestion}
              </div>

              <div style={{ fontSize: "0.8rem", color: "#8da1aa", marginBottom: "16px", lineHeight: 1.4 }}>
                <span style={{ color: "#adbcc4", fontWeight: 700 }}>Key Physics:</span> {item.keyPhysics}
              </div>
            </div>

            <div
              style={{
                borderTop: "1px solid #2e3a3f",
                paddingTop: "14px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "var(--amber)" }}>
                ⚡ {item.sequence}
              </div>
              <Link
                href="/workbench"
                style={{
                  background: "linear-gradient(180deg, #323d42 0%, #1f272a 100%)",
                  border: "1px solid #4f636b",
                  color: "var(--cyan)",
                  textDecoration: "none",
                  fontSize: "0.8rem",
                  fontWeight: 800,
                  padding: "8px 16px",
                  borderRadius: "4px",
                  boxShadow: "0 2px 6px rgba(0,0,0,0.3)",
                  letterSpacing: "0.5px",
                }}
              >
                Launch Cockpit ➔
              </Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
