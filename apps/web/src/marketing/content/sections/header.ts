/** Copy for the site header, from the layout template's GdHeader instance. */

export type NavLink = { label: string; href: string };

export type HeaderContent = {
  /** Main navigation, in order. Hrefs are the reference's paths; the header resolves them. */
  links: NavLink[];
  /** Small caps line under the wordmark. */
  logoTag: string;
  /** The nav link whose button opens the projects drawer instead of navigating. Empty = no drawer. */
  drawerFor: string;
  ctaLabel: string;
  /** Where the "Get your build plan" button goes (bar and phone sheet). Empty = the site's bid link. */
  ctaHref: string;
  showCta: boolean;
  showPhone: boolean;
  drawerTitle: string;
  allLabel: string;
  servicesTitle: string;
  servicesLabel: string;
  servicesLink: string;
  cardKicker: string;
  cardTitle: string;
  cardLine: string;
  cardButton: string;
  homeLabel: string;
  newestLabel: string;
  callLabel: string;
  /** Names the phone menu (the sheet dialog). */
  menuLabel: string;
  /** Names the burger while the menu is closed and open. */
  openMenuLabel: string;
  closeLabel: string;
};

export const header: HeaderContent = {
  links: [
    { label: 'Home', href: '/' },
    { label: 'How it works', href: '/#how-it-works' },
    { label: 'For homeowners', href: '/for-homeowners' },
    { label: 'For professionals', href: '/for-professionals' },
    { label: 'About', href: '/about' },
    // Returning homeowners: the account lives behind sign-in (the e2e suite looks for it in "Main").
    { label: 'Sign in', href: '/sign-in' },
  ],
  logoTag: 'Plan Compare Build Verify',
  drawerFor: '',
  ctaLabel: 'Get your build plan',
  /** Starts the homeowner journey: entry questions, then sign-in by code, then requirements. */
  ctaHref: '/start',
  showCta: true,
  showPhone: true,
  drawerTitle: 'Sample build plans',
  allLabel: 'All sample plans',
  servicesTitle: 'What we do',
  servicesLabel: 'All services',
  servicesLink: '/services',
  cardKicker: 'Holding a quote?',
  cardTitle: 'Quote Review from ₹4,999',
  cardLine: 'Know what is included, missing and unclear before you sign.',
  cardButton: 'Start your build plan',
  homeLabel: 'Home',
  newestLabel: 'Sample plans',
  callLabel: 'Talk to an expert',
  menuLabel: 'Menu',
  openMenuLabel: 'Open menu',
  closeLabel: 'Close menu',
};
