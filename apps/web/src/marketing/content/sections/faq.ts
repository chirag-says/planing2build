/** Copy for "09 · Questions", the FAQ on `/` and `/services`. Questions come from `faqs`. */

export type FaqContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  /** `{phone}` and `{email}` become links to the site's phone and email. */
  subCopy: string;
  /** Calls the site's phone. Empty hides the button. */
  callLabel: string;
  /** Filter tabs built from the questions' groups. */
  showTabs: boolean;
  allLabel: string;
  /** The letter before each row number (Q01). */
  tagLetter: string;
};

export const faq: FaqContent = {
  eyebrow: '10 · Questions',
  heading: 'Ask before|*you sign.*',
  subCopy: 'Something else? Call {phone} or email {email}.',
  callLabel: 'Talk to an expert',
  showTabs: true,
  allLabel: 'All',
  tagLetter: 'Q',
};
