/** Copy for the home page hero: Plan2Build's "Build with clarity" opener. */

/** A labelled pointer on the house drawing; where it sits and its leader lines are set in hero.css. */
export type HeroCallout = { title: string; lines: string[] };
export type HeroStep = { title: string; text: string };

export type HeroContent = {
  eyebrow: string;
  /** `|` breaks a line, `*word*` sits on the yellow plate. */
  heading: string;
  subCopy: string;
  primary: string;
  primaryLink: string;
  secondary: string;
  secondaryLink: string;
  /** Pointers on the drawing, top to bottom (Plan, Compare, Build, Verify). */
  callouts: HeroCallout[];
  /** The rail along the bottom of the hero. */
  steps: HeroStep[];
  imageAlt: string;
};

export const hero: HeroContent = {
  eyebrow: "India's home construction platform",
  heading: 'Build|with *clarity.*|Not guesswork.',
  subCopy:
    'Plan your home, understand the real cost, compare contractors, and keep every construction decision verified — all in one place.',
  primary: 'Create your build plan',
  primaryLink: '/#bid',
  secondary: 'Are you a homeowner?',
  /** Same destination as the header's "For homeowners". */
  secondaryLink: '/for-homeowners',
  callouts: [
    { title: 'Plan', lines: ['Cost • BOQ • Specifications', 'Schedule • Cash Flow'] },
    { title: 'Compare', lines: ['Contractor Quotes', 'Scope Normalisation'] },
    { title: 'Build', lines: ['Track Decisions', 'Manage Variations'] },
    { title: 'Verify', lines: ['Six Assurance Gates', 'Evidence • Build Record'] },
  ],
  steps: [
    { title: 'Plan', text: 'Your requirements, cost, and complete Build Plan' },
    { title: 'Compare', text: 'Standard RFQ and apples-to-apples quotes' },
    { title: 'Select', text: 'Choose the right contractor with full clarity' },
    { title: 'Build', text: 'Track decisions, procurement and variations' },
    { title: 'Verify', text: 'Independent inspections at six key stages' },
    { title: 'Your Build Record', text: 'A permanent record for your home' },
  ],
  imageAlt:
    'A modern two-storey concrete and timber home, half finished and half drawn as a blueprint wireframe, with dimension lines and yellow blocks',
};
