/**
 * Copy for `/for-professionals`. DRAFT (W-01): written from the client's S14 contractors section
 * and PROFESSIONALS_FLOW (POC scope, PD-18/PD-19 listing rules); the client approves it before
 * release. Rules kept: no fees for invited contractors, no paid placement, no star ratings,
 * leads show the locality only, at most three contractors per request.
 */
import imgProEngage from '@/marketing/assets/professionals/engage.webp';
import imgProEvidence from '@/marketing/assets/professionals/evidence.webp';
import imgProListed from '@/marketing/assets/professionals/listed.webp';
import imgProRecord from '@/marketing/assets/professionals/record.webp';
import imgProQuote from '@/marketing/assets/professionals/quote.webp';
import imgProRegister from '@/marketing/assets/professionals/register.webp';
import type { BoardContent } from '@/marketing/content/sections/board';
import type { BuiltContent } from '@/marketing/content/sections/built';
import type { FaqContent } from '@/marketing/content/sections/faq';
import type { PageHeroContent } from '@/marketing/content/sections/pageHero';
import type { Faq } from '@/marketing/content/types';
import { professionalsSignInUrl } from '@/marketing/lib/hosts';

/** Sign-in on the professionals host: "Sign in or register", where onboarding starts. */
export const PRO_GET_STARTED = professionalsSignInUrl();

export const forProfessionalsMeta = {
  title: 'For professionals',
  description:
    'We never take the contract. Your client signs with you and pays you. Plan2Build makes the scope clear, the quotes comparable and your verified work visible. Listing is free for the contractors we invite.',
};

export const prosHero: PageHeroContent = {
  ground: 'concrete',
  object: 'crane',
  eyebrow: 'For professionals',
  title: 'We are not|*your competitor.*',
  lead: 'We never take the contract. Your client signs with you and pays you. We make the scope clear, the quotes comparable, and your good work visible.',
  mainButton: 'Get started',
  mainLink: PRO_GET_STARTED,
  secondButton: 'How it works',
  secondLink: '#how-it-works',
  words: 'QUOTE;BUILD;VERIFY',
  showProof: false,
};

export const prosPledges: BoardContent = {
  eyebrow: '01 · Our rules',
  heading: 'Position is|*not for sale.*',
  subCopy:
    'Listing is earned with verified evidence, never bought. Requests reach you pre-qualified, and the inspection record of your work stays on your profile.',
  boardTitle: 'Plan2Build · Listing rules',
  boardNote: 'For every professional',
  stats: [
    { value: '₹0', label: 'Listing fee for the contractors we invite' },
    { value: '0', label: 'Paid placements or premium tiers' },
    { value: '3', label: 'Contractors at most per request to quote' },
    { value: '6', label: 'Independent checks that certify your work' },
  ],
  yellowCell: 1,
  showTicker: false,
  daysWord: 'days',
  tickerSpeed: 40,
};

/** The professionals' own screens, one per step. */
const PRO_PHOTO = {
  register: imgProRegister.src,
  evidence: imgProEvidence.src,
  listed: imgProListed.src,
  quote: imgProQuote.src,
  engage: imgProEngage.src,
  record: imgProRecord.src,
};

