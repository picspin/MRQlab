import type { Metadata } from "next";
import "./style.css";
import { WorkspaceProvider } from "../components/workspace/WorkspaceProvider";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";

export const metadata: Metadata = {title:"MRQLab — From spin to pixel", description:"Teaching MRI simulator"};

export default function Layout({children}:{children:React.ReactNode}) {
  return (
    <html lang="en">
      <body>
        <WorkspaceProvider>
          <WorkspaceShell>{children}</WorkspaceShell>
        </WorkspaceProvider>
      </body>
    </html>
  );
}
