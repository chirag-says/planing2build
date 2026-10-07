/** Copy for the home page's quote comparison ("07 · Three quotes, one house"). The quotes come from `reviews`. */
export type OwnersContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  /** Handover-sheet checklist, separated by `;` (first six are used). */
  checks: string;
  /** Sheet title, followed by the review's project ("Handover · Depot 9"). */
  cardLabel: string;
  /** Sheet number label ("Sheet 01 / 04"). */
  sheetLabel: string;
  resultLabel: string;
  /** Pressed onto the sheet on hover; empty = no stamp. */
  stampText: string;
  /** The five-square rating above each quote. */
  showRating: boolean;
  prevLabel: string;
  nextLabel: string;
};

export const owners: OwnersContent = {
  eyebrow: '07 · Three quotes, one house',
  heading: 'The cheapest quote|*is rarely the cheapest house.*',
  checks: 'Every line priced or excluded; Gaps against the specification; Rupee impact of each gap; Totals on equal scope',
  cardLabel: 'Quote audit',
  sheetLabel: 'Quote',
  resultLabel: 'On equal scope',
  stampText: 'Audited',
  prevLabel: 'Previous quote',
  nextLabel: 'Next quote',
  showRating: false,
};
