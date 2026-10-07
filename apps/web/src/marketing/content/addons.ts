import imgAssurance from '@/marketing/assets/services/assurance.webp';
import imgStageChecks from '@/marketing/assets/services/stage-checks.webp';
import imgStagesBuild from '@/marketing/assets/stages/build.webp';
import imgStagesRecord from '@/marketing/assets/stages/record.webp';
import type { Review } from './types';

/**
 * The add-on services ("07 · After handover"): what a family can call on once the house is
 * built, one slide per service, each done by a verified provider who works from the house's
 * own build record. The house is illustrative.
 */

const PROJECT = '2,650 sq ft · G+1 · Raipur';
const photo = (image: { src: string; width: number; height: number }) => ({ src: image.src, width: image.width, height: image.height });

export const addons: Review[] = [
  {
    slug: 'electrical',
    name: 'Electrical',
    role: 'Add-on 01 · power and wiring after you move in',
    quote: 'New points, inverter and backup wiring, earthing checks and repairs, by an electrician who works from your house’s own wiring map.',
    project: PROJECT,
    result: 'Verified electrician',
    rating: 5,
    portrait: null,
    projectPhoto: photo(imgAssurance),
  },
  {
    slug: 'plumbing',
    name: 'Plumbing',
    role: 'Add-on 02 · water, drainage and fittings',
    quote: 'Leak repairs, fitting changes, tank and pump work and drainage fixes, by a plumber working to the as-built plumbing lines.',
    project: PROJECT,
    result: 'Verified plumber',
    rating: 5,
    portrait: null,
    projectPhoto: photo(imgStageChecks),
  },
  {
    slug: 'interiors',
    name: 'Interiors & painting',
    role: 'Add-on 03 · finishes after you move in',
    quote: 'Repainting, false ceilings, wardrobes and modular kitchens, quoted on a fixed scope before any work starts.',
    project: PROJECT,
    result: 'Verified interior team',
    rating: 5,
    portrait: null,
    projectPhoto: photo(imgStagesBuild),
  },
  {
    slug: 'maintenance',
    name: 'Annual maintenance',
    role: 'Add-on 04 · a yearly check of the whole house',
    quote: 'Terrace waterproofing, seepage, cracks, electrical safety and plumbing checked once a year and added to your build record.',
    project: PROJECT,
    result: 'Verified maintenance team',
    rating: 5,
    portrait: null,
    projectPhoto: photo(imgStagesRecord),
  },
];
