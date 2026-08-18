import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import type { PipelineStage } from "@/lib/api";

export function PipelineStatusBanner({ stages: data }: { stages: PipelineStage[] | undefined }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(t);
  }, []);

  const stages = data ?? [];
  const visible = stages.filter((s) => {
    if (s.status === "running" || s.status === "error") return true;
    if (s.status === "done" && s.finished_at) {
      const finishedMs = new Date(s.finished_at).getTime();
      return !Number.isNaN(finishedMs) && now - finishedMs < 2 * 60 * 1000;
    }
    return false;
  });

  if (visible.length === 0) return null;

  return (
    <div className="mb-4 space-y-2">
      {visible.map((s) => (
        <StageBanner key={s.stage} stage={s} />
      ))}
    </div>
  );
}

function formatStageName(stage: string) {
  return stage.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StageBanner({ stage }: { stage: PipelineStage }) {
  const label = formatStageName(stage.stage);

  if (stage.status === "running") {
    const total = stage.total_items ?? 0;
    const done = stage.completed_items ?? 0;
    return (
      <div className="flex items-start gap-3 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900 dark:border-blue-900/60 dark:bg-blue-950/40 dark:text-blue-100">
        <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
        <div className="min-w-0">
          <span className="font-medium">{label} running:</span>{" "}
          <span>
            {done} / {total}
          </span>
          {stage.current_item && (
            <span className="text-blue-800/80 dark:text-blue-200/80"> — {stage.current_item}</span>
          )}
        </div>
      </div>
    );
  }

  if (stage.status === "error") {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3 text-sm text-destructive">
        <span className="font-medium">{label} failed:</span>{" "}
        {stage.error_message ?? "Unknown error"}
      </div>
    );
  }

  return (
    <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-100">
      <span className="font-medium">{label} finished</span>
      {stage.total_items != null && (
        <span>
          {" "}
          — {stage.completed_items ?? 0} / {stage.total_items}
        </span>
      )}
    </div>
  );
}