export const prosHow: BuiltContent = {
  eyebrow: '02 · How it works',
  title: 'How it works for professionals: register, profile and evidence, listed, quote, engage, record',
  levelLetter: 'S',
  stageWord: 'Step',
  nextWord: 'Next',
  lastTag: 'On record',
  stages: [
    {
      slug: 'register',
      name: 'Register',
      meta: 'Two minutes',
      summary: 'Sign in with a code sent to your email. Your first sign-in creates your professional account.',
      specs: [
        { label: 'You need', value: 'An email address' },
        { label: 'Fees', value: 'None to register' },
      ],
      result: { label: 'Then', value: 'Your profile and evidence' },
      photo: PRO_PHOTO.register,
      cta: { label: 'Get started', href: PRO_GET_STARTED },
    },
    {
      slug: 'evidence',
      name: 'Evidence',
      meta: 'Your profile, then proof',
      summary: 'Set up your profile: your name, firm, base location and the radius you cover, and the category you work in. Then add registration documents, references and a portfolio of houses you have built or designed.',
      specs: [
        { label: 'Profile', value: 'Name · firm · service area' },
        { label: 'Categories', value: 'Contractor · Architect · Engineer' },
        { label: 'Documents', value: 'Licence · registration' },
        { label: 'Portfolio', value: 'Your past work' },
      ],
      result: { label: 'Then', value: 'Submit for review' },
      photo: PRO_PHOTO.evidence,
      cta: { label: '', href: '' },
    },
    {
      slug: 'listed',
      name: 'Listed',
      meta: 'Reviewed by Plan2Build',
      summary: 'We check your evidence. Once approved you are listed in the directory families browse.',
      specs: [
        { label: 'States', value: 'In review · Listed' },
        { label: 'Placement', value: 'Never for sale' },
      ],
      result: { label: 'Then', value: 'Requests arrive' },
      photo: PRO_PHOTO.listed,
      cta: { label: '', href: '' },
    },
    {
      slug: 'quote',
      name: 'Quote',
      meta: 'One standard scope',
      summary: 'Requests to quote come with drawings, BOQ and specifications. Clarifications go through us; no competitor sees your price.',
      specs: [
        { label: 'Per request', value: 'At most 3 contractors' },
        { label: 'Lead shows', value: 'Locality only' },
      ],
      result: { label: 'Then', value: 'The family chooses' },
      photo: PRO_PHOTO.quote,
      cta: { label: '', href: '' },
    },
    {
      slug: 'engage',
      name: 'Engage',
      meta: 'Your contract, your client',
      summary: 'The family signs with you and pays you directly. You report each stage in one standard format.',
      specs: [
        { label: 'Contract', value: 'Directly with the family' },
        { label: 'Payments', value: 'Directly to you' },
      ],
      result: { label: 'Then', value: 'Independent checks' },
      photo: PRO_PHOTO.engage,
      cta: { label: '', href: '' },
    },
    {
      slug: 'record',
      name: 'Record',
      meta: 'Work that speaks for itself',
      summary: 'Every passed inspection certifies your work. The record sits on your profile and you can send it to anyone.',
      specs: [
        { label: 'Reputation', value: 'From verified work' },
        { label: 'Star ratings', value: 'None' },
      ],
      result: { label: 'You get', value: 'A verified record' },
      photo: PRO_PHOTO.record,
      cta: { label: 'Get started', href: PRO_GET_STARTED },
    },
  ],
};

export type WhoContent = {
  eyebrow: string;
  heading: string;
  open: Array<{ name: string; text: string }>;
  soonLabel: string;
  soon: string[];
};

export const prosWho: WhoContent = {
  eyebrow: '03 · Who it is for',
  heading: 'Built for the people|*who build.*',
  open: [
    { name: 'Contractors', text: 'Civil contractors quoting and building homes against one standard scope.' },
    { name: 'Architects', text: 'Designers on request, when a family wants its own design pack.' },
    { name: 'Structural engineers', text: 'Qualified engineers who sign off the structural lines of a Build Plan.' },
  ],
  soonLabel: 'Coming soon',
  soon: ['Interior designers', 'Specialist services', 'Material suppliers'],
};

export const prosFaq: FaqContent = {
  eyebrow: '04 · Questions',
  heading: 'Before you|*join.*',
  subCopy: 'Questions about listing? Write to {email}.',
  callLabel: '',
  showTabs: false,
  allLabel: 'All',
  tagLetter: 'Q',
};

export const prosFaqItems: Faq[] = [
  {
    slug: 'competitor',
    question: 'Will Plan2Build compete with me for the contract?',
    answer: 'No. We never take a construction contract. The family signs with you and pays you directly.',
    group: 'Professionals',
  },
  {
    slug: 'fees',
    question: 'What does listing cost?',
    answer: 'Listing is free for the contractors we invite. There is no paid placement and no premium tier: position is not for sale.',
    group: 'Professionals',
  },
  {
    slug: 'leads',
    question: 'How do requests to quote reach me?',
    answer: 'A family with an active Plan2Build package asks for quotes. Each request goes to at most three contractors and shows the locality, not the family, until you agree to quote.',
    group: 'Professionals',
  },
  {
    slug: 'prices',
    question: 'Will other contractors see my price?',
    answer: 'No. Clarifications go through Plan2Build, and quotes are compared on equal scope without showing one contractor’s price to another.',
    group: 'Professionals',
  },
  {
    slug: 'ratings',
    question: 'Are there star ratings?',
    answer: 'No. Your reputation comes from verified work: the inspections your work passes stay on your profile.',
    group: 'Professionals',
  },
];

export type ClosingContent = { eyebrow: string; heading: string; subCopy: string; button: string; buttonLink: string };

export const prosClosing: ClosingContent = {
  eyebrow: '05 · Get started',
  heading: 'Your work,|*on record.*',
  subCopy: 'Register with your email, complete your profile, and submit your category for review.',
  button: 'Get started',
  buttonLink: PRO_GET_STARTED,
};
