import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { Play, Upload, Users } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { PipelineStatusBanner } from "@/components/pipeline-status-banner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/research")({
  component: ResearchPage,
});

const ALL = "__all__";

function ResearchPage() {
  const [status, setStatus] = useState<string>("researched");
  const [selectedCompanyKeys, setSelectedCompanyKeys] = useState<Set<string>>(new Set());
  const [personalizeOpen, setPersonalizeOpen] = useState(false);

  const companiesQuery = useQuery({
    queryKey: ["companies", status],
    queryFn: () => api.companies({ research_status: status === ALL ? undefined : status }),
  });

  const statusQuery = useQuery({
    queryKey: ["pipeline-status"],
    queryFn: () => api.pipelineStatus(),
    refetchInterval: 3000,
    refetchIntervalInBackground: true,
  });
  const isPersonalizeRunning = (statusQuery.data ?? []).some(
    (s) => s.stage === "personalize" && s.status === "running",
  );

  const companies = companiesQuery.data ?? [];

  const toggleCompany = (companyKey: string) => {
    setSelectedCompanyKeys((prev) => {
      const next = new Set(prev);
      if (next.has(companyKey)) next.delete(companyKey);
      else next.add(companyKey);
      return next;
    });
  };

  const selectedLeadIds = companies
    .filter((c) => selectedCompanyKeys.has(c.company_key))
    .flatMap((c) => c.lead_ids);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageHeader />

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
        <PipelineStatusBanner stages={statusQuery.data} />

        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border bg-card p-4">
          <div>
            <h2 className="text-sm font-semibold">Personalize each email</h2>
            <p className="text-xs text-muted-foreground">
              Select companies below, then generate a personalized draft per contact using the
              campaign agenda and their research.
            </p>
          </div>
          <Button
            size="sm"
            variant="secondary"
            disabled={isPersonalizeRunning}
            onClick={() => setPersonalizeOpen(true)}
          >
            Personalize emails
          </Button>
        </div>

        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Companies ({companies.length})</h2>
            <p className="text-xs text-muted-foreground">
              Grouped by company — research runs once per company, not per contact.
              {selectedCompanyKeys.size > 0 && ` — ${selectedCompanyKeys.size} selected`}
            </p>
          </div>
          <div className="w-48">
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All statuses</SelectItem>
                <SelectItem value="researched">Researched</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="error">Error</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {companiesQuery.error ? (
          <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
            Failed to load: {(companiesQuery.error as Error).message}
          </div>
        ) : companiesQuery.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : companies.length === 0 ? (
          <div className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">
            No companies match this filter.
          </div>
        ) : (
          <Accordion type="multiple" className="rounded-md border bg-card px-4">
            {companies.map((c) => (
              <AccordionItem key={c.company_key} value={c.company_key}>
                <div className="flex items-center gap-3">
                  <div onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={selectedCompanyKeys.has(c.company_key)}
                      onCheckedChange={() => toggleCompany(c.company_key)}
                      aria-label={`Select ${c.company_name ?? "company"}`}
                    />
                  </div>
                  <AccordionTrigger className="flex-1">
                    <div className="flex flex-1 flex-wrap items-center justify-between gap-2 pr-2 text-left">
                      <div>
                        <span className="font-semibold">{c.company_name ?? "Unknown company"}</span>
                        {c.industry && (
                          <span className="ml-2 text-xs text-muted-foreground">{c.industry}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          {c.contact_count} contact{c.contact_count === 1 ? "" : "s"}
                        </span>
                        <StatusBadge status={c.research_status} />
                      </div>
                    </div>
                  </AccordionTrigger>
                </div>
                <AccordionContent>
                  {c.research_status === "pending" ? (
                    <p className="text-sm text-muted-foreground">Not yet researched.</p>
                  ) : (
                    <dl className="space-y-3 text-sm">
                      <ResearchField label="Values alignment" value={c.values_alignment} />
                      <ResearchField label="Recent relevant news" value={c.recent_relevant_news} />
                      <ResearchField label="Facility notes" value={c.facility_notes} />
                    </dl>
                  )}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </main>

      <PersonalizeDialog
        open={personalizeOpen}
        onOpenChange={setPersonalizeOpen}
        selectedLeadIds={selectedLeadIds}
        isPersonalizeRunning={isPersonalizeRunning}
      />
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "researched" ? "default" : status === "error" ? "destructive" : "secondary";
  return <Badge variant={variant as "default" | "destructive" | "secondary"}>{status}</Badge>;
}

function ResearchField({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-0.5">{value || "—"}</dd>
    </div>
  );
}

function PersonalizeDialog({
  open,
  onOpenChange,
  selectedLeadIds,
  isPersonalizeRunning,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedLeadIds: number[];
  isPersonalizeRunning: boolean;
}) {
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [agendaText, setAgendaText] = useState("");
  const [seeded, setSeeded] = useState(false);

  const agendaQuery = useQuery({
    queryKey: ["campaign-agenda"],
    queryFn: () => api.campaignAgenda(),
    enabled: open,
  });

  useEffect(() => {
    if (open && !seeded && agendaQuery.data) {
      setAgendaText(agendaQuery.data.text);
      setSeeded(true);
    }
    if (!open) setSeeded(false);
  }, [open, seeded, agendaQuery.data]);

  const extractMutation = useMutation({
    mutationFn: (file: File) => api.extractAgendaFile(file),
    onSuccess: (result) => {
      setAgendaText(result.text);
      toast.success("Extracted text from file — review it below before running");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to extract text from file");
    },
  });

  const runMutation = useMutation({
    mutationFn: (leadIds: number[] | undefined) => api.runPersonalize(leadIds, agendaText),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline-status"] });
      toast.success("Personalization started");
      onOpenChange(false);
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to start personalization");
    },
  });

  const disabled = isPersonalizeRunning || runMutation.isPending || agendaText.trim().length === 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Personalize emails</DialogTitle>
          <DialogDescription>
            Type or upload the campaign agenda — it's combined with each contact's company research
            to write a personalized draft. Review drafts on the Pending approvals page before
            anything is sent.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Textarea
            value={agendaText}
            onChange={(e) => setAgendaText(e.target.value)}
            placeholder="e.g. Q3 campaign: sustainable lighting remanufacturing for public-sector estates. Emphasize carbon reduction and cost savings vs new fixtures..."
            className="min-h-40"
          />
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) extractMutation.mutate(file);
                e.target.value = "";
              }}
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={extractMutation.isPending}
              onClick={() => fileInputRef.current?.click()}
              className="gap-2"
            >
              <Upload className="h-4 w-4" />
              {extractMutation.isPending ? "Extracting..." : "Upload PDF/DOCX"}
            </Button>
            <span className="text-xs text-muted-foreground">Replaces the text above</span>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            variant="secondary"
            disabled={disabled || selectedLeadIds.length === 0}
            onClick={() => runMutation.mutate(selectedLeadIds)}
            className="gap-2"
          >
            <Users className="h-4 w-4" />
            Personalize selected ({selectedLeadIds.length})
          </Button>
          <Button
            variant="outline"
            disabled={disabled}
            onClick={() => runMutation.mutate(undefined)}
            className="gap-2"
          >
            <Play className="h-4 w-4" />
            Personalize all researched leads
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
