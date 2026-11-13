"use client";

import React, { useState } from "react";
import Link from "next/link";
import { exploreCasesByCategory } from "../lib/explore-catalog";

const CASE_TAXONOMY = exploreCasesByCategory();

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
          borderBottom: ".5px solid var(--border)",
          paddingBottom: "18px",
          marginBottom: "24px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <span
            style={{
              fontSize: "12px",
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
              fontSize: "20px",
              color: "var(--text)",
              margin: "4px 0 0 0",
              fontWeight: 900,
              letterSpacing: "1px",
            }}
          >
            Clinical Intent ➔ Physics Execution
          </h1>
          <p style={{ color: "var(--text-muted)", margin: "6px 0 0 0", fontSize: "14px" }}>
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
              backgroundColor: "var(--surface)",
              border: ".5px solid var(--border)",
              borderRadius: "6px",
              padding: "8px 14px",
              color: "var(--text)",
              fontSize: "12px",
              minWidth: "260px",
              outline: "none",
            }}
          />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            style={{
              backgroundColor: "var(--surface)",
              border: ".5px solid var(--border)",
              borderRadius: "6px",
              padding: "8px 12px",
              color: "var(--cyan)",
              fontWeight: 700,
              fontSize: "12px",
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
              background: "linear-gradient(170deg, var(--surface) 0%, var(--surface) 100%)",
              border: ".5px solid var(--border)",
              borderRadius: "4px",
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxShadow: "none",
              transition: "color 250ms ease-out, background-color 250ms ease-out, border-color 250ms ease-out",
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
                    fontSize: "12px",
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
                    fontSize: "12px",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontFamily: "monospace",
                    fontWeight: 700,
                    backgroundColor:
                      item.difficulty === "Fundamental"
                        ? "var(--difficulty-fundamental)"
                        : item.difficulty === "Intermediate"
                        ? "var(--difficulty-intermediate)"
                        : "var(--difficulty-advanced)",
                    color:
                      item.difficulty === "Fundamental"
                        ? "var(--green-neon)"
                        : item.difficulty === "Intermediate"
                        ? "var(--amber)"
                        : "var(--orange-neon)",
                    border: ".5px solid var(--border)",
                  }}
                >
                  {item.difficulty}
                </span>
              </div>

              <h2 style={{ fontSize: "16px", color: "var(--text)", margin: "0 0 10px 0", fontWeight: 800 }}>
                {item.id === "dark-blood-tse" ? "Dark Blood" : item.title}
              </h2>

              <div
                style={{
                  backgroundColor: "var(--surface-sunken)",
                  borderLeft: ".5px solid var(--border)",
                  padding: "8px 12px",
                  borderRadius: "0 4px 4px 0",
                  marginBottom: "12px",
                  fontSize: "12px",
                  color: "var(--text)",
                  lineHeight: 1.4,
                }}
              >
                <b>Clinical Question:</b> {item.clinicalQuestion}
              </div>

              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "16px", lineHeight: 1.4 }}>
                <span style={{ color: "var(--text-muted)", fontWeight: 700 }}>Key Physics:</span> {item.keyPhysics}
              </div>
            </div>

            <div
              style={{
                borderTop: ".5px solid var(--border)",
                paddingTop: "14px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ fontSize: "12px", fontFamily: "monospace", color: "var(--amber)" }}>
                ⚡ {item.sequence}
              </div>
              {item.executable && item.recipeId ? (
                <Link
                  href={`/workbench?recipe=${item.recipeId}`}
                  data-testid={`launch-${item.id}`}
                  style={{
                    background: "linear-gradient(180deg, var(--surface-raised) 0%, var(--surface) 100%)",
                    border: ".5px solid var(--border)",
                    color: "var(--cyan)",
                    textDecoration: "none",
                    fontSize: "12px",
                    fontWeight: 800,
                    padding: "8px 16px",
                    borderRadius: "4px",
                    boxShadow: "none",
                    letterSpacing: "0.5px",
                  }}
                >
                  Launch Cockpit ➔
                </Link>
              ) : (
                <span
                  data-testid={`badge-${item.id}`}
                  title="No engine / recipe in v0.1 — not a fake Launch"
                  style={{
                    fontSize: "12px",
                    fontWeight: 800,
                    letterSpacing: "0.4px",
                    color: "var(--text-muted)",
                    border: ".5px solid var(--border)",
                    padding: "8px 12px",
                    borderRadius: "4px",
                    textTransform: "uppercase",
                  }}
                >
                  not in v0.1
                </span>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
