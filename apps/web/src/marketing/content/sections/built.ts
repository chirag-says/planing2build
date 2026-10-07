/** Copy for the home page's "Seven stages" showcase: Plan → Find → Compare → Select → Build → Verify → Record. */

import imgStagesBuild from '@/marketing/assets/stages/build.webp';
import imgStagesCompare from '@/marketing/assets/stages/compare.webp';
import imgStagesFind from '@/marketing/assets/stages/find.webp';
import imgStagesPlan from '@/marketing/assets/stages/plan.webp';
import imgStagesRecord from '@/marketing/assets/stages/record.webp';
import imgStagesSelect from '@/marketing/assets/stages/select.webp';
import imgStagesVerify from '@/marketing/assets/stages/verify.webp';

export type BuiltStageContent = {
  /** Anchor id and React key. */
  slug: string;
  /** "Plan" */
  name: string;
  /** Mono line under the name. */
  meta: string;
  summary: string;
  /** Up to four short figures as a ruled table. Values that hold a number count up. */
  specs: Array<{ label: string; value: string }>;
  /** The yellow plate under the table. Empty label hides it. */
  result: { label: string; value: string };
  /** Photo URL, one image per stage in /public/images/stages. */
  photo: string;
  /** The stage's call to action. Backend wiring comes later; empty label = no button. */
  cta: { label: string; href: string };
};

export type BuiltContent = {
  eyebrow: string;
  /** Hidden section heading for screen readers and search. Empty = "Built by <site name>". */
  title: string;
  /** Stands before the stage number on the level rail ("S" -> "S01"). */
  levelLetter: string;
  /** Before the stage number on the dimension line above the photo ("Stage" -> "Stage 01 · Plan"). */
  stageWord: string;
  /** Tag on the photo pointing at the next stage ("Next" -> "Next · Find"). */
  nextWord: string;
  /** Tag on the last stage's photo. */
  lastTag: string;
  /** One scroll per stage, in order. */
  stages: BuiltStageContent[];
};

const PHOTO = {
  plan: imgStagesPlan.src,
  find: imgStagesFind.src,
  compare: imgStagesCompare.src,
  select: imgStagesSelect.src,
  build: imgStagesBuild.src,
  verify: imgStagesVerify.src,
  record: imgStagesRecord.src,
};

export const built: BuiltContent = {
  eyebrow: '03 · Seven stages',
  title: 'Plan, find, compare, select, build, verify, record',
  levelLetter: 'S',
  stageWord: 'Stage',
  nextWord: 'Next',
  lastTag: 'Handover',
  stages: [
    {
      slug: 'plan',
      name: 'Plan',
      meta: 'Before the first quote',
      summary: 'Set your plot, floors and finish, and see what your home should really cost in your city.',
      specs: [
        { label: 'You decide', value: 'Area · floors · finish' },
        { label: 'Includes', value: 'Cost · BOQ · specs' },
        { label: 'Use it to', value: 'Check any quote' },
        { label: 'Decide-by dates', value: '67 decisions' },
      ],
      result: { label: 'You get', value: 'Your build plan' },
      photo: PHOTO.plan,
      cta: { label: 'Start planning', href: '/request-a-bid' },
    },
    {
      slug: 'find',
      name: 'Find',
      meta: 'Verified contractors near your plot',
      summary: 'Meet contractors who have been checked for licences, past sites and references, not just ads.',
      specs: [
        { label: 'Who', value: 'Verified contractors' },
        { label: 'Includes', value: 'Licence · sites · references' },
        { label: 'Use it to', value: 'Invite quotes on your plan' },
        { label: 'Your own builder', value: 'Welcome too' },
      ],
      result: { label: 'You get', value: 'A shortlist of 3–5' },
      photo: PHOTO.find,
      cta: { label: 'Find contractors', href: '/request-a-bid' },
    },
    {
      slug: 'compare',
      name: 'Compare',
      meta: 'Same scope, side by side',
      summary: 'Every contractor quotes against the same drawings and BOQ, so prices line up item by item.',
      specs: [
        { label: 'Quotes on', value: 'One shared BOQ' },
        { label: 'Includes', value: 'Gaps · ₹ impact · risks' },
        { label: 'Use it to', value: 'Spot missing work' },
        { label: 'Expert call', value: '90 min' },
      ],
      result: { label: 'You get', value: 'Like-for-like quotes' },
      photo: PHOTO.compare,
      cta: { label: 'Compare quotes', href: '/request-a-bid' },
    },
    {
      slug: 'select',
      name: 'Select',
      meta: 'Pick with the facts in front of you',
      summary: 'Choose your contractor and sign a clear contract with a stage-wise payment schedule.',
      specs: [
        { label: 'You sign', value: 'Direct with contractor' },
        { label: 'Includes', value: 'Scope · specs · schedule' },
        { label: 'Use it to', value: 'Pay stage by stage' },
        { label: 'Changes', value: 'OTP-confirmed' },
      ],
      result: { label: 'You get', value: 'A signed agreement' },
      photo: PHOTO.select,
      cta: { label: 'Select a contractor', href: '/request-a-bid' },
    },
    {
      slug: 'build',
      name: 'Build',
      meta: 'Work starts on schedule',
      summary: 'Follow progress stage by stage, with decide-by dates for tiles, doors and fittings.',
      specs: [
        { label: 'Updates', value: 'Every stage' },
        { label: 'Includes', value: 'Cash flow · calendar' },
        { label: 'Use it to', value: 'Order on time' },
        { label: 'Changes', value: 'Priced before work' },
      ],
      result: { label: 'You get', value: 'Progress you can see' },
      photo: PHOTO.build,
      cta: { label: 'Track your build', href: '/request-a-bid' },
    },
    {
      slug: 'verify',
      name: 'Verify',
      meta: 'Checked before you pay',
      summary: 'An independent engineer checks the work at each stage before the next payment is released.',
      specs: [
        { label: 'Checked by', value: 'Independent engineer' },
        { label: 'Includes', value: 'Photos · findings · fixes' },
        { label: 'Use it to', value: 'Fix it before it’s buried' },
        { label: 'Site checks', value: '6 gates' },
      ],
      result: { label: 'You get', value: 'Payment on proof' },
      photo: PHOTO.verify,
      cta: { label: 'Book a site check', href: '/request-a-bid' },
    },
    {
      slug: 'record',
      name: 'Record',
      meta: 'Every decision in one place',
      summary: 'Drawings, bills, photos, test reports and warranties, kept together for the life of your home.',
      specs: [
        { label: 'Includes', value: 'Bills · photos · warranties' },
        { label: 'Use it to', value: 'Sell with proof' },
        { label: 'Pipe map', value: 'Inside every wall' },
        { label: 'Access', value: 'No login needed' },
      ],
      result: { label: 'You get', value: 'Your home’s record' },
      photo: PHOTO.record,
      cta: { label: 'See your records', href: '/request-a-bid' },
    },
  ],
};
