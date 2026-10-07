/** Copy and settings for the first-visit loader (GdLoader instance props). */
export type LoaderCopy = {
  enabled: boolean;
  /** Play on the first page of a visit only (remembered in sessionStorage). */
  once: boolean;
  /** Seconds until the beam is hoisted away; the lift-off adds about 1s. Clamped to 1.8–4. */
  duration: number;
  /** Text on the beam. Empty = the site name. */
  wordmark: string;
  /** Line after the tag. Empty = the site's service area. */
  place: string;
  /** The counter runs from L00 to this level (1–99). */
  topLevel: number;
  tag: string;
  /** One word per stage: hook on, lifting, set down. */
  statuses: string[];
  counterLabel: string;
  skipLabel: string;
};

export const loader: LoaderCopy = {
  enabled: true,
  once: true,
  duration: 2.4,
  wordmark: '',
  place: '',
  topLevel: 16,
  tag: 'Plan to build',
  statuses: ['Plan', 'Compare', 'Build'],
  counterLabel: 'Stage',
  skipLabel: 'Skip',
};
