"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { WorkbenchCockpit } from "../../components/workbench/WorkbenchCockpit";

function WorkbenchFromQuery() {
  const params = useSearchParams();
  return <WorkbenchCockpit initialRecipeId={params.get("recipe") ?? undefined} />;
}

export default function WorkbenchPage() {
  return (
    <Suspense fallback={<WorkbenchCockpit />}>
      <WorkbenchFromQuery />
    </Suspense>
  );
}
