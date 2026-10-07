/**
 * Geometry of the Safety section's elevation drawing: a four-bay, five-storey building on piles
 * with a scaffold on its left, a tower crane on its right, level marks and grid axes. Coordinates
 * are in a 720 × 860 viewBox. Everything here is computed once on the server.
 *
 * Each stroke carries the lowest point it reaches (`y`), which sets when it is drawn: the
 * drawing builds from the ground up as the section scrolls (see `drawDelay`).
 */
export const DRAWING_WIDTH = 720;
export const DRAWING_HEIGHT = 860;

/**
 * Stroke styles: h heavy rule, m medium, l light, f solid ink fill (slabs), c light fill
 * (columns, plant), x cross-hatched (foundations), y yellow fill (the crane's load).
 */
export type StrokeKind = 'h' | 'm' | 'l' | 'f' | 'c' | 'x' | 'y';

export type DrawingStroke = { d: string; y: number; kind: StrokeKind };

export type DrawingLabel = {
  x: number;
  y: number;
  text: string;
  anchor: 'start' | 'middle' | 'end';
  /** Rotated -90° about its anchor (the vertical height dimension). */
  vertical?: boolean;
};

/** Grid axes A–D, 9.00 m apart. */
export const GRID_X = [240, 333, 427, 520] as const;
/** Floor levels from ground (L01) to roof. */
export const LEVEL_Y = [590, 506, 422, 338, 254, 170] as const;
/** The five storeys, each from its floor level (base) up to the level above (top). */
export const STOREYS = LEVEL_Y.slice(1).map((top, index) => ({ base: LEVEL_Y[index] ?? top, top }));

/** Lowest point of the ground-floor slab, used for the rotated height label's timing. */
const GROUND_Y = 590;
/** Long verticals are split into pieces of this height so they draw in steps. */
const SEGMENT = 84;

/**
 * When a part of the drawing appears, as a fraction of the draw progress `--dr` (0..1):
 * 0 at the bottom of the viewBox, 0.82 at the top, so the last strokes still finish by 1.
 */
export const drawDelay = (y: number) => (((DRAWING_HEIGHT - y) / DRAWING_HEIGHT) * 0.82).toFixed(3);

