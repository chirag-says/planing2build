/** Copy for the home page's "Start your build plan" section. */
export type BidContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  subCopy: string;
  cardLabel: string;
  cardNote: string;
  /** Question 1; its answers are the services. */
  step1: string;
  /** Question 2; its answers are `startOptions`. */
  step2: string;
  /** Answers to question 2, separated by `;`. */
  startOptions: string;
  step3: string;
  dropText: string;
  dropHint: string;
  button: string;
  /** Empty = the site's proof line. */
  proofLine: string;
  callLabel: string;
};

export const bid: BidContent = {
  eyebrow: '09 · Start your build plan',
  heading: 'Tell us about|*your house.*',
  subCopy:
    'Your plot, your area and roughly when you want to start. We come back with an indicative cost broken down by stage, and your first decisions.',
  cardLabel: 'Build plan request',
  cardNote: 'Takes one minute',
  step1: 'What do you need help with?',
  step2: 'When do you want to start?',
  startOptions: 'Within 3 months; In 3–6 months; Later this year; Just exploring',
  step3: 'Drawings or quotes',
  dropText: 'Drop drawings or contractor quotes here',
  dropHint: 'Plot papers, sketches, drawings or quotes',
  button: 'Start your build plan',
  proofLine: '',
  callLabel: 'Or talk to an expert',
};
