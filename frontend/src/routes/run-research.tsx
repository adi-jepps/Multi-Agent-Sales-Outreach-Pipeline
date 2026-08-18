import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { api, type LeadDetail, type LeadTableRow } from "@/lib/api";
import { Columns3, Play, Users } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { PipelineStatusBanner } from "@/components/pipeline-status-banner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type ColumnKey = keyof LeadTableRow;

const COLUMNS: { key: ColumnKey; label: string }[] = [
  { key: "lead_id", label: "Lead ID" },
  { key: "company_name", label: "Company" },
  { key: "industry", label: "Industry" },
  { key: "website", label: "Website" },
  { key: "contact_name", label: "Contact" },
  { key: "title", label: "Title" },
  { key: "email", label: "Email" },
  { key: "person_linkedin_url", label: "LinkedIn" },
  { key: "research_status", label: "Research status" },
  { key: "values_alignment", label: "Values alignment" },
  { key: "recent_relevant_news", label: "Recent news" },
  { key: "facility_notes", label: "Facility notes" },
];

const DEFAULT_VISIBLE: ColumnKey[] = [
  "lead_id",
  "company_name",
  "industry",
  "contact_name",
  "title",
  "email",
  "research_status",
];

export const Route = createFileRoute("/run-research")({
  component: RunResearchPage,
});

const ALL = "__all__";

type Filters = { industry: string; research_status: string };