function buildDrawing() {
  const strokes: DrawingStroke[] = [];
  const labels: DrawingLabel[] = [];

  const line = (x1: number, y1: number, x2: number, y2: number, kind: StrokeKind = 'm') => {
    strokes.push({ d: `M${x1} ${y1}L${x2} ${y2}`, y: Math.max(y1, y2), kind });
  };
  const segmented = (x: number, from: number, to: number, kind: StrokeKind = 'm') => {
    for (let y = from; y > to; y -= SEGMENT) line(x, y, x, Math.max(to, y - SEGMENT), kind);
  };
  const box = (x: number, y: number, width: number, height: number, kind: StrokeKind = 'm') => {
    strokes.push({ d: `M${x} ${y + height}V${y}H${x + width}V${y + height}Z`, y: y + height, kind });
  };
  // lattice between two chords: a zigzag from (x1, yA) to x2, alternating to yB every `step`
  const lattice = (x1: number, x2: number, yA: number, yB: number, step: number, kind: StrokeKind = 'l') => {
    let d = `M${x1} ${yA}`;
    const count = Math.round(Math.abs(x2 - x1) / step);
    for (let index = 1; index <= count; index++) {
      d += `L${(x1 + ((x2 - x1) * index) / count).toFixed(1)} ${index % 2 ? yB : yA}`;
    }
    strokes.push({ d, y: Math.max(yA, yB), kind });
  };

  // ground line and hatching
  line(24, 590, 222, 590, 'h');
  line(538, 590, 700, 590, 'h');
  for (const x of [44, 92, 140, 552, 644, 684]) {
    for (let tick = 0; tick < 3; tick++) line(x + tick * 7, 590, x + tick * 7 - 9, 601, 'l');
  }

  // piles and pile caps under each grid axis
  for (const x of GRID_X) {
    segmented(x - 8, 776, 706);
    segmented(x + 8, 776, 706);
    strokes.push({ d: `M${x - 8} 776L${x} 790L${x + 8} 776`, y: 790, kind: 'm' });
    box(x - 24, 688, 48, 18, 'x');
  }

  // basement: raft, walls, columns, stair, ground slab
  box(230, 674, 300, 14, 'x');
  box(230, 600, 12, 74, 'x');
  box(518, 600, 12, 74, 'x');
  box(327, 600, 12, 74, 'c');
  box(421, 600, 12, 74, 'c');
  line(350, 674, 410, 632, 'l');
  line(410, 632, 422, 632, 'l');
  line(410, 632, 350, 600, 'l');
  box(222, 590, 316, 10, 'f');

  // five storeys: columns, stair, window heads and sills, facade, scaffold, slab
  for (const { base, top } of STOREYS) {
    for (const x of GRID_X) box(x - 6, top + 10, 12, base - top - 10, 'c');
    line(350, base, 410, base - 42, 'l');
    line(410, base - 42, 422, base - 42, 'l');
    line(410, base - 42, 350, top + 10, 'l');
    for (const x of [222, 530]) {
      line(x, base - 34, x + 8, base - 34, 'l');
      line(x, top + 18, x + 8, top + 18, 'l');
    }
    line(222, base, 222, top, 'm');
    line(226, base, 226, top, 'l');
    line(538, base, 538, top, 'm');
    line(534, base, 534, top, 'l');
    line(176, base, 176, top, 'm');
    line(212, base, 212, top, 'm');
    line(176, base - 42, 212, base - 42, 'l');
    line(176, base, 212, base - 42, 'l');
    line(212, base - 42, 176, top, 'l');
    box(230, top, 300, 10, 'f');
    line(173, top, 215, top, 'h');
    line(212, top - 3, 222, top - 3, 'm');
  }

  // roof: scaffold guard rail, parapets, falls, stair core, plant and vents
  line(176, 170, 176, 148, 'm');
  line(212, 170, 212, 148, 'm');
  line(176, 150, 212, 150, 'l');
  line(176, 160, 212, 160, 'l');
  line(222, 170, 222, 146, 'm');
  line(538, 170, 538, 146, 'm');
  box(222, 146, 12, 24, 'c');
  box(526, 146, 12, 24, 'c');
  line(218, 146, 238, 146, 'h');
  line(522, 146, 542, 146, 'h');
  strokes.push({ d: 'M234 152V162L270 167L350 162', y: 167, kind: 'm' });
  strokes.push({ d: 'M414 162H526V152', y: 162, kind: 'm' });
  box(266, 165, 8, 5, 'm');
  box(350, 136, 64, 34, 'c');
  line(345, 136, 419, 136, 'h');
  box(392, 146, 14, 24, 'l');
  box(462, 136, 50, 24, 'c');
  for (const y of [143, 148, 153]) line(468, y, 492, y, 'l');
  line(468, 160, 468, 162, 'm');
  line(506, 160, 506, 162, 'm');
  box(497, 141, 9, 9, 'l');

  // crane: base, lattice mast, ties back to the building at L03 and L05
  box(576, 590, 48, 14, 'x');
  for (let y = 590, bay = 0; y > 70; y -= 26, bay++) {
    line(588, y, 588, y - 26, 'm');
    line(612, y, 612, y - 26, 'm');
    line(588, y - 26, 612, y - 26, 'l');
    if (bay % 2) line(588, y, 612, y - 26, 'l');
    else line(612, y, 588, y - 26, 'l');
  }
  for (const y of [LEVEL_Y[2], LEVEL_Y[4]]) {
    box(583, y - 9, 34, 18, 'm');
    line(583, y - 6, 538, y + 5, 'm');
    line(583, y + 6, 538, y + 5, 'm');
  }

  // crane top: cab, apex, jib, counter-jib with its weight, pendants, trolley, hook and load
  box(584, 58, 32, 12, 'c');
  box(616, 62, 16, 17, 'c');
  line(600, 58, 600, 24, 'm');
  line(584, 58, 262, 58, 'm');
  line(584, 46, 262, 46, 'm');
  line(262, 58, 262, 46, 'm');
  lattice(584, 262, 58, 46, 12);
  line(616, 58, 692, 58, 'm');
  line(616, 48, 692, 48, 'm');
  line(692, 58, 692, 48, 'm');
  lattice(616, 692, 58, 48, 12);
  box(664, 58, 28, 22, 'f');
  line(600, 24, 334, 46, 'l');
  line(600, 24, 678, 48, 'l');
  box(292, 58, 16, 6, 'f');
  line(300, 64, 300, 100, 'l');
  box(296, 100, 8, 8, 'f');
  line(300, 108, 276, 116, 'l');
  line(300, 108, 324, 116, 'l');
  box(270, 116, 60, 9, 'y');

  // level marks on the left: leader line, triangle, label
  const levels: Array<[string, number]> = [
    ['B1 −4.20', 674],
    ['L01 ±0.00', 590],
    ['L02 +4.20', 506],
    ['L03 +8.40', 422],
    ['L04 +12.60', 338],
    ['L05 +16.80', 254],
    ['ROOF +21.00', 170],
  ];
  for (const [text, y] of levels) {
    line(34, y, y === 674 ? 222 : 166, y, 'l');
    strokes.push({ d: `M133 ${y - 9}H147L140 ${y}Z`, y, kind: 'm' });
    labels.push({ x: 127, y: y - 5, text, anchor: 'end' });
  }

  // overall height dimension on the right
  segmented(666, 590, 170, 'l');
  line(660, 596, 672, 584, 'm');
  line(660, 176, 672, 164, 'm');
  line(630, 170, 678, 170, 'l');
  labels.push({ x: 659, y: 500, text: '21.00 m', anchor: 'middle', vertical: true });

  // grid axes below: dimension line, ticks, bubbles A–D and bay widths
  line(240, 814, 520, 814, 'l');
  GRID_X.forEach((x, index) => {
    line(x - 5, 819, x + 5, 809, 'm');
    line(x, 829, x, 800, 'l');
    strokes.push({ d: `M${x - 11} 841a11 11 0 1 0 22 0a11 11 0 1 0 -22 0`, y: 852, kind: 'm' });
    labels.push({ x, y: 845, text: 'ABCD'[index] ?? '', anchor: 'middle' });
    if (index) labels.push({ x: (x + (GRID_X[index - 1] ?? x)) / 2, y: 808, text: '9.00', anchor: 'middle' });
  });

  return { strokes, labels };
}

export const DRAWING = buildDrawing();

/** Delay for a label: the rotated height label appears with the ground floor. */
export const labelDelay = (label: DrawingLabel) => drawDelay(label.vertical ? GROUND_Y : label.y);

/**
 * Where each check is pinned on the drawing (marker at x, y), the leader line from the marker
 * out to the side the card hangs on, and the height (ly) where it meets the card.
 */
export type Callout = { x: number; y: number; leader: string; ly: number; side: 'l' | 'r' };

export const CALLOUTS: Callout[] = [
  { x: 427, y: 697, leader: 'M427 697L451 721H720', ly: 721, side: 'r' },
  { x: 333, y: 511, leader: 'M333 511L292 470H0', ly: 470, side: 'l' },
  { x: 534, y: 380, leader: 'M534 380L558 356H720', ly: 356, side: 'r' },
  { x: 428, y: 166, leader: 'M428 166L476 118H720', ly: 118, side: 'r' },
  { x: 194, y: 212, leader: 'M194 212L170 188H0', ly: 188, side: 'l' },
];
