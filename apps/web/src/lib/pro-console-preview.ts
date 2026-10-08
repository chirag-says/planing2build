// Sample data for the command center's states, for local design review only (`?preview=listed`,
// `working` or `multi` on the dashboard outside production). Every object has the API's own shape,
// so the same buildConsole rules run on it. Never used in production builds.
import type { Connection, ConsoleInput, Dashboard, Invitation, Stage, WonProject } from "@/lib/pro-console";

export const PREVIEW_STATES = ["listed", "working", "multi"] as const;
export type PreviewState = (typeof PREVIEW_STATES)[number];

export function previewAllowed(value: unknown): value is PreviewState {
  return process.env.NODE_ENV !== "production" && PREVIEW_STATES.includes(value as PreviewState);
}

const STAGE_NAMES = [
  "Pre-construction",
  "Excavation",
  "Foundation",
  "Plinth",
  "Superstructure",
  "Roof slab",
  "Masonry",
  "Electrical rough-in",
  "Plumbing rough-in",
  "Plastering",
  "Flooring",
  "Doors and windows",
  "Painting",
  "Fixtures",
  "External works",
  "Handover",
];

function iso(now: Date, days: number, hours = 0): string {
  return new Date(now.getTime() + days * 86_400_000 + hours * 3_600_000).toISOString();
}

/** Sixteen stages, complete up to `current`, which is in `state`. */
function stages(current: number, state: Stage["state"], gate?: Stage["gate_status"]): Stage[] {
  return STAGE_NAMES.map((name, index) => {
    const n = index + 1;
    return {
      id: `stage-${n}`,
      name,
      stage_number: n,
      sequence: n,
      floor: null,
      state: n < current ? "COMPLETED" : n === current ? state : "NOT_STARTED",
      is_gate: n === 3 || n === 5,
      is_payment_milestone: n % 3 === 0,
      gate_status: n === current && gate ? gate : null,
      actual_start: null,
      actual_end: null,
      completion_requested_at: null,
      last_update_at: null,
      update_count: n <= current ? 3 : 0,
      version: 1,
    };
  });
}

function connection(now: Date, id: string, over: Partial<Connection>): Connection {
  return {
    id,
    category: "CONTRACTOR",
    category_name: "Contractor",
    state: "SENT",
    respond_by: iso(now, 3),
    responded_at: null,
    sent_at: iso(now, -1),
    engagement_state: null,
    decline_note: null,
    decline_reason: null,
    withdraw_reason: null,
    family_contact: null,
    location: null,
    shared_files: [],
    brief: {
      category: "CONTRACTOR",
      locality: "Shankar Nagar",
      built_up_area_sqft: 2450,
      plot_area_sqft: "2400",
      floors: 2,
      basement: false,
      budget_band: null,
      start_window: null,
      services: [],
      subtypes: [],
    },
    ...over,
  };
}

function invitation(now: Date, id: string, over: Partial<Invitation>): Invitation {
  return {
    id,
    locality: "Devendra Nagar",
    state: "ACCEPTED",
    rfq_open: true,
    outcome: null,
    respond_by: iso(now, 2),
    quotes_due_at: iso(now, 5),
    sent_at: iso(now, -4),
    ...over,
  };
}

