import imgServicesAssurance from '@/marketing/assets/services/assurance.webp';
import imgServicesBuildPlanSiteCheck from '@/marketing/assets/services/build-plan-site-check.webp';
import imgServicesCompareAndDecide from '@/marketing/assets/services/compare-and-decide.webp';
import imgServicesHomeCostCheck from '@/marketing/assets/services/home-cost-check.webp';
import imgServicesQuoteReview from '@/marketing/assets/services/quote-review.webp';
import imgServicesStageChecks from '@/marketing/assets/services/stage-checks.webp';
import type { Service } from './types';

/**
 * Plan2Build's services, in the order a family usually meets them. Fees are the working prices
 * from the latest price board; confirm before launch.
 */

export const services: Service[] = [
  {
    "slug": "home-cost-check",
    "name": "Home Cost Check",
    "line": "What a house like yours should cost, before you talk to anyone.",
    "includes": [
      "Cost range for your city",
      "Cost per sq ft",
      "Time to build",
      "Stage-by-stage breakdown"
    ],
    "from": "Free",
    "timeline": "No sign-up",
    "detail": "Enter your city, built-up area, floors and finish level. See a likely range, never a false exact number.",
    "steps": [
      "City",
      "Built-up area",
      "Floors",
      "Finish level",
      "Your range",
      "Next steps"
    ],
    "body": "## What you get\nA likely cost range for your house, the cost per sq ft, about how long it takes from excavation to handover, and what each of the 16 stages costs.\n\n## Who it is for\n- Families with a plot and a rough idea of the house\n- Anyone holding a contractor's number who wants a second opinion\n\n## How we price it\nIt is free. No sign-up and no email. Leave a mobile number only if you want a PDF copy.",
    "stat": {
      "value": "16",
      "label": "stages in the breakdown"
    },
    "photo": {
      "src": imgServicesHomeCostCheck.src,
      "width": 1254,
      "height": 1254
    }
  },
  {
    "slug": "quote-review",
    "name": "Quote Review",
    "line": "Already have a contractor's quote? Know exactly what you are paying for.",
    "includes": [
      "Included, missing, unclear",
      "Risk areas",
      "Questions to ask",
      "60-min expert call"
    ],
    "from": "₹4,999",
    "timeline": "One quote",
    "detail": "We read your contractor's quote line by line against what a house like yours needs.",
    "steps": [
      "Send the quote",
      "Line-by-line read",
      "Gaps flagged",
      "Risks listed",
      "Expert call",
      "Your questions"
    ],
    "body": "## What you get\nA detailed review of one quotation: what is included, what is missing and what is unclear, the risk areas, and the questions to ask your contractor before you sign. Then a 60-minute discussion with our expert.\n\n## Who it is for\nFamilies who already have a contractor and a quote. We never replace the contractor you have chosen.\n\n## How we price it\nA fixed fee for one quote.",
    "stat": {
      "value": "60 min",
      "label": "with an expert"
    },
    "photo": {
      "src": imgServicesQuoteReview.src,
      "width": 1254,
      "height": 1254
    }
  },
  {
    "slug": "compare-and-decide",
    "name": "Compare & Decide",
    "line": "Up to three quotes, made comparable on equal scope.",
    "includes": [
      "Up to 3 quotes",
      "Scope-normalised report",
      "Specification check",
      "90-min expert call"
    ],
    "from": "₹9,999",
    "timeline": "Up to 3 quotes",
    "detail": "The cheapest quote is almost never the cheapest house. We show you what each number leaves out.",
    "steps": [
      "Send the quotes",
      "Common basis",
      "Every gap priced",
      "Comparable totals",
      "Expert call",
      "You choose"
    ],
    "body": "## What you get\nUp to three quotations compared on a common basis. Every difference from the specification, such as missing waterproofing or a lower steel grade, is shown with its rupee impact, then the totals are made comparable. A 90-minute expert discussion follows.\n\n## What we never do\nRank contractors by price or choose for you. You choose.\n\n## How we price it\nA fixed fee for up to three quotes.",
    "stat": {
      "value": "3",
      "label": "quotes on equal scope"
    },
    "photo": {
      "src": imgServicesCompareAndDecide.src,
      "width": 1254,
      "height": 1254
    }
  },
  {
    "slug": "build-plan",
    "name": "Complete Build Plan",
    "line": "Your house written down before anyone quotes on it.",
    "includes": [
      "Drawings & 3D views",
      "Specifications & BOQ",
      "Schedule & cash flow",
      "Decisions calendar"
    ],
    "from": "₹24,999",
    "timeline": "Before you dig",
    "detail": "Cost, specifications, BOQ, payment schedule and a calendar for all 67 decisions, with structural items signed off by a registered engineer.",
    "steps": [
      "Your requirement",
      "Drawings",
      "Specifications",
      "BOQ & cost",
      "Engineer sign-off",
      "Plan issued"
    ],
    "body": "## What you get\nArchitectural drawings and 3D views, a cost estimate, specifications and bill of quantities, inclusions and exclusions, a payment schedule, a monthly cash-flow plan and a decisions calendar. A registered structural engineer signs off every structural item.\n\n## Why it matters\nEvery contractor quotes against the same plan, so their numbers finally mean the same thing.\n\n## How we price it\n₹24,999 to ₹29,999, depending on the size and complexity of the house.",
    "stat": {
      "value": "67",
      "label": "decisions with a decide-by date"
    },
    "photo": {
      "src": imgServicesBuildPlanSiteCheck.src,
      "width": 1240,
      "height": 1268
    }
  },
  {
    "slug": "stage-checks",
    "name": "Stage Checks",
    "line": "An independent engineer on your site at the stage you choose.",
    "includes": [
      "On-site inspection",
      "Specification check",
      "Photo report",
      "Corrective actions"
    ],
    "from": "₹5,000",
    "timeline": "Per check",
    "detail": "Book a check before the work that cannot be undone, such as a slab pour or plastering over pipes.",
    "steps": [
      "Book the stage",
      "Site visit",
      "Checkpoints",
      "Photo evidence",
      "Report",
      "Fix verified"
    ],
    "body": "## What you get\nAn on-site inspection by an engineer we retain, checked against your specification. A report with time-stamped photos, findings and the corrective actions needed.\n\n## Who is checking\nThe inspector is never told who supplied the material, and never works for your contractor.\n\n## How we price it\n₹5,000 to ₹7,500 per stage check.",
    "stat": {
      "value": "0",
      "label": "ties to your contractor"
    },
    "photo": {
      "src": imgServicesStageChecks.src,
      "width": 1254,
      "height": 1254
    }
  },
  {
    "slug": "assurance",
    "name": "Assurance Package",
    "line": "All six inspection gates, from the foundation to the final snag.",
    "includes": [
      "6 independent inspections",
      "Report at every gate",
      "Defects closed with proof",
      "Capped structural remedy"
    ],
    "from": "₹30,000",
    "timeline": "Foundation to handover",
    "detail": "Every stage that cannot be undone is checked before it is covered up.",
    "steps": [
      "Foundation",
      "Plinth beam",
      "Every slab",
      "Before plaster",
      "Waterproofing",
      "Final snag"
    ],
    "body": "## What you get\nIndependent inspections at all six gates: the foundation before pouring, the plinth beam, every slab before pouring, before plastering, waterproofing, and the final snag check. A plain-language report at each one, and defects stay open until the fix is checked.\n\n## Our promise\nIf a structural defect appears later in work we inspected, Plan2Build pays to fix it, up to a cap.\n\n## How we price it\nFrom ₹30,000, depending on the size of the house and the number of slabs.",
    "stat": {
      "value": "6",
      "label": "gates checked before they are covered"
    },
    "photo": {
      "src": imgServicesAssurance.src,
      "width": 1254,
      "height": 1254
    }
  }
];
