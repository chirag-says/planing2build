import imgHouseBlueprint from '@/marketing/assets/house-blueprint.webp';
import type { Review } from './types';

/**
 * The quote comparison demo: three contractors quoting the same 2,650 sq ft, G+1 house in
 * Raipur. The structure is real; the figures are illustrative. Each `result` is the quote's
 * total once every gap against the specification is priced in.
 */

const HOUSE_PHOTO = { "src": imgHouseBlueprint.src, "width": 1536, "height": 1024 };

export const reviews: Review[] = [
  {
    "slug": "contractor-a",
    "name": "Contractor A",
    "role": "Quoted ₹48.20 L",
    "quote": "Every line priced against the specification. Scope complete as issued, nothing to add.",
    "project": "2,650 sq ft · G+1 · Raipur",
    "result": "₹48.20 L",
    "rating": 5,
    "portrait": null,
    "projectPhoto": HOUSE_PHOTO
  },
  {
    "slug": "contractor-b",
    "name": "Contractor B",
    "role": "Quoted ₹44.60 L · looked cheapest by ₹3.6 L",
    "quote": "No waterproofing to the terrace or bathrooms (+₹1.85 L). Fe500 steel where the drawings call for Fe500D (+₹0.62 L). No compound wall or gate (+₹1.40 L). 12 mm plaster against 15 mm (+₹0.48 L).",
    "project": "2,650 sq ft · G+1 · Raipur",
    "result": "₹48.95 L",
    "rating": 5,
    "portrait": null,
    "projectPhoto": HOUSE_PHOTO
  },
  {
    "slug": "contractor-c",
    "name": "Contractor C",
    "role": "Quoted ₹49.80 L",
    "quote": "Includes a false ceiling in two rooms you did not ask for (−₹1.20 L).",
    "project": "2,650 sq ft · G+1 · Raipur",
    "result": "₹48.60 L",
    "rating": 5,
    "portrait": null,
    "projectPhoto": HOUSE_PHOTO
  }
];
