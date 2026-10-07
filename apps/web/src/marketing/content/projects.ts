import imgHouseBlueprint from '@/marketing/assets/house-blueprint.webp';
import imgHouseVilla from '@/marketing/assets/house-villa.webp';
import type { Project } from './types';

/**
 * Sample houses shown in the "Sample build plans" showcase. These are illustrations, not
 * client projects: each cost range and duration is the Home Cost Check's result for Raipur at
 * the stated area, floors and finish level (excluding land and approvals).
 */

export const projects: Project[] = [
  {
    "slug": "compact-2bhk",
    "name": "Compact 2 BHK",
    "place": "Raipur",
    "type": "Ground only · Standard finish",
    "floors": 1,
    "bays": 3,
    "value": "₹18.2–21.6 L",
    "daysOnSite": 14,
    "status": "Sample plan",
    "glass": "var(--gd-glass-sand)",
    "summary": "A single-storey family home on a compact plot, planned before the first quote.",
    "service": "Complete Build Plan",
    "size": "1,200 sq ft",
    "year": "",
    "result": "₹1,520–1,800 / sq ft",
    "body": "## The house\nA single-storey 2 BHK with a standard finish.\n\n## What the plan fixes\n- Concrete and steel grades for the foundation and slab\n- Waterproofing for the roof and both bathrooms\n- A stage-wise payment schedule\n\n> Indicative range for Raipur, excluding land and approvals.",
    "scope": [
      "Drawings",
      "Specifications",
      "BOQ",
      "Cash-flow plan"
    ],
    "lead": "",
    "client": "Sample plan",
    "photo": {
      "src": "https://framerusercontent.com/images/Pnp9zdIU4FbEn5up8ncfnuJLFQ.webp",
      "width": 2000,
      "height": 1342
    },
    "gallery": []
  },
  {
    "slug": "family-3bhk",
    "name": "3 BHK Family Home",
    "place": "Raipur",
    "type": "Ground + 1 · Standard finish",
    "floors": 2,
    "bays": 4,
    "value": "₹25.4–30.1 L",
    "daysOnSite": 16,
    "status": "Sample plan",
    "glass": "var(--gd-glass-bronze)",
    "summary": "Two floors for a growing family, with the upper slab and staircase planned from day one.",
    "service": "Complete Build Plan",
    "size": "1,650 sq ft",
    "year": "",
    "result": "₹1,538–1,822 / sq ft",
    "body": "## The house\nA ground-plus-one 3 BHK with a standard finish.\n\n## What the plan fixes\n- One specification every contractor quotes against\n- Electrical and plumbing points before the walls go up\n- Decide-by dates for tiles, doors and fittings\n\n> Indicative range for Raipur, excluding land and approvals.",
    "scope": [
      "Drawings",
      "Specifications",
      "BOQ",
      "Decisions calendar"
    ],
    "lead": "",
    "client": "Sample plan",
    "photo": {
      "src": "https://framerusercontent.com/images/8VKJkKF0epxdL7UUJUrCaRfgfJs.webp",
      "width": 2000,
      "height": 1123
    },
    "gallery": []
  },
  {
    "slug": "duplex-2650",
    "name": "The 2,650 sq ft Duplex",
    "place": "Raipur",
    "type": "Ground + 1 · Premium finish",
    "floors": 2,
    "bays": 5,
    "value": "₹52.3–64.4 L",
    "daysOnSite": 17,
    "status": "Sample plan",
    "glass": "var(--gd-glass-sky)",
    "summary": "The house in our quote comparison: three contractors, three numbers, one plan to make them comparable.",
    "service": "Compare & Decide",
    "size": "2,650 sq ft",
    "year": "",
    "result": "₹1,973–2,429 / sq ft",
    "body": "## The house\nA ground-plus-one home with a premium finish.\n\n## What the plan fixes\n- Fe500D steel and the concrete grade for every slab\n- 15 mm internal plaster, not 12 mm\n- Compound wall and gate inside the scope\n\n> Indicative range for Raipur, excluding land and approvals.",
    "scope": [
      "Drawings & 3D",
      "Specifications",
      "BOQ",
      "Quote comparison"
    ],
    "lead": "",
    "client": "Sample plan",
    "photo": {
      "src": imgHouseBlueprint.src,
      "width": 1536,
      "height": 1024
    },
    "gallery": []
  },
  {
    "slug": "villa-3500",
    "name": "Rooftop Garden Villa",
    "place": "Raipur",
    "type": "Ground + 2 · Luxury finish",
    "floors": 3,
    "bays": 6,
    "value": "₹95 L–1.29 Cr",
    "daysOnSite": 20,
    "status": "Sample plan",
    "glass": "var(--gd-glass-sage)",
    "summary": "Cantilevers, a rooftop garden and three slabs, each one checked before it is poured.",
    "service": "Assurance Package",
    "size": "3,500 sq ft",
    "year": "",
    "result": "₹2,714–3,686 / sq ft",
    "body": "## The house\nA ground-plus-two villa with a luxury finish and a rooftop garden.\n\n## What the plan fixes\n- Structural items signed off by a registered engineer\n- Terrace waterproofing with a ponding test\n- An inspection before every slab pour\n\n> Indicative range for Raipur, excluding land and approvals.",
    "scope": [
      "Drawings & 3D",
      "Specifications",
      "BOQ",
      "Six inspections"
    ],
    "lead": "",
    "client": "Sample plan",
    "photo": {
      "src": imgHouseVilla.src,
      "width": 1536,
      "height": 1024
    },
    "gallery": []
  }
];
