import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { api, type EmailDraft } from "@/lib/api";
import { CheckCircle2, Send } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/emails")({
  component: EmailsPage,
});

const ALL = "__all__";

function EmailsPage() {
  const [status, setStatus] = useState<string>("pending");

  const emailsQuery = useQuery({
    queryKey: ["emails", status],
    queryFn: () => api.emails({ status: status === ALL ? undefined : status }),
  });

  const drafts = emailsQuery.data ?? [];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageHeader />

      <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Email drafts ({drafts.length})</h2>
            <p className="text-xs text-muted-foreground">
              Review each draft, edit if needed, then approve or reject.
            </p>
          </div>
          <div className="w-48">
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {emailsQuery.error ? (
          <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
            Failed to load: {(emailsQuery.error as Error).message}
          </div>
        ) : emailsQuery.isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-40 w-full" />
            ))}
          </div>
        ) : drafts.length === 0 ? (
          <div className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">
            No email drafts match this filter yet. Generate some from the Research page's
            "Personalize emails" action.
          </div>
        ) : (
          <div className="space-y-4">
            {drafts.map((draft) => (
              // Keying on updated_at too so a refetch after a stale-conflict
              // (409) remounts the card with the fresh server text, instead
              // of keeping the rejected local edit in state.
              <EmailCard key={`${draft.contact_key}:${draft.updated_at}`} draft={draft} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function EmailCard({ draft }: { draft: EmailDraft }) {
  const qc = useQueryClient();
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);

  const mutation = useMutation({
    mutationFn: (nextStatus: "approved" | "rejected") =>
      api.updateEmail(draft.contact_key, {
        subject,
        body,
        status: nextStatus,
        expected_updated_at: draft.updated_at,
      }),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["emails"] });
      toast.success(updated.status === "approved" ? "Approved" : "Rejected");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to update draft");
      qc.invalidateQueries({ queryKey: ["emails"] });
    },
  });

  const pushMutation = useMutation({
    mutationFn: () => api.pushToOutlook(draft.contact_key),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["emails"] });
      toast.success("Draft created in Outlook");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to create draft in Outlook");
    },
  });

  return (
    <div className="space-y-3 rounded-md border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="font-semibold">{draft.contact_name ?? "Unknown contact"}</span>
          {draft.title && <span className="ml-2 text-xs text-muted-foreground">{draft.title}</span>}
          <span className="mx-1 text-xs text-muted-foreground">·</span>
          <span className="text-xs text-muted-foreground">{draft.company_name}</span>
        </div>
        <StatusBadge status={draft.status} />
      </div>

      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">Subject</label>
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
      </div>

      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">Body</label>
        <Textarea value={body} onChange={(e) => setBody(e.target.value)} className="min-h-40" />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          {draft.status === "approved" &&
            (draft.outlook_draft_id ? (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                Draft created in Outlook
              </span>
            ) : (
              <Button
                size="sm"
                variant="outline"
                disabled={pushMutation.isPending}
                onClick={() => pushMutation.mutate()}
                className="gap-2"
              >
                <Send className="h-4 w-4" />
                {pushMutation.isPending ? "Creating..." : "Create draft in Outlook"}
              </Button>
            ))}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate("rejected")}
          >
            Reject
          </Button>
          <Button
            size="sm"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate("approved")}
          >
            Approve
          </Button>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "approved" ? "default" : status === "rejected" ? "destructive" : "secondary";
  return <Badge variant={variant as "default" | "destructive" | "secondary"}>{status}</Badge>;
}
