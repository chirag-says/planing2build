/** Copy for "02 · What we do", the service rows shown on `/` and `/services`. Rows come from `services`. */

export type TradesContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  /** Empty hides the button. */
  button: string;
  buttonLink: string;
  /** Stands before each service's starting price ("From ₹4,999"); empty when the fees already say it. */
  fromWord: string;
  /** How many services are listed, in their CMS order. */
  rows: number;
  /** Desktop with a mouse: the hovered service's photo hangs from the cursor. */
  hoverPhoto: boolean;
};

export const trades: TradesContent = {
  eyebrow: '02 · What we do',
  heading: 'Six services,|*one side: yours.*',
  button: 'All services',
  buttonLink: '/services',
  fromWord: '',
  rows: 6,
  hoverPhoto: true,
};
