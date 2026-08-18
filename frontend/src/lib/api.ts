export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export type LeadTableRow = {
  lead_id: number;
  company_name: string | null;
  industry: string | null;
  website: string | null;
  contact_name: string | null;
  title: string | null;
  email: string | null;
  person_linkedin_url: string | null;
  research_status: "researched" | "pending" | "error";
  values_alignment: string | null;
  recent_relevant_news: string | null;
  facility_notes: string | null;
};

export type LeadDetail = {
  lead_id: number;
  company: {
    name: string | null;
    website: string | null;
    linkedin_url: string | null;
    industry: string | null;
    city: string | null;
    state: string | null;
    country: string | null;
  } | null;
  contact: {
    full_name: string | null;
    title: string | null;
    email: string | null;
    linkedin_url: string | null;
  } | null;
  research: {
    values_alignment: string;
    recent_relevant_news: string;
    facility_notes: string;
  } | null;
};

export type FiltersResponse = {
  industries: string[];
  research_statuses: string[];
};

export type CompanyResearchRow = {
  company_key: string;
  company_name: string | null;
  website: string | null;
  industry: string | null;
  contact_count: number;
  lead_ids: number[];
  research_status: "researched" | "pending" | "error";
  values_alignment: string | null;
  recent_relevant_news: string | null;
  facility_notes: string | null;
};

export type EmailDraft = {
  contact_key: string;
  company_name: string | null;
  contact_name: string | null;
  title: string | null;
  subject: string;
  body: string;
  status: "pending" | "approved" | "rejected";
  updated_at: string;
};

export type CampaignAgendaResponse = {
  text: string;
};

export type BucketCount = {
  bucket: string;
  count: number;
};

export type LabelCount = {
  label: string;
  count: number;
};

export type DashboardStats = {
  pipeline: {
    research: { researched: number; pending: number; error: number; total: number };
    emails: { pending: number; approved: number; rejected: number; total: number };
  };
  company_size: BucketCount[];
  industry: LabelCount[];
  titles: LabelCount[];
  revenue: {
    companies_with_data: number;
    total_companies: number;
    buckets: BucketCount[];
  };
};

export type PipelineStage = {
  stage: string;
  status: "running" | "done" | "error" | string;
  total_items: number | null;
  completed_items: number | null;
  current_item: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail)
        msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // non-JSON error body, fall back to status text
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  filters: () => request<FiltersResponse>("/api/filters"),
  lead: (id: number | string) => request<LeadDetail>(`/api/leads/${id}`),
  leadsTable: (params: { industry?: string; research_status?: string }) => {
    const qs = new URLSearchParams();
    if (params.industry) qs.set("industry", params.industry);
    if (params.research_status) qs.set("research_status", params.research_status);
    const q = qs.toString();
    return request<LeadTableRow[]>(`/api/leads/table${q ? `?${q}` : ""}`);
  },
  companies: (params: { research_status?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.research_status) qs.set("research_status", params.research_status);
    const q = qs.toString();
    return request<CompanyResearchRow[]>(`/api/companies${q ? `?${q}` : ""}`);
  },
  runResearch: (leadIds?: number[]) =>
    request<{ status: string }>("/api/research/run", {
      method: "POST",
      body: JSON.stringify({ lead_ids: leadIds ?? null }),
    }),
  pipelineStatus: () => request<PipelineStage[]>("/api/pipeline-status"),
  dashboardStats: () => request<DashboardStats>("/api/dashboard/stats"),
  campaignAgenda: () => request<CampaignAgendaResponse>("/api/campaign-agenda"),
  extractAgendaFile: async (file: File): Promise<CampaignAgendaResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    // Raw fetch, not the JSON request() helper above - this needs multipart
    // form data, not a Content-Type: application/json body.
    const res = await fetch(`${API_BASE_URL}/api/campaign-agenda/extract`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (body?.detail)
          msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch {
        // non-JSON error body, fall back to status text
      }
      throw new Error(msg);
    }
    return res.json() as Promise<CampaignAgendaResponse>;
  },
  runPersonalize: (leadIds: number[] | undefined, agendaText: string) =>
    request<{ status: string }>("/api/emails/run", {
      method: "POST",
      body: JSON.stringify({ lead_ids: leadIds ?? null, agenda_text: agendaText }),
    }),
  emails: (params: { status?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    const q = qs.toString();
    return request<EmailDraft[]>(`/api/emails${q ? `?${q}` : ""}`);
  },
  updateEmail: (
    contactKey: string,
    patch: { subject?: string; body?: string; status?: string; expected_updated_at: string },
  ) =>
    request<EmailDraft>(`/api/emails/${encodeURIComponent(contactKey)}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
};
