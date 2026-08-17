"use client";
import { useEffect } from "react";
import { LinkedLens } from "../../components/editor/LinkedLens";
import { useWorkspace } from "../../components/workspace/WorkspaceProvider";
export default function EditorPage() {
  const { openWorkspace } = useWorkspace();
  useEffect(() => openWorkspace("editor"), [openWorkspace]);
  return <section className="editor-cockpit"><aside>Experiment navigator</aside><LinkedLens/><aside>SAR · duty · assumptions</aside></section>;
}
