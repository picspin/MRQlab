"use client";
import Link from "next/link";
import { useWorkspace } from "./WorkspaceProvider";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { profile, setProfile, executionState } = useWorkspace();

  return (
    <main className="workspace-shell">
      <nav aria-label="Top Level Taxonomy" className="top-nav">
        <div className="nav-brand">
          <Link href="/">MRQLAB</Link>
          <span className="version-tag">v0.2</span>
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
          <span className="nav-item disabled" title="Coming later in v0.3+">
            AI LAB
          </span>
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

      <div className="workspace-content">{children}</div>

      <footer className="disclaimer">
        <span>EDUCATIONAL MRI SIMULATOR · NOT FOR CLINICAL USE · RETROMORPHIC WORKBENCH</span>
      </footer>
    </main>
  );
}
