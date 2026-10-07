/** Copy for the home page's crew section ("06 · On your side"). Badges come from `team`. */
export type CrewContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  subCopy: string;
  /** Team button label; empty hides the button. */
  allLabel: string;
  allLink: string;
  /** Printed after the site name at the top of every badge ("Plan2Build · Role"). */
  idLabel: string;
  yearsWord: string;
  badgeWord: string;
  /** Profile button, followed by the member's first name ("Meet Marcus"). Empty = no button. */
  meetWord: string;
};

export const crew: CrewContent = {
  eyebrow: '06 · On your side',
  heading: 'The people|*on your side.*',
  subCopy:
    'Nobody here works for your contractor or for a brand. Each role answers to your family and to the plan.',
  allLabel: '',
  allLink: '/about',
  idLabel: 'Role',
  yearsWord: 'yrs',
  badgeWord: 'Role',
  meetWord: '',
};
