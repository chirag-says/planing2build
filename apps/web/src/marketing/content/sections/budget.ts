/**
 * Copy for "08 · Home Cost Check", the estimate sheet on `/` and `/services`. Rates are the
 * Raipur rate card: Standard ₹1,520–1,800, Premium ₹1,950–2,400, Luxury ₹2,650–3,600 per sq ft,
 * 1.2% more per extra floor; time to build ≈ 12 + area / 700 + 1.6 per extra floor, in months.
 */

export type BudgetContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  subCopy: string;
  /** The big number on the beam. Empty hides the fact. */
  factNumber: string;
  factLabel: string;
  cardTitle: string;
  typeLabel: string;
  sizeLabel: string;
  unitLabel: string;
  finishLabel: string;
  /** `Name:price factor; …` */
  finishes: string;
  /** The choices for the first question, separated by `;`. Each one's rate line is keyed by its slug. */
  types: string;
  /**
   * One per type: `slug:price per unit:smallest size:largest size:base:pace; …`.
   * Duration (in the unit `weeksText` names) = base + pace × √size.
   */
  rates: string;
  /** Plus and minus around the estimate, in percent (0–45). */
  spread: number;
  resultLabel: string;
  scheduleLabel: string;
  /** `{n}` = the number of weeks. */
  weeksText: string;
  lowLabel: string;
  highLabel: string;
  note: string;
  /** Links to the site's bid page with the answers added. Empty hides the button. */
  cta: string;
};

export const budget: BudgetContent = {
  eyebrow: '08 · Home Cost Check',
  heading: 'Know the cost|*before the quotes.*',
  subCopy: 'Three answers give you a likely range and the time to build. Free, with no sign-up.',
  factNumber: '₹0',
  factLabel: 'to find out what your house should cost',
  cardTitle: 'Home Cost Check',
  typeLabel: 'Floors',
  types: 'Ground only; Ground + 1; Ground + 2; Ground + 3',
  sizeLabel: 'Built-up area',
  unitLabel: 'sq ft',
  finishLabel: 'Finish level',
  finishes: 'Standard:1; Premium:1.31; Luxury:1.88',
  rates:
    'ground-only:1660:500:8000:8.85:0.135; ground-1:1680:500:8000:10.45:0.135; ground-2:1700:500:8000:12.05:0.135; ground-3:1720:500:8000:13.65:0.135',
  spread: 10,
  resultLabel: 'Likely cost',
  scheduleLabel: 'Time to build',
  weeksText: 'about {n} months',
  lowLabel: 'Low',
  highLabel: 'High',
  note: 'Indicative for Raipur, excluding land and approvals',
  cta: 'Start your build plan',
};
