/**
 * Copy for the services page hero (the reference's GdPageHero instance). The reference
 * component also offers `level` / `helmet` objects and `steel` / `night` grounds; this site only
 * uses the crane on concrete, so only those are built.
 */
export type PageHeroContent = {
  ground: 'concrete';
  object: 'crane';
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  title: string;
  lead: string;
  mainButton: string;
  mainLink: string;
  secondButton: string;
  secondLink: string;
  /** The words on the beam the crane lowers, separated by `;` (at most 8 are used). */
  words: string;
  /** Show the site's proof line and licence under the ground line. */
  showProof: boolean;
};

export const pageHero: PageHeroContent = {
  ground: 'concrete',
  object: 'crane',
  eyebrow: 'Services',
  title: 'Pay for advice.|*Never for a contract.*',
  lead: 'Six services, from a free cost check to independent checks at every stage that cannot be undone. Use one, or use them all.',
  mainButton: 'Start your build plan',
  mainLink: '/request-a-bid',
  secondButton: 'How it works',
  secondLink: '/#how-it-works',
  words: 'PLAN;COMPARE;VERIFY',
  showProof: true,
};
