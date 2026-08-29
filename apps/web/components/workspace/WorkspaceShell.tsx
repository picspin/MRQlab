"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useWorkspace } from "./WorkspaceProvider";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { profile, setProfile, executionState } = useWorkspace();
  const [showAiModal, setShowAiModal] = useState(false);

  return (
    <main className="workspace-shell">
      {/* 1. Top Navigation: Brushed Aluminum Bar */}
      <nav aria-label="Top Level Taxonomy" className="top-nav">
        <div className="nav-brand">
          <Link href="/">MRQLAB</Link>
          <span className="version-tag" data-testid="version-tag">v0.67.15</span>
        </div>

        <div className="nav-routes">
          <Link href="/" className="nav-item">
            EXPLORE
          </Link>
          <Link href="/workbench" className="nav-item active">
            WORKBENCH
          </Link>
          <Link href="/labs" className="nav-item">
            LABS
          </Link>
          <button
            onClick={() => setShowAiModal(true)}
            className="nav-item"
            style={{
              background: "linear-gradient(180deg, #2e2614 0%, #1a150a 100%)",
              border: "1px solid #785a1a",
              color: "var(--amber)",
              cursor: "pointer",
            }}
          >
            ✨ AI LAB
          </button>
        </div>

        <div className="nav-profile">
          <div className="persona-toggle">
            <button
              className={profile === "clinical" ? "active" : ""}
              onClick={() => setProfile("clinical")}
            >
              Clinical
            </button>
            <button
              className={profile === "physics" ? "active" : ""}
              onClick={() => setProfile("physics")}
            >
              Physics
            </button>
          </div>
          <div className={`status-indicator ${executionState.toLowerCase()}`}>
            <span className="dot" />
            <small>{executionState}</small>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="workspace-content">{children}</div>

      {/* AI Lab Info Modal */}
      {showAiModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            backdropFilter: "blur(4px)",
            padding: "20px",
          }}
        >
          <div
            style={{
              backgroundColor: "#13181a",
              border: "2px solid #5a6e77",
              borderRadius: "10px",
              padding: "24px",
              maxWidth: "520px",
              width: "100%",
              boxShadow: "0 10px 30px rgba(0,0,0,0.8), 0 0 20px rgba(255, 184, 52, 0.2)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ margin: 0, color: "var(--amber)", fontSize: "1.2rem", fontWeight: 800 }}>
                🤖 AI LAB vs 🧪 LABS (Taxonomy)
              </h3>
              <button
                onClick={() => setShowAiModal(false)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#8da1aa",
                  fontSize: "1.2rem",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ fontSize: "0.85rem", color: "#d1dde2", lineHeight: 1.6, display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ background: "#0c1012", padding: "12px", borderRadius: "6px", borderLeft: "3px solid var(--cyan)" }}>
                <b style={{ color: "var(--cyan)" }}>🧪 LABS (Teaching Sandboxes)</b>:
                <div style={{ color: "#9eb0b9", marginTop: "4px" }}>
                  面向物理教学与特定序列的交互实验室（如 <b>TSE Signal Lab</b>、<b>Linked Lens Editor</b>、<b>Bloch Isochromats</b>）。
                </div>
              </div>

              <div style={{ background: "#0c1012", padding: "12px", borderRadius: "6px", borderLeft: "3px solid var(--amber)" }}>
                <b style={{ color: "var(--amber)" }}>✨ AI LAB (Autonomous Agent Co-Pilot)</b>:
                <div style={{ color: "#9eb0b9", marginTop: "4px" }}>
                  面向自然语言驱动的自主 MRI 专家 Agent。接收临床医生目标（如 <i>"帮我优化脑部扫描以避开植入物 SAR 限制"</i>），通过 MCP tool schemas 自主生成 ExperimentGraph 并调用内核优化器。
                </div>
              </div>

              <div style={{ fontSize: "0.75rem", color: "#6b828c", fontFamily: "monospace" }}>
                * AI Lab Runtime 规划在 Wave H / v0.5+ 中接入 Agent 调度内核。
              </div>
            </div>

            <div style={{ marginTop: "20px", display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowAiModal(false)}
                style={{
                  backgroundColor: "var(--amber)",
                  color: "#0a0d0e",
                  border: "none",
                  borderRadius: "4px",
                  padding: "8px 18px",
                  fontWeight: 800,
                  fontSize: "0.8rem",
                  cursor: "pointer",
                }}
              >
                Understood
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="disclaimer">
        <span>EDUCATIONAL MRI SIMULATOR · NOT FOR CLINICAL USE · RETROMORPHIC WORKBENCH</span>
      </footer>
    </main>
  );
}
