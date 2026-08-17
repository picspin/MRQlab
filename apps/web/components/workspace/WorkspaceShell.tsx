"use client";
import Link from "next/link";
import { useWorkspace } from "./WorkspaceProvider";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { workspace } = useWorkspace();
  return <main className="workspace-shell">
    <nav aria-label="Workspaces">
      <Link href="/">MRQLAB</Link><span>{workspace.toUpperCase()}</span>
      <Link href="/">Explore</Link><Link href="/editor">Editor</Link><Link href="/signal-lab">Signal Lab</Link>
    </nav>
    {children}
    <p className="disclaimer">EDUCATIONAL SIMULATOR · NOT FOR CLINICAL USE · NO SCANNER HARDWARE CONNECTED</p>
  </main>;
}
