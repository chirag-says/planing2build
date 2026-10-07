/** Copy for the home page's "Live build progress" elevation drawing: where the house is right now, stage by stage. */

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
  eyebrow: '05 · Live build progress',
  heading: 'See what stage your house|*is at right now.*',
  checks: [
    { title: 'Foundation & plinth', text: 'Know the day the footings are poured and the plinth beam is cast.' },
    { title: 'Every slab', text: 'Watch each floor go up, from steel tied to slab poured, level by level.' },
    { title: 'Walls & services', text: 'See the walls rise, and the wiring and plumbing photographed before they close.' },
    { title: 'Roof & waterproofing', text: 'Know when the terrace is sealed and tested, before a single tile goes on.' },
    { title: 'Finishes & handover', text: 'Follow the last snags until the scaffolding comes down and the keys are yours.' },
  ],
  checkWord: 'Stage',
  certLabel: 'At every stage you see',
  certs: ['Where the work is today', 'Dated site photos', 'What comes next'],
};
