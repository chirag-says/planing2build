import imgElectrical from '@/marketing/assets/addons/electrical.webp';
import imgInteriors from '@/marketing/assets/addons/interiors.webp';
import imgMaintenance from '@/marketing/assets/addons/maintenance.webp';
import imgPlumbing from '@/marketing/assets/addons/plumbing.webp';
import type { Review } from './types';

/**
 * The add-on services ("07 · Add-on services"): what a family can call on once the house is
 * built, one slide per service, each done by a verified provider who works from the house's
 * own build record.
 */

const photo = (image: { src: string; width: number; height: number }) => ({ src: image.src, width: image.width, height: image.height });

export const addons: Review[] = [
  {
    slug: 'electrical',
    name: 'Electrical',
    role: 'Add-on 01',
    quote: 'New points, backup power and electrical repairs.',
    project: '',
    result: '',
    rating: 5,
    portrait: null,
    projectPhoto: photo(imgElectrical),
  },
  {
    slug: 'plumbing',
    name: 'Plumbing',
    role: 'Add-on 02',
    quote: 'Leaks, fittings, tanks, pumps and drainage.',
    project: '',
    result: '',
    rating: 5,
    portrait: null,
    projectPhoto: photo(imgPlumbing),
  },
  {
    slug: 'interiors',
    name: 'Interiors & painting',
    role: 'Add-on 03',
    quote: 'Painting, ceilings, wardrobes and kitchens.',
    project: '',
    result: '',
    rating: 5,
    portrait: null,
    projectPhoto: photo(imgInteriors),
  },
  {
    slug: 'maintenance',
    name: 'Annual maintenance',
    role: 'Add-on 04',
    quote: 'A yearly check of the whole house.',
    project: '',
    result: '',
    rating: 5,
    portrait: null,
    projectPhoto: photo(imgMaintenance),
  },
];
