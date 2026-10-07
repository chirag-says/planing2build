/** Copy for the home page's "Independent checks" elevation drawing: the six inspection gates. */

export type SafetyCheck = { title: string; text: string };

export type SafetyContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  /**
   * Up to five, in drawing order: foundations, structure, envelope, roof, people. Each one is
   * tied to that part of the drawing, so the order matters.
   */
  checks: SafetyCheck[];
  /** Word before each card's number ("Check 01"). */
  checkWord: string;
  certLabel: string;
  /** Up to six plates. */
  certs: string[];
};

export const safety: SafetyContent = {
  eyebrow: '05 · Independent checks',
  heading: 'Checked before|*it is covered up.*',
  checks: [
    { title: 'Foundation & plinth', text: 'Gates 1 and 2: the footings before the pour, then the plinth beam.' },
    { title: 'Every slab', text: 'Gate 3: steel, cover and shuttering checked before each slab is poured.' },
    { title: 'Before plaster', text: 'Gate 4: concealed wiring and plumbing photographed before the walls close.' },
    { title: 'Waterproofing', text: 'Gate 5: terrace and bathrooms ponding-tested before the tiles go on.' },
    { title: 'Final snag', text: 'Gate 6: every defect closed with proof before the last payment falls due.' },
  ],
  checkWord: 'Check',
  certLabel: 'Our inspection rules',
  certs: ['Blind to the supplier', 'Time-stamped evidence', 'Capped structural remedy'],
};
