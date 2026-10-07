import imgHouseBlueprint from '@/marketing/assets/house-blueprint.webp';
import type { SiteInfo } from './types';

/** Plan2Build's contact details and the lines repeated across the site. */

export const site: SiteInfo = {
  "name": "Plan2Build",
  "descriptor": "Home construction platform",
  "tagline": "Independent advice for the family building one house: a written Build Plan, quotes compared on equal scope, and independent checks at the six stages that cannot be undone. We never take your contract.",
  "email": "hello@plan2build.in",
  "phone": "+91 98765 43210",
  "bidHref": "/request-a-bid",
  "projectsHref": "/projects",
  "area": "Raipur",
  "proof": "67 decisions · 16 stages · 6 independent inspections · 1 permanent build record",
  "socials": [
    {
      "label": "LinkedIn",
      "href": "https://linkedin.com"
    },
    {
      "label": "Instagram",
      "href": "https://instagram.com"
    },
    {
      "label": "YouTube",
      "href": "https://youtube.com"
    }
  ],
  "projectsBuilt": 0,
  "licence": "ConjunIQ Technologies Private Limited",
  "office": "Raipur, Chhattisgarh",
  "hours": "Mon–Sat 9:00 AM–6:00 PM",
  "photo": {
    "src": imgHouseBlueprint.src,
    "width": 1536,
    "height": 1024
  }
};
