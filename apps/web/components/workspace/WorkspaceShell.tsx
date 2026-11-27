"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useWorkspace } from "./WorkspaceProvider";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { profile, setProfile, executionState } = useWorkspace();
  const [showAiModal, setShowAiModal] = useState(false);

  return (
    <main className="workspace-shell">
      {/* 1. Top Navigation: Brushed Aluminum Bar */}
      <nav aria-label="Top Level Taxonomy" className="top-nav">
        <div className="nav-brand">
          <Link href="/">MRQLAB</Link>
          <span className="version-tag" data-testid="version-tag">v0.76.15</span>
        </div>

        <div className="nav-routes">
          <Link href="/" className="nav-item">
            EXPLORE
          </Link>
          <Link href="/workbench" className={pathname?.startsWith("/research") ? "nav-item" : "nav-item active"}>
            WORKBENCH
          </Link>
          <Link href="/labs" className="nav-item">
            LABS
          </Link>
          <Link href="/research" className={pathname?.startsWith("/research") ? "nav-item active" : "nav-item"}>RESEARCH</Link>
          <button
            onClick={() => setShowAiModal(true)}
            className="nav-item"
            style={{
              background: "linear-gradient(180deg, var(--amber-3) 0%, var(--amber-3) 100%)",
              border: ".5px solid var(--amber-11)",
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
            backgroundColor: "var(--scrim)",
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
              backgroundColor: "var(--surface)",
              border: ".5px solid var(--border)",
              borderRadius: "4px",
              padding: "24px",
              maxWidth: "520px",
              width: "100%",
              boxShadow: "none",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ margin: 0, color: "var(--amber)", fontSize: "16px", fontWeight: 800 }}>
                🤖 AI LAB vs 🧪 LABS (Taxonomy)
              </h3>
              <button
                onClick={() => setShowAiModal(false)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-muted)",
                  fontSize: "16px",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ fontSize: "12px", color: "var(--text)", lineHeight: 1.6, display: "flex", flexDirection: "column", gap: "12px" }}>
              <div style={{ background: "var(--surface-sunken)", padding: "12px", borderRadius: "6px", borderLeft: ".5px solid var(--border)" }}>
                <b style={{ color: "var(--cyan)" }}>🧪 LABS (Teaching Sandboxes)</b>:
                <div style={{ color: "var(--text-muted)", marginTop: "4px" }}>
                  面向物理教学与特定序列的交互实验室（如 <b>TSE Signal Lab</b>、<b>Linked Lens Editor</b>、<b>Bloch Isochromats</b>）。
                </div>
              </div>

              <div style={{ background: "var(--surface-sunken)", padding: "12px", borderRadius: "6px", borderLeft: "3px solid var(--amber)" }}>
                <b style={{ color: "var(--amber)" }}>✨ AI LAB (Autonomous Agent Co-Pilot)</b>:
                <div style={{ color: "var(--text-muted)", marginTop: "4px" }}>
                  面向自然语言驱动的自主 MRI 专家 Agent。接收临床医生目标（如 <i>"帮我优化脑部扫描以避开植入物 SAR 限制"</i>），通过 MCP tool schemas 自主生成 ExperimentGraph 并调用内核优化器。
                </div>
              </div>

              <div style={{ fontSize: "12px", color: "var(--text-muted)", fontFamily: "monospace" }}>
                * AI Lab Runtime 规划在 Wave H / v0.5+ 中接入 Agent 调度内核。
              </div>
            </div>

            <div style={{ marginTop: "20px", display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowAiModal(false)}
                style={{
                  backgroundColor: "var(--amber)",
                  color: "var(--surface-sunken)",
                  border: "none",
                  borderRadius: "4px",
                  padding: "8px 18px",
                  fontWeight: 800,
                  fontSize: "12px",
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
        <span>EDUCATIONAL MRI SIMULATOR  --  NOT FOR CLINICAL USE  --  RETROMORPHIC WORKBENCH</span>
      </footer>
    </main>
  );
}
