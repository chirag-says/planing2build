/** Copy for "04 · How a house gets built", the stage chart on `/` and `/services`. Units are months. */

/** One of the 16 canonical construction stages (system blueprint, S04 §4). */
export type ScheduleStage = {
  name: string;
  /** Short chip after the name: the audit gate the stage carries ("Gate 3"). Empty = none. */
  tag?: string;
};

export type SchedulePhase = {
  name: string;
  /** First month of the phase. */
  start: number;
  /** Month the phase ends (its milestone). */
  end: number;
  /** The phase's stages in order; stage numbers run on across phases (01 to 16). */
  stages: ScheduleStage[];
};

export type ScheduleContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the ink beam. */
  heading: string;
  subCopy: string;
  /** Up to 8 phases; the chart length follows the last end month. */
  phases: SchedulePhase[];
  weekLabel: string;
  todayLabel: string;
  weeksWord: string;
  phaseWord: string;
  /** "Stage" -> "Stages 03–05" in the panel. */
  stageWord: string;
  /** Shown on the dimension line under the chart after the total months. */
  note: string;
};

export const schedule: ScheduleContent = {
  eyebrow: '04 · How a house gets built',
  heading: 'Sixteen stages,|*one plan.*',
  subCopy:
    'The 16 construction stages fall into five phases. Your workspace tracks each one with planned and actual dates, and every decision comes up before the stage that needs it.',
  phases: [
    { name: 'Plan', start: 0, end: 3, stages: [{ name: 'Drawings & approvals' }] },
    {
      name: 'Foundation',
      start: 3,
      end: 6,
      stages: [
        { name: 'Site prep & excavation' },
        { name: 'Foundation & footings', tag: 'Gate 1' },
        { name: 'Plinth & backfilling', tag: 'Gate 2' },
      ],
    },
    {
      name: 'Structure',
      start: 5,
      end: 11,
      stages: [
        { name: 'Columns & beams, each floor' },
        { name: 'Slab casting, each floor', tag: 'Gate 3' },
        { name: 'Blockwork & brickwork' },
        { name: 'Roof, parapet & staircase' },
      ],
    },
    {
      name: 'Services & finishes',
      start: 10,
      end: 18,
      stages: [
        { name: 'Concealed wiring & pipes', tag: 'Gate 4' },
        { name: 'Waterproofing', tag: 'Gate 5' },
        { name: 'Plastering' },
        { name: 'Doors, windows & grills' },
        { name: 'Flooring & tiling' },
        { name: 'Fittings & sanitary' },
        { name: 'Painting & finishes' },
      ],
    },
    { name: 'Handover', start: 17, end: 20, stages: [{ name: 'External works & handover', tag: 'Gate 6' }] },
  ],
  weekLabel: 'Month',
  todayLabel: 'Today',
  weeksWord: 'Months',
  phaseWord: 'Phase',
  stageWord: 'Stage',
  note: 'Plan to handover · 2,650 sq ft, G+1 · indicative',
};
