/**
 * Copy for `/for-homeowners`. DRAFT (W-01): written from the client's own S14 lines and the facts
 * in IHB_FLOW (67 decisions, 16 stages, six checks, one package); the client approves it before
 * release. No figure here is a marketing statistic.
 */
import type { BoardContent } from '@/marketing/content/sections/board';
import type { FaqContent } from '@/marketing/content/sections/faq';
import { hero, type HeroContent } from '@/marketing/content/sections/hero';
import { bid, type BidContent } from '@/marketing/content/sections/bid';

export type PlanTier = { title: string; note: string; items: string[] };

export type TiersContent = {
  eyebrow: string;
  heading: string;
  subCopy: string;
  free: PlanTier;
  paid: PlanTier;
  /** Between the two: how a project moves from free to paid. */
  steps: string[];
  button: string;
  buttonLink: string;
};

export const forHomeownersMeta = {
  title: 'For homeowners',
  description:
    'A family builds once. Plan2Build writes your 67 decisions down, compares quotes on equal scope and checks the six things that cannot be undone. We never take your contract.',
};

export const homeownersHero: HeroContent = {
  ...hero,
  eyebrow: 'For homeowners',
  heading: 'A family|builds *once.*|Build it right.',
  subCopy:
    'You will make sixty-seven material decisions building your home. We make you a competent buyer, not a construction expert: the cost in writing, quotes on equal scope, and independent checks before anything is covered up.',
  primary: 'Plan a project',
  primaryLink: '/start',
  secondary: 'See what your house should cost',
  secondaryLink: '/estimate',
};

export const homeownersProblem: BoardContent = {
  eyebrow: '01 · The problem',
  heading: 'Sixty-seven decisions.|*No one on your side.*',
  subCopy:
    'Quotes that never price the same scope. Decisions made in a hurry on site. Money that runs out mid-build. And at the end, land with papers and a house with none.',
  boardTitle: 'Plan2Build · Why houses overrun',
  boardNote: 'Every family, every build',
  stats: [
    { value: '67', label: 'Material decisions, most made under pressure' },
    { value: '16', label: 'Construction stages to coordinate' },
    { value: '6', label: 'Stages that cannot be undone once covered' },
    { value: '1', label: 'Chance to get it right: a family builds once' },
  ],
  yellowCell: 1,
  showTicker: false,
  daysWord: 'days',
  tickerSpeed: 40,
};

export const homeownersTiers: TiersContent = {
  eyebrow: '02 · Free, then one package',
  heading: 'Start free.|*Pay only for the plan.*',
  subCopy:
    'Your dashboard opens the moment you submit your requirements. When Plan2Build accepts your project, one package unlocks the rest of the journey. You never pay us for a contract.',
  free: {
    title: 'Free dashboard',
    note: 'From the day you submit',
    items: [
      'Your project and requirements',
      'An indicative cost estimate',
      'Three AI concept designs (illustrative)',
      'Approved professionals near you',
    ],
  },
  paid: {
    title: 'Plan2Build package',
    note: 'After we accept your project',
    items: [
      'Your Build Plan: drawings, BOQ, specifications',
      'Requests to quote on one standard scope',
      'Quotes compared on equal scope',
      'Independent checks at six stages',
      'Your permanent build record',
    ],
  },
  steps: ['Submit', 'We review', 'Accepted', 'Package'],
  button: 'Plan a project',
  buttonLink: '/start',
};

export const homeownersFaq: FaqContent = {
  eyebrow: '03 · Questions',
  heading: 'Before you|*start.*',
  subCopy: 'Still unsure? Call {phone} or write to {email}.',
  callLabel: 'Talk to an expert',
  showTabs: true,
  allLabel: 'All',
  tagLetter: 'Q',
};

export const homeownersStart: BidContent = {
  ...bid,
  eyebrow: '04 · Plan a project',
  heading: 'Tell us about|*your house.*',
  button: 'Plan a project',
};
