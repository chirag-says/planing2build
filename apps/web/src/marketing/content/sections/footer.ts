/** Copy for the site footer. Phone, email, socials, licence and the wordmark come from `site`. */
import { professionalsSignInUrl } from '@/marketing/lib/hosts';

export type FooterLink = { label: string; href: string };
export type FooterColumn = { title: string; links: FooterLink[] };

export type FooterContent = {
  /** Lift the page off the footer as it scrolls into view (see LiftReveal). */
  reveal: boolean;
  /** Stacking order of the lift wrapper; must stay below the sections above it (10). */
  layer: number;
  officeTitle: string;
  address: string;
  hours: string;
  columns: FooterColumn[];
  newsTitle: string;
  newsLine: string;
  newsLabel: string;
  newsButton: string;
  newsDone: string;
  newsError: string;
  /** `{year}` and `{name}` are filled in. */
  legal: string;
  builtWith: string;
};

export const footer: FooterContent = {
  reveal: true,
  layer: 8,
  officeTitle: 'Office',
  address: 'Raipur, Chhattisgarh',
  hours: 'Mon–Sat 9:00 AM–6:00 PM',
  columns: [
    {
      title: 'Homeowners',
      links: [
        { label: 'Free cost estimate', href: '/services#home-cost-check' },
        { label: 'Compare your quotes', href: '/services#compare-and-decide' },
        { label: 'Build Plan', href: '/services#build-plan' },
        { label: 'How it works', href: '/#how-it-works' },
      ],
    },
    {
      title: 'Professionals',
      links: [
        { label: 'For professionals', href: '/for-professionals' },
        { label: 'Apply to be listed', href: professionalsSignInUrl() },
        { label: 'About', href: '/about' },
        { label: 'Contact', href: '/contact' },
      ],
    },
    {
      title: 'Legal',
      links: [
        { label: 'Privacy', href: '/privacy' },
        { label: 'Terms', href: '/terms' },
      ],
    },
  ],
  newsTitle: 'Build letter',
  newsLine: 'One stage of building a house, explained once a month.',
  newsLabel: 'Your email',
  newsButton: 'Subscribe',
  newsDone: "You're on the list. The next build letter is yours.",
  newsError: 'Please enter a valid email.',
  legal: '© {year} {name}',
  builtWith: 'Estimates are indicative and vary with site conditions, design and specification.',
};