function RunResearchPage() {
  const [filters, setFilters] = useState<Filters>({
    industry: ALL,
    research_status: ALL,
  });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const filtersQuery = useQuery({
    queryKey: ["filters"],
    queryFn: () => api.filters(),
  });

  const apiParams = useMemo(
    () => ({
      industry: filters.industry === ALL ? undefined : filters.industry,
      research_status: filters.research_status === ALL ? undefined : filters.research_status,
    }),
    [filters],
  );

  const statusQuery = useQuery({
    queryKey: ["pipeline-status"],
    queryFn: () => api.pipelineStatus(),
    refetchInterval: 3000,
    refetchIntervalInBackground: true,
  });
  const isResearchRunning = (statusQuery.data ?? []).some(
    (s) => s.stage === "research" && s.status === "running",
  );

  const qc = useQueryClient();
  const runMutation = useMutation({
    mutationFn: (leadIds?: number[]) => api.runResearch(leadIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline-status"] });
      toast.success("Research run started");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to start research run");
    },
  });
  const researchDisabled = isResearchRunning || runMutation.isPending;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageHeader />

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <PipelineStatusBanner stages={statusQuery.data} />

        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border bg-card p-4">
          <div>
            <h2 className="text-sm font-semibold">Run company research</h2>
            <p className="text-xs text-muted-foreground">
              Research runs per company, not per contact — selecting any contact re-researches their
              whole company.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={researchDisabled || selectedIds.size === 0}
              onClick={() => runMutation.mutate(Array.from(selectedIds))}
              className="gap-2"
            >
              <Users className="h-4 w-4" />
              Run for selected ({selectedIds.size})
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={researchDisabled}
              onClick={() => runMutation.mutate(undefined)}
              className="gap-2"
            >
              <Play className="h-4 w-4" />
              Run for all leads
            </Button>
          </div>
        </div>

        <FiltersBar
          filters={filters}
          onChange={setFilters}
          options={filtersQuery.data}
          loading={filtersQuery.isLoading}
        />

        <div className="mt-6">
          <LeadsTableView
            filters={apiParams}
            onSelect={(id) => setSelectedId(id)}
            selectedId={selectedId}
            selectedIds={selectedIds}
            onSelectedIdsChange={setSelectedIds}
          />
        </div>
      </main>

      <Sheet
        open={selectedId !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedId(null);
        }}
      >
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          {selectedId !== null && <LeadDetailPanel id={selectedId} />}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function FiltersBar({
  filters,
  onChange,
  options,
  loading,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  options: { industries: string[]; research_statuses: string[] } | undefined;
  loading: boolean;
}) {
  const set = (key: keyof Filters) => (value: string) => onChange({ ...filters, [key]: value });

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <FilterSelect
        label="Industry"
        value={filters.industry}
        onChange={set("industry")}
        options={options?.industries ?? []}
        loading={loading}
      />
      <FilterSelect
        label="Research status"
        value={filters.research_status}
        onChange={set("research_status")}
        options={options?.research_statuses ?? []}
        loading={loading}
      />
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
  loading,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  loading: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <Select value={value} onValueChange={onChange} disabled={loading}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder={loading ? "Loading..." : "All"} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All</SelectItem>
          {options.map((o) => (
            <SelectItem key={o} value={o}>
              {o}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function LeadDetailPanel({ id }: { id: number }) {
  const detailQuery = useQuery({
    queryKey: ["lead", id],
    queryFn: () => api.lead(id),
  });

  if (detailQuery.isLoading) {
    return (
      <div className="space-y-4 py-4">
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (detailQuery.error) {
    return (
      <div className="py-4 text-sm text-destructive">
        Failed to load: {(detailQuery.error as Error).message}
      </div>
    );
  }

  const lead = detailQuery.data as LeadDetail;

  return (
    <div className="space-y-6">
      <SheetHeader className="space-y-1 px-0">
        <SheetTitle>{lead.company?.name ?? "Lead"}</SheetTitle>
        <SheetDescription>{lead.contact?.full_name ?? "Lead details"}</SheetDescription>
        {lead.company?.industry && (
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">{lead.company.industry}</Badge>
          </div>
        )}
      </SheetHeader>

      <Section title="Company">
        {lead.company ? (
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            <Field label="Name" value={lead.company.name} />
            <Field
              label="Location"
              value={[lead.company.city, lead.company.state, lead.company.country]
                .filter(Boolean)
                .join(", ")}
            />
            <Field label="Industry" value={lead.company.industry} />
            <Field
              label="Website"
              value={
                lead.company.website ? (
                  <a
                    href={lead.company.website}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline underline-offset-2"
                  >
                    {lead.company.website}
                  </a>
                ) : null
              }
            />
            <Field
              label="Company LinkedIn"
              value={
                lead.company.linkedin_url ? (
                  <a
                    href={lead.company.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline underline-offset-2 break-all"
                  >
                    {lead.company.linkedin_url}
                  </a>
                ) : null
              }
            />
          </dl>
        ) : (
          <EmptyNote>No company data.</EmptyNote>
        )}
      </Section>

      <Section title="Contact">
        {lead.contact ? (
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            <Field label="Name" value={lead.contact.full_name} />
            <Field label="Title" value={lead.contact.title} />
            <Field label="Email" value={lead.contact.email} />
            <Field
              label="LinkedIn"
              value={
                lead.contact.linkedin_url ? (
                  <a
                    href={lead.contact.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline underline-offset-2 break-all"
                  >
                    {lead.contact.linkedin_url}
                  </a>
                ) : null
              }
            />
          </dl>
        ) : (
          <EmptyNote>No contact assigned.</EmptyNote>
        )}
      </Section>

      <Section title="Research">
        {lead.research ? (
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs font-medium text-muted-foreground">Values alignment</dt>
              <dd className="mt-0.5">{lead.research.values_alignment}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground">Recent relevant news</dt>
              <dd className="mt-0.5">{lead.research.recent_relevant_news}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground">Facility notes</dt>
              <dd className="mt-0.5">{lead.research.facility_notes}</dd>
            </div>
          </dl>
        ) : (
          <EmptyNote>Not yet researched.</EmptyNote>
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Field({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode | string | null | undefined;
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">
        {value == null || value === "" ? <span className="text-muted-foreground">—</span> : value}
      </dd>
    </div>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-dashed bg-muted/30 p-3 text-sm text-muted-foreground">
      {children}
    </p>
  );
}

function LeadsTableView({
  filters,
  onSelect,
  selectedId,
  selectedIds,
  onSelectedIdsChange,
}: {
  filters: { industry?: string; research_status?: string };
  onSelect: (id: number) => void;
  selectedId: number | null;
  selectedIds: Set<number>;
  onSelectedIdsChange: (ids: Set<number>) => void;
}) {
  const [visible, setVisible] = useState<Set<ColumnKey>>(() => new Set(DEFAULT_VISIBLE));
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(1);

  const tableQuery = useQuery({
    queryKey: ["leads-table", filters],
    queryFn: () => api.leadsTable(filters),
  });

  const toggle = (key: ColumnKey) => {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const shownColumns = COLUMNS.filter((c) => visible.has(c.key));
  const rows = tableQuery.data ?? [];

  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedRows = rows.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  useEffect(() => {
    setPage(1);
  }, [filters, pageSize]);

  const pagedIds = pagedRows.map((r) => r.lead_id);
  const allPagedSelected = pagedIds.length > 0 && pagedIds.every((id) => selectedIds.has(id));

  const toggleRow = (id: number) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectedIdsChange(next);
  };

  const toggleAllOnPage = () => {
    const next = new Set(selectedIds);
    if (allPagedSelected) {
      pagedIds.forEach((id) => next.delete(id));
    } else {
      pagedIds.forEach((id) => next.add(id));
    }
    onSelectedIdsChange(next);
  };

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">All columns</h2>
          <p className="text-xs text-muted-foreground">
            {tableQuery.isLoading
              ? "Loading..."
              : rows.length === 0
                ? "0 rows"
                : `Showing ${(currentPage - 1) * pageSize + 1}-${Math.min(currentPage * pageSize, rows.length)} of ${rows.length} row${rows.length === 1 ? "" : "s"}${selectedIds.size > 0 ? ` — ${selectedIds.size} selected` : ""}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <PageSizeSelect value={pageSize} onChange={setPageSize} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2">
                <Columns3 className="h-4 w-4" />
                Columns ({visible.size}/{COLUMNS.length})
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="max-h-96 w-56 overflow-y-auto">
              <DropdownMenuLabel>Toggle columns</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {COLUMNS.map((c) => (
                <DropdownMenuCheckboxItem
                  key={c.key}
                  checked={visible.has(c.key)}
                  onCheckedChange={() => toggle(c.key)}
                  onSelect={(e) => e.preventDefault()}
                >
                  {c.label}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {tableQuery.error ? (
        <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
          Failed to load: {(tableQuery.error as Error).message}
        </div>
      ) : tableQuery.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">
          No leads match the current filters.
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-x-auto rounded-md border bg-card md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      checked={allPagedSelected}
                      onCheckedChange={toggleAllOnPage}
                      aria-label="Select all on page"
                    />
                  </TableHead>
                  {shownColumns.map((c) => (
                    <TableHead key={c.key} className="whitespace-nowrap">
                      {c.label}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagedRows.map((lead) => (
                  <TableRow
                    key={lead.lead_id}
                    data-selected={selectedId === lead.lead_id}
                    className="cursor-pointer data-[selected=true]:bg-muted"
                  >
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={selectedIds.has(lead.lead_id)}
                        onCheckedChange={() => toggleRow(lead.lead_id)}
                        aria-label={`Select ${lead.company_name ?? "lead"}`}
                      />
                    </TableCell>
                    {shownColumns.map((c) => (
                      <TableCell
                        key={c.key}
                        className="whitespace-nowrap align-top text-sm"
                        onClick={() => onSelect(lead.lead_id)}
                      >
                        {renderCell(lead, c.key)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Mobile stacked cards */}
          <div className="space-y-2 md:hidden">
            {pagedRows.map((lead) => (
              <div
                key={lead.lead_id}
                data-selected={selectedId === lead.lead_id}
                className="w-full rounded-md border bg-card p-4 text-left transition hover:bg-muted data-[selected=true]:bg-muted"
              >
                <div className="mb-2 flex items-center justify-between">
                  <Checkbox
                    checked={selectedIds.has(lead.lead_id)}
                    onCheckedChange={() => toggleRow(lead.lead_id)}
                    aria-label={`Select ${lead.company_name ?? "lead"}`}
                  />
                  <button
                    onClick={() => onSelect(lead.lead_id)}
                    className="text-xs text-primary underline underline-offset-2"
                  >
                    View details
                  </button>
                </div>
                <dl className="grid grid-cols-1 gap-2">
                  {shownColumns.map((c) => (
                    <div
                      key={c.key}
                      className="flex justify-between gap-3 border-b pb-1 last:border-b-0 last:pb-0"
                    >
                      <dt className="text-xs text-muted-foreground">{c.label}</dt>
                      <dd className="text-right text-sm">{renderCell(lead, c.key)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between gap-2 pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {currentPage} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </section>
  );
}

function PageSizeSelect({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <Select value={String(value)} onValueChange={(v) => onChange(Number(v))}>
      <SelectTrigger className="w-[110px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {[10, 25, 50, 100].map((n) => (
          <SelectItem key={n} value={String(n)}>
            {n} / page
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function renderCell(lead: LeadTableRow, key: ColumnKey) {
  const v = lead[key];
  if (key === "research_status" && typeof v === "string" && v) {
    const variant = v === "researched" ? "default" : v === "error" ? "destructive" : "secondary";
    return <Badge variant={variant as "default" | "destructive" | "secondary"}>{v}</Badge>;
  }
  if (key === "website" && typeof v === "string" && v) {
    return (
      <a
        href={v}
        target="_blank"
        rel="noreferrer"
        className="text-primary underline underline-offset-2"
      >
        {v.replace(/^https?:\/\//, "")}
      </a>
    );
  }
  if (key === "person_linkedin_url" && typeof v === "string" && v) {
    return (
      <a
        href={v}
        target="_blank"
        rel="noreferrer"
        className="text-primary underline underline-offset-2"
      >
        LinkedIn
      </a>
    );
  }
  if (
    (key === "values_alignment" || key === "recent_relevant_news" || key === "facility_notes") &&
    typeof v === "string" &&
    v
  ) {
    return (
      <span className="block max-w-xs truncate text-muted-foreground" title={v}>
        {v}
      </span>
    );
  }
  if (v === "" || v === null || v === undefined) {
    return <span className="text-muted-foreground">—</span>;
  }
  return String(v);
}
