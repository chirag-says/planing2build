import imgRolesAdvisor from '@/marketing/assets/roles/advisor.svg';
import imgRolesAuditor from '@/marketing/assets/roles/auditor.svg';
import imgRolesEngineer from '@/marketing/assets/roles/engineer.svg';
import imgRolesOperations from '@/marketing/assets/roles/operations.svg';
import type { TeamMember } from './types';

/**
 * The roles on the family's side of a Plan2Build project. Each badge is a role, not a named
 * person, drawn as an icon; swap in names, photos and contact details once the team is public.
 */

export const team: TeamMember[] = [
  {
    "slug": "advisor",
    "name": "Advisor",
    "role": "Your Plan2Build build advisor",
    "years": 0,
    "certs": [
      "Plan2Build staff",
      "Writes your Build Plan"
    ],
    "quote": "Writes your house down before anyone quotes on it, so every number means the same thing.",
    "phone": "",
    "email": "",
    "badge": "01",
    "bio": "## The role\nWrites the Build Plan: cost estimate, specifications, BOQ, payment schedule, cash-flow plan and decisions calendar.\n\n## During the build\nRecords every change and decision, and is the person you call.",
    "projects": [],
    "languages": [
      "English",
      "Hindi"
    ],
    "photo": {
      "src": imgRolesAdvisor.src,
      "width": 400,
      "height": 500
    }
  },
  {
    "slug": "engineer",
    "name": "Engineer",
    "role": "Registered structural engineer",
    "years": 0,
    "certs": [
      "Retained by Plan2Build",
      "Signs off structure"
    ],
    "quote": "Specifies your foundation, columns, beams and slabs. No brand can ever be attached to a structural item.",
    "phone": "",
    "email": "",
    "badge": "02",
    "bio": "## The role\nReviews and signs off every structural item in your Build Plan.\n\n## Independence\nRetained by Plan2Build. Never quotes to you, and is never paid by a contractor or a brand.",
    "projects": [],
    "languages": [
      "English",
      "Hindi"
    ],
    "photo": {
      "src": imgRolesEngineer.src,
      "width": 400,
      "height": 500
    }
  },
  {
    "slug": "auditor",
    "name": "Auditor",
    "role": "Independent site inspector",
    "years": 0,
    "certs": [
      "Paid per inspection",
      "Blind to the supplier"
    ],
    "quote": "Checks each stage before it is covered up, without being told who supplied the material.",
    "phone": "",
    "email": "",
    "badge": "03",
    "bio": "## The role\nInspects your house at the six gates, with time- and location-stamped photos that cannot be backdated.\n\n## Independence\nKept separate from contractors and local business partners.",
    "projects": [],
    "languages": [
      "English",
      "Hindi"
    ],
    "photo": {
      "src": imgRolesAuditor.src,
      "width": 400,
      "height": 500
    }
  },
  {
    "slug": "operations",
    "name": "Operations",
    "role": "Plan2Build operations team",
    "years": 0,
    "certs": [
      "Approves every report",
      "Handles exceptions"
    ],
    "quote": "Watches for overdue decisions, open defects and stages behind plan, and steps in before they cost you.",
    "phone": "",
    "email": "",
    "badge": "04",
    "bio": "## The role\nAssigns inspections, approves every report before you see it, and leads the discussion when you and your contractor disagree.",
    "projects": [],
    "languages": [
      "English",
      "Hindi"
    ],
    "photo": {
      "src": imgRolesOperations.src,
      "width": 400,
      "height": 500
    }
  }
];
