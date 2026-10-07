/** Copy and settings for the page transition "hoist" (GdPageTrans instance props). */
export type HoistCopy = {
  enabled: boolean;
  /** Seconds for the plate to rise and cover the screen. Clamped to 0.3–1.2. */
  duration: number;
  /** Seconds for the plate to lift off the arriving page. Clamped to 0.3–1.2. */
  enter: number;
  /** Name shown for `/`. */
  homeLabel: string;
  kicker: string;
  /** Name shown on the plate for each destination path. */
  names: Array<{ label: string; path: string }>;
  /**
   * The website's pages. The plate plays only for moves to or from one of them; between the
   * signed-in screens navigation is immediate. Empty or missing: every move is hoisted.
   */
  publicPaths?: string[];
};

export const hoist: HoistCopy = {
  enabled: true,
  duration: 0.55,
  enter: 0.5,
  homeLabel: 'Home',
  kicker: 'Next stage',
  publicPaths: ['/', '/services', '/for-homeowners', '/for-professionals'],
  names: [
    { label: 'Services', path: '/services' },
    { label: 'For homeowners', path: '/for-homeowners' },
    { label: 'For professionals', path: '/for-professionals' },
    { label: 'Plan a project', path: '/start' },
    { label: 'Sign in', path: '/sign-in' },
    { label: 'My projects', path: '/projects' },
    { label: 'Cost estimate', path: '/estimate' },
    { label: 'Find professionals', path: '/professionals' },
    { label: 'About', path: '/about' },
    { label: 'Contact', path: '/contact' },
    { label: 'Privacy', path: '/privacy' },
    { label: 'Terms', path: '/terms' },
  ],
};
