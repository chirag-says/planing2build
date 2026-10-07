/** Content model for the site. */

export type Photo = { src: string; width: number | null; height: number | null };

export type SiteInfo = {
  name: string;
  descriptor: string;
  tagline: string;
  email: string;
  phone: string;
  bidHref: string;
  projectsHref: string;
  area: string;
  proof: string;
  socials: Array<{ label: string; href: string }>;
  projectsBuilt: number;
  licence: string;
  office: string;
  hours: string;
  photo: Photo | null;
};

export type Service = {
  slug: string;
  name: string;
  /** One-line description shown in lists. */
  line: string;
  includes: string[];
  /** Starting fee, e.g. "₹4,999" or "Free". */
  from: string;
  timeline: string;
  detail: string;
  steps: string[];
  /** Markdown. */
  body: string;
  /** "67:decisions with a decide-by date". */
  stat: { value: string; label: string } | null;
  photo: Photo | null;
};

export type ProjectStatus = 'Sample plan' | 'On site' | 'Topped out' | 'Handed over';

export type Project = {
  slug: string;
  name: string;
  place: string;
  type: string;
  floors: number;
  bays: number;
  /** Cost or contract value, e.g. "₹52.3–64.4 L". */
  value: string;
  daysOnSite: number;
  status: ProjectStatus;
  /** Tint used for the building's glass in drawings. */
  glass: string;
  summary: string;
  service: string;
  size: string;
  year: string;
  result: string;
  /** Markdown. */
  body: string;
  scope: string[];
  /** Team member slug. */
  lead: string;
  client: string;
  photo: Photo | null;
  gallery: Photo[];
};

export type TeamMember = {
  slug: string;
  name: string;
  role: string;
  years: number;
  certs: string[];
  quote: string;
  phone: string;
  email: string;
  badge: string;
  /** Markdown. */
  bio: string;
  projects: string[];
  languages: string[];
  photo: Photo | null;
};

export type Review = {
  slug: string;
  name: string;
  role: string;
  quote: string;
  project: string;
  result: string;
  rating: number;
  portrait: Photo | null;
  projectPhoto: Photo | null;
};

export type Faq = { slug: string; question: string; answer: string; group: string };