function listed(dashboard: Dashboard, now: Date): Dashboard {
  const name = dashboard.profile.display_name ?? "Asha Verma";
  return {
    ...dashboard,
    profile: {
      ...dashboard.profile,
      display_name: name,
      firm_name: dashboard.profile.firm_name ?? "Verma Build Studio",
      base_locality: dashboard.profile.base_locality ?? "Civil Lines",
      years_experience: dashboard.profile.years_experience ?? 12,
      team_size: dashboard.profile.team_size ?? 8,
      missing: [],
    },
    categories: [
      {
        code: "CONTRACTOR",
        name: "Contractor",
        listing_state: "LISTED",
        public: true,
        hidden: false,
        listed_at: iso(now, -120),
        review_due_at: iso(now, 245),
        submitted_at: iso(now, -130),
        message: null,
        missing_requirements: [],
        reapply_after: null,
        requirements: [],
        subtypes: [],
      },
      {
        code: "SITE_ENGINEER",
        name: "Site/civil engineer",
        listing_state: "PENDING_REVIEW",
        public: false,
        hidden: false,
        listed_at: null,
        review_due_at: null,
        submitted_at: iso(now, -2),
        message: null,
        missing_requirements: [],
        reapply_after: null,
        requirements: [],
        subtypes: [],
      },
    ],
    portfolio: dashboard.portfolio.length
      ? dashboard.portfolio
      : [{ item_id: "p1", caption: "Courtyard house", review_state: "APPROVED", file: null }],
  };
}

export function previewInput(state: PreviewState, dashboard: Dashboard, now: Date): ConsoleInput {
  const base = listed(dashboard, now);
  const history: Connection[] = [
    connection(now, "c-old-1", { state: "DECLINED", responded_at: iso(now, -40), sent_at: iso(now, -42) }),
    connection(now, "c-old-2", { state: "ACCEPTED", responded_at: iso(now, -60), sent_at: iso(now, -61), engagement_state: "ENDED" }),
    connection(now, "c-old-3", { state: "EXPIRED", responded_at: null, sent_at: iso(now, -90) }),
  ];
  const inbound: Connection[] = [
    connection(now, "c-new-1", { respond_by: iso(now, 1, 2) }),
    connection(now, "c-new-2", { respond_by: iso(now, 3), brief: { ...connection(now, "x", {}).brief, locality: "Telibandha" } }),
  ];
  const rfqs: Invitation[] = [
    invitation(now, "i-open-1", { quotes_due_at: iso(now, 1, 4) }),
    invitation(now, "i-sent-1", { state: "SENT", rfq_open: true, respond_by: iso(now, 4), locality: "Avanti Vihar" }),
    invitation(now, "i-quoted-1", { outcome: "SUBMITTED", locality: "Mowa" }),
    invitation(now, "i-quoted-2", { outcome: "SUBMITTED", locality: "Pandri" }),
    invitation(now, "i-lost-1", { outcome: "NOT_SELECTED", rfq_open: false, locality: "Tatibandh" }),
  ];
  if (state === "listed") {
    return { dashboard: base, connections: [...history, ...inbound], invitations: rfqs, inspections: null, won: [], now };
  }
  const won: WonProject[] = [
    {
      invitationId: "i-won-1",
      engagementId: "e-1",
      projectCode: "P2B-00219",
      category: "Contractor",
      startedAt: iso(now, -96),
      ended: false,
      locality: "Shankar Nagar",
      family: "Rahul Sharma",
      stages: stages(5, "IN_PROGRESS"),
    },
  ];
  if (state === "multi") {
    won.push(
      {
        invitationId: "i-won-2",
        engagementId: "e-2",
        projectCode: "P2B-00184",
        category: "Contractor",
        startedAt: iso(now, -180),
        ended: false,
        locality: "Avanti Vihar",
        family: "Meera Iyer",
        stages: stages(9, "IN_PROGRESS", "OPEN_NC"),
      },
      {
        invitationId: "i-won-3",
        engagementId: "e-3",
        projectCode: "P2B-00141",
        category: "Contractor",
        startedAt: iso(now, -260),
        ended: false,
        locality: "Telibandha",
        family: "Anil Deshmukh",
        stages: stages(13, "COMPLETION_REQUESTED"),
      },
    );
  }
  const wonInvites = won.map((p) => invitation(now, p.invitationId, { outcome: "SELECTED", rfq_open: false, locality: p.locality }));
  return {
    dashboard: base,
    connections: [...history, ...(state === "multi" ? inbound : inbound.slice(0, 1))],
    invitations: [...rfqs, ...wonInvites],
    inspections: null,
    won,
    now,
  };
}
