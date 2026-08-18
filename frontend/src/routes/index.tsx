import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Sparkles, Mail, Clock } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { PipelineStatusBanner } from "@/components/pipeline-status-banner";
import { BucketBarChart, LabelBarChart, PipelineStatusRow } from "@/components/dashboard-charts";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/")({
  component: HomePage,
});

function HomePage() {
  const statusQuery = useQuery({
    queryKey: ["pipeline-status"],
    queryFn: () => api.pipelineStatus(),
    refetchInterval: 3000,
    refetchIntervalInBackground: true,
  });

  const statsQuery = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.dashboardStats(),
  });

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageHeader />

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <PipelineStatusBanner stages={statusQuery.data} />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <NavCard
            to="/run-research"
            icon={Sparkles}
            title="Run company research"
            description="Browse leads, select which ones to research, and track progress as CrewAI investigates each company."
          />
          <NavCard
            to="/research"
            icon={Mail}
            title="Personalize each email"
            description="Review completed company research, then generate tailored outreach emails per contact using a campaign agenda."
          />
          <NavCard
            to="/emails"
            icon={Clock}
            title="Pending approvals"
            description="Review, edit, and approve or reject generated email drafts before anything is sent."
          />
        </div>

        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Pipeline overview
          </h2>
          {statsQuery.isLoading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          ) : statsQuery.error ? (
            <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
              Failed to load dashboard stats: {(statsQuery.error as Error).message}
            </div>
          ) : statsQuery.data ? (
            <PipelineStatusRow stats={statsQuery.data.pipeline} />
          ) : null}
        </div>

        {statsQuery.data && (
          <div className="mt-8">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Market overview
            </h2>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <BucketBarChart
                title="Company size"
                data={statsQuery.data.company_size}
                caption="By number of employees, one bar per company"
              />
              <BucketBarChart
                title="Annual revenue"
                data={statsQuery.data.revenue.buckets}
                caption={`${statsQuery.data.revenue.companies_with_data} of ${statsQuery.data.revenue.total_companies} companies have revenue data on file`}
              />
              <LabelBarChart
                title="Industry mix"
                data={statsQuery.data.industry}
                caption="One count per company"
              />
              <LabelBarChart
                title="Buying personas"
                data={statsQuery.data.titles}
                caption="Top job titles across all contacts"
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function NavCard({
  to,
  icon: Icon,
  title,
  description,
}: {
  to: "/run-research" | "/research" | "/emails";
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <Link
      to={to}
      className="group flex flex-col gap-3 rounded-md border bg-card p-4 transition-colors hover:border-primary/50 hover:bg-accent"
    >
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <p className="text-xs text-muted-foreground">{description}</p>
      <span className="mt-auto flex items-center gap-1 text-xs font-medium text-primary">
        Go to page
        <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
