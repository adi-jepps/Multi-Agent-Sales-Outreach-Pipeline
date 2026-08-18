import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import type { BucketCount, DashboardStats, LabelCount } from "@/lib/api";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

const SEQUENTIAL_CONFIG: ChartConfig = {
  count: { label: "Companies", color: "var(--viz-sequential)" },
};

type StatusSegment = { key: string; label: string; count: number; colorVar: string };

export function PipelineStatusRow({ stats }: { stats: DashboardStats["pipeline"] }) {
  const researchSegments: StatusSegment[] = [
    {
      key: "researched",
      label: "Researched",
      count: stats.research.researched,
      colorVar: "var(--viz-status-good)",
    },
    {
      key: "pending",
      label: "Pending",
      count: stats.research.pending,
      colorVar: "var(--viz-status-warning)",
    },
    {
      key: "error",
      label: "Error",
      count: stats.research.error,
      colorVar: "var(--viz-status-critical)",
    },
  ];
  const emailSegments: StatusSegment[] = [
    {
      key: "approved",
      label: "Approved",
      count: stats.emails.approved,
      colorVar: "var(--viz-status-good)",
    },
    {
      key: "pending",
      label: "Pending review",
      count: stats.emails.pending,
      colorVar: "var(--viz-status-warning)",
    },
    {
      key: "rejected",
      label: "Rejected",
      count: stats.emails.rejected,
      colorVar: "var(--viz-status-critical)",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <StatusProgressBar
        title="Research pipeline"
        segments={researchSegments}
        total={stats.research.total}
      />
      <StatusProgressBar
        title="Email approvals"
        segments={emailSegments}
        total={stats.emails.total}
      />
    </div>
  );
}

function StatusProgressBar({
  title,
  segments,
  total,
}: {
  title: string;
  segments: StatusSegment[];
  total: number;
}) {
  return (
    <div className="rounded-md border bg-card p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {total === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">No data yet.</p>
      ) : (
        <>
          <div className="mt-3 flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-muted">
            {segments
              .filter((s) => s.count > 0)
              .map((s) => (
                <div
                  key={s.key}
                  className="h-full first:rounded-l-full last:rounded-r-full"
                  style={{ width: `${(s.count / total) * 100}%`, backgroundColor: s.colorVar }}
                  title={`${s.label}: ${s.count}`}
                />
              ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
            {segments.map((s) => (
              <div key={s.key} className="flex items-center gap-1.5 text-xs">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: s.colorVar }}
                  aria-hidden
                />
                <span className="text-muted-foreground">{s.label}</span>
                <span className="font-medium tabular-nums text-foreground">{s.count}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function BucketBarChart({
  title,
  data,
  caption,
}: {
  title: string;
  data: BucketCount[];
  caption?: string;
}) {
  return (
    <div className="rounded-md border bg-card p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {caption && <p className="text-xs text-muted-foreground">{caption}</p>}
      <ChartContainer config={SEQUENTIAL_CONFIG} className="mt-2 aspect-auto h-56 w-full">
        <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="bucket" tickLine={false} axisLine={false} fontSize={11} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={28} fontSize={11} />
          <ChartTooltip
            content={<ChartTooltipContent hideLabel nameKey="count" />}
            cursor={{ fill: "var(--muted)" }}
          />
          <Bar dataKey="count" fill="var(--color-count)" radius={[4, 4, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ChartContainer>
    </div>
  );
}

export function LabelBarChart({
  title,
  data,
  caption,
}: {
  title: string;
  data: LabelCount[];
  caption?: string;
}) {
  const height = Math.max(160, data.length * 34);

  return (
    <div className="rounded-md border bg-card p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {caption && <p className="text-xs text-muted-foreground">{caption}</p>}
      <ChartContainer
        config={SEQUENTIAL_CONFIG}
        className="mt-2 aspect-auto w-full"
        style={{ height }}
      >
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          <XAxis
            type="number"
            allowDecimals={false}
            tickLine={false}
            axisLine={false}
            fontSize={11}
          />
          <YAxis
            type="category"
            dataKey="label"
            tickLine={false}
            axisLine={false}
            width={170}
            fontSize={11}
            tickFormatter={(v: string) => (v.length > 24 ? `${v.slice(0, 24)}…` : v)}
          />
          <ChartTooltip
            content={<ChartTooltipContent hideLabel nameKey="count" />}
            cursor={{ fill: "var(--muted)" }}
          />
          <Bar dataKey="count" fill="var(--color-count)" radius={[0, 4, 4, 0]} maxBarSize={20} />
        </BarChart>
      </ChartContainer>
    </div>
  );
}
