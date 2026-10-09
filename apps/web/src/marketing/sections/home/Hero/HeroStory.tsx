import type { CSSProperties } from 'react';
import { TYPE } from '@/marketing/lib/typography';
import './hero-story.css';

/**
 * The homeowners hero's art: a family home built once, in seven steps, drawn in code in the site's
 * own language (ink linework, brass plates, warm timber). One clock drives everything: `--bt`
 * runs 0 -> 1 a single time (hero-story.css) and stays there, on the finished house. Each piece
 * takes its own window of it, `--a` (when it starts) and `--d` (how long it takes):
 *
 *   0.00 - 0.24  01 PLAN     a ghost of the finished elevation is drawn, then the plot is set out
 *                            and footings, columns and slabs go in while a crane lifts material
 *   0.24 - 0.38  02 FIND     a card: approved professionals
 *   0.36 - 0.50  03 COMPARE  a card: three quotes on one scope
 *   0.48 - 0.60  04 SELECT   a card: the family chooses
 *   0.56 - 0.76  05 BUILD    masonry, services chased in, plaster, glazing, timber
 *   0.76 - 0.90  06 VERIFY   the crane leaves, terrace planting, lights on, six checks stamped
 *   0.90 - 1.00  07 RECORD   a card: the build record, kept for good
 *
 * The drawing's own pieces are timed on a simpler 0-1 scale of their own (plan / build / finish);
 * `win` maps that onto the windows above. With reduced motion the film rests on its end.
 * Server-rendered, no script.
 */

/** What is seen: the crane's room on the left, no empty sky above the house. */
const VX = -100;
const VY = 110;
const VW = 740;
const VH = 654;
/** Ground line, the two floor slabs and the roof slab (y of each top edge). */
const GROUND = 630;
const SLAB1 = 468;
const ROOF = 320;
const COLS = [130, 235, 340, 445, 550];

/**
 * The drawing's pieces are written on a 0-1 scale of three phases (plan 0-0.36, build 0.36-0.72,
 * finish 0.72-0.9); `win` puts each phase in its place in the seven steps, leaving the middle of
 * the film for the professionals, the quotes and the choice.
 */
const PLAN_END = 0.36;
const BUILD_END = 0.72;
const phase = (x: number, endOfPiece: boolean) => {
  // A piece that starts exactly on a boundary belongs to the phase that begins there; one that
  // ends there belongs to the phase that ends there.
  const eps = endOfPiece ? 1e-9 : -1e-9;
  return x <= PLAN_END + eps ? 0 : x <= BUILD_END + eps ? 1 : 2;
};
const place = (x: number, endOfPiece: boolean) => {
  const p = phase(x, endOfPiece);
  return p === 0 ? (x * 0.25) / PLAN_END : p === 1 ? 0.56 + ((x - PLAN_END) * 0.2) / (BUILD_END - PLAN_END) : 0.76 + ((x - BUILD_END) * 0.16) / 0.18;
};
const win = (a: number, d: number) => {
  const from = place(a, false);
  return { '--a': from, '--d': Math.max(0.001, place(a + d, true) - from) } as CSSProperties;
};
const when = (s: number, e: number) => ({ '--s': s, '--e': e }) as CSSProperties;

type Bay = { x: number; w: number };
const bay = (index: number): Bay => {
  const left = (COLS[index] ?? 0) + 7;
  return { x: left, w: (COLS[index + 1] ?? 0) - 7 - left };
};

/** Ground-floor and first-floor masonry panels (bay index, top, height). */
const GF_Y = SLAB1 + 14;
const GF_H = GROUND - 14 - GF_Y;
const FF_Y = ROOF + 14;
const FF_H = SLAB1 - FF_Y;
const GF_WALLS = [0, 1, 2];
const FF_WALLS = [0, 1, 2, 3];

/** Openings: where glass goes (and a dark void shows while the masonry is still bare). */
const OPENINGS = [
  { x: 156, y: 520, w: 50, h: 62, at: 0.62 },
  { x: 254, y: 504, w: 66, h: 112, at: 0.635 },
  { x: 152, y: 350, w: 62, h: 100, at: 0.65 },
  { x: 262, y: 372, w: 52, h: 60, at: 0.665 },
  { x: 358, y: 350, w: 70, h: 100, at: 0.68 },
  { x: 462, y: 350, w: 138, h: 100, at: 0.695 },
];

const LEAVES = [
  { x: 396, h: 44, s: 0.74 },
  { x: 432, h: 56, s: 0.755 },
  { x: 470, h: 40, s: 0.77 },
  { x: 508, h: 58, s: 0.785 },
  { x: 544, h: 42, s: 0.8 },
];

export function HeroStory({ alt }: { alt: string }) {
  return (
    <div className="hs" role="img" aria-label={alt}>
      <svg className="hs-svg" viewBox={`${VX} ${VY} ${VW} ${VH}`} aria-hidden="true" focusable="false" style={TYPE.mono}>
        <defs>
          <pattern id="hs-brick" width="24" height="10" patternUnits="userSpaceOnUse">
            <rect width="24" height="10" fill="#d9cdbf" />
            <rect x="1" y="1" width="22" height="3.6" fill="#b46a4e" />
            <rect x="-11" y="5.6" width="22" height="3.6" fill="#a95f45" />
            <rect x="13" y="5.6" width="22" height="3.6" fill="#a95f45" />
          </pattern>
          <pattern id="hs-hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <path d="M0 0V7" stroke="#1c1f22" strokeWidth="1" />
          </pattern>
          <pattern id="hs-slat" width="9" height="10" patternUnits="userSpaceOnUse">
            <rect width="9" height="10" fill="#c58f58" />
            <rect width="3.2" height="10" fill="#8d5b2e" />
          </pattern>
          <linearGradient id="hs-glass" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#c6d3da" />
            <stop offset="1" stopColor="#8fa4b0" />
          </linearGradient>
          <radialGradient id="hs-sun" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#ffcf4a" stopOpacity="0.55" />
            <stop offset="1" stopColor="#ffcf4a" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="hs-glow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#ffd98a" />
            <stop offset="1" stopColor="#f2a94b" />
          </linearGradient>
        </defs>

        {/* The lights coming on warm the air around the house. */}
        <ellipse className="hs-sun" style={win(0.8, 0.1)} cx="360" cy="470" rx="330" ry="250" fill="url(#hs-sun)" />

        {/* A ghost of the finished elevation, drawn first; the real build fills it in. */}
        <g className="hs-ghost">
          <path
            className="hs-ghost-line hs-draw"
            pathLength={1}
            style={win(0.02, 0.2)}
            d={`M100 ${GROUND}H570V${SLAB1 + 14}H620V${SLAB1}H100V${ROOF + 14}H590V${ROOF}H100ZM${COLS.map((c) => `M${c - 7} ${ROOF + 14}V${GROUND - 14}M${c + 7} ${ROOF + 14}V${GROUND - 14}`).join('')}`}
          />
          <path
            className="hs-ghost-line hs-draw"
            pathLength={1}
            style={win(0.1, 0.2)}
            d={OPENINGS.map((o) => `M${o.x} ${o.y}h${o.w}v${o.h}h${-o.w}Z`).join('')}
          />
        </g>

        {/* A tower crane at the left lifts loads over the roof while the frame goes up, then leaves. */}
        <g className="hs-crane" style={win(0.04, 0.1)}>
          <path className="hs-crane-line" d={`M-52 ${GROUND}V236M-30 ${GROUND}V236${Array.from({ length: 13 }, (_, i) => { const y = GROUND - i * 32; return `M-52 ${y}L-30 ${y - 32}M-30 ${y}L-52 ${y - 32}`; }).join('')}`} />
          <path className="hs-crane-line" d="M-92 236H214M-62 252H196M-92 236L-62 252M-62 252L-30 236M-30 252L10 236M10 252L50 236M50 252L90 236M90 252L130 236M130 252L170 236M170 252L214 236" />
          <path className="hs-crane-line" d="M-41 236V206M-41 206L-92 236M-41 206L214 236" />
          <rect className="hs-crane-weight" x="-96" y="236" width="24" height="30" />
          <rect className="hs-crane-cab" x="-56" y="252" width="24" height="18" />
          <g className="hs-trolley">
            <rect className="hs-crane-cab" x="12" y="252" width="16" height="8" />
            <rect className="hs-cable" x="19" y="260" width="2" height="100" />
            <g className="hs-load">
              <path className="hs-crane-line" d="M20 0L8 18M20 0L32 18" />
              <rect className="hs-crane-load" x="6" y="18" width="28" height="18" />
            </g>
          </g>
        </g>

        <g className="hs-ground">
          {/* The plot: boundary, set-out pegs and the ground line, there from the start. */}
          <path className="hs-plot hs-draw" pathLength={1} style={win(0.0, 0.07)} d={`M40 ${GROUND + 70}H600M40 ${GROUND + 70}V${GROUND + 6}M600 ${GROUND + 70}V${GROUND + 6}`} />
          <path className="hs-ink hs-draw" pathLength={1} style={win(0.0, 0.06)} d={`M-96 ${GROUND}H636`} />
          {[40, 600].map((x) => (
            <rect key={x} className="hs-peg hs-fade" style={win(0.04, 0.03)} x={x - 4} y={GROUND + 66} width="8" height="8" />
          ))}
        </g>

        {/* Two brass plates behind the house, as on the home page. */}
        <rect className="hs-plate hs-fade" style={win(0.0, 0.1)} x="330" y="170" width="250" height="150" />
        <rect className="hs-plate hs-fade" style={win(0.02, 0.1)} x="18" y="560" width="120" height="82" />

        <g className="hs-stage">
          {/* PLAN: foundations */}
          <rect className="hs-found hs-sweep" style={win(0.08, 0.06)} x="100" y={GROUND} width="470" height="20" />
          {COLS.map((c, i) => (
            <rect key={`pad${c}`} className="hs-found hs-rise" style={win(0.1 + i * 0.012, 0.05)} x={c - 28} y={GROUND + 20} width="56" height="24" />
          ))}
          <rect className="hs-concrete hs-sweep" style={win(0.15, 0.05)} x="100" y={GROUND - 14} width="470" height="14" />

          {/* PLAN: columns rise one by one */}
          {COLS.map((c, i) => (
            <rect key={`col${c}`} className="hs-concrete hs-rise" style={win(0.17 + i * 0.026, 0.06)} x={c - 7} y={ROOF + 14} width="14" height={GROUND - 14 - ROOF - 14} />
          ))}

          {/* PLAN: slabs sweep across, ground-floor ceiling first, then the cantilevered floor and roof */}
          <rect className="hs-concrete hs-sweep" style={win(0.27, 0.05)} x="100" y={SLAB1} width="520" height="14" />
          <rect className="hs-concrete hs-sweep" style={win(0.31, 0.05)} x="100" y={ROOF} width="490" height="14" />

          {/* COMPARE: masonry rises bay by bay, with the openings left dark */}
          {GF_WALLS.map((b, i) => {
            const { x, w } = bay(b);
            return <rect key={`gf${b}`} className="hs-brick hs-rise" style={win(0.36 + i * 0.022, 0.06)} x={x} y={GF_Y} width={w} height={GF_H} />;
          })}
          {FF_WALLS.map((b, i) => {
            const { x, w } = bay(b);
            const right = b === 3 ? 612 - x : w;
            return <rect key={`ff${b}`} className="hs-brick hs-rise" style={win(0.42 + i * 0.022, 0.06)} x={x} y={FF_Y} width={right} height={FF_H} />;
          })}
          {/* The carport stays open: a dark void under the cantilever. */}
          <rect className="hs-void hs-fade" style={win(0.44, 0.04)} x={bay(3).x} y={GF_Y} width={bay(3).w} height={GF_H} />
          {OPENINGS.map((o, i) => (
            <rect key={`vo${i}`} className="hs-void hs-fade" style={win(0.46 + i * 0.012, 0.04)} x={o.x} y={o.y} width={o.w} height={o.h} />
          ))}

          {/* BUILD: conduits and a soil stack chased into the masonry, then plastered over */}
          <path className="hs-wire hs-draw" pathLength={1} style={win(0.5, 0.05)} d="M140 512V560M140 560H152M268 500V470M268 470H330M352 340V300" />
          <path className="hs-wire hs-draw" pathLength={1} style={win(0.525, 0.05)} d="M226 374V440H246M326 346V380M326 380H355" />
          <path className="hs-pipe hs-draw" pathLength={1} style={win(0.515, 0.05)} d={`M232 ${GF_Y}V${GROUND - 20}`} />

          {[...GF_WALLS.map((b) => ({ b, y: GF_Y, h: GF_H, ff: false })), ...FF_WALLS.map((b) => ({ b, y: FF_Y, h: FF_H, ff: true }))].map(({ b, y, h, ff }, i) => {
            const { x, w } = bay(b);
            const right = ff && b === 3 ? 612 - x : w;
            return <rect key={`pl${ff ? 'f' : 'g'}${b}`} className="hs-plaster hs-fade" style={win(0.565 + i * 0.006, 0.04)} x={x} y={y} width={right} height={h} />;
          })}

          {/* BUILD: glazing fitted, then the timber screen slides across the ground-floor bay */}
          {OPENINGS.map((o, i) => (
            <g key={`gl${i}`}>
              <rect className="hs-glass hs-fade" style={win(o.at, 0.04)} x={o.x} y={o.y} width={o.w} height={o.h} />
              <rect className="hs-lit hs-fade" style={win(0.8 + i * 0.01, 0.04)} x={o.x} y={o.y} width={o.w} height={o.h} />
              <path className="hs-frame hs-fade" style={win(o.at, 0.04)} d={`M${o.x + o.w / 2} ${o.y}V${o.y + o.h}M${o.x} ${o.y + o.h * 0.35}H${o.x + o.w}`} />
            </g>
          ))}
          <rect className="hs-slats hs-sweep" style={win(0.665, 0.05)} x={bay(2).x} y={GF_Y} width={bay(2).w} height={GF_H} />
          <rect className="hs-slats hs-sweep" style={win(0.7, 0.05)} x="452" y={SLAB1 + 14} width="6" height={GF_H} />

          {/* VERIFY: terrace planter, planting and the tree grow in; the lights come on */}
          <rect className="hs-concrete hs-rise" style={win(0.72, 0.03)} x="384" y={ROOF - 24} width="196" height="24" />
          {LEAVES.map((l, i) => (
            <path
              key={`lf${i}`}
              className="hs-leaf hs-grow"
              style={win(l.s, 0.05)}
              d={`M${l.x} ${ROOF - 24}C${l.x - 22} ${ROOF - 24 - l.h * 0.5} ${l.x - 8} ${ROOF - 24 - l.h} ${l.x} ${ROOF - 24 - l.h}C${l.x + 8} ${ROOF - 24 - l.h} ${l.x + 22} ${ROOF - 24 - l.h * 0.5} ${l.x} ${ROOF - 24}Z`}
            />
          ))}
          <rect className="hs-trunk hs-rise" style={win(0.74, 0.05)} x="46" y={GROUND - 140} width="8" height="140" />
          {[
            { cx: 50, cy: GROUND - 160, r: 44, s: 0.77 },
            { cx: 22, cy: GROUND - 132, r: 28, s: 0.785 },
            { cx: 80, cy: GROUND - 138, r: 30, s: 0.8 },
          ].map((c, i) => (
            <circle key={`tr${i}`} className="hs-canopy hs-grow" style={win(c.s, 0.05)} cx={c.cx} cy={c.cy} r={c.r} />
          ))}
        </g>

        {/* Levels and dimensions: set out with the plan, then the floors as the slabs go in */}
        <g className="hs-dim">
          <path className="hs-ink hs-draw" pathLength={1} style={win(0.05, 0.07)} d={`M130 ${GROUND + 98}H550M130 ${GROUND + 92}V${GROUND + 104}M235 ${GROUND + 92}V${GROUND + 104}M340 ${GROUND + 92}V${GROUND + 104}M445 ${GROUND + 92}V${GROUND + 104}M550 ${GROUND + 92}V${GROUND + 104}`} />
          {[182, 287, 392, 497].map((x) => (
            <text key={x} className="hs-label hs-fade" style={win(0.1, 0.04)} x={x} y={GROUND + 88} textAnchor="middle">
              3.00
            </text>
          ))}
          {[
            { y: GROUND, t: 'GF +0.00', a: 0.12 },
            { y: SLAB1, t: 'L1 +3.60', a: 0.28 },
            { y: ROOF, t: 'ROOF +7.20', a: 0.32 },
          ].map((l) => (
            <g key={l.t} className="hs-fade" style={win(l.a, 0.04)}>
              <path className="hs-ink" d={`M8 ${l.y}H90`} />
              <text className="hs-label" x="8" y={l.y - 6}>
                {l.t}
              </text>
            </g>
          ))}
        </g>
      </svg>

      {/* One card at the top right per early step, each in turn: Find, Compare, Select; Record stays. */}
      <div className="hs-card" aria-hidden="true" style={{ ...TYPE.mono, ...when(0.24, 0.4) }}>
        <p className="hs-card-t"><b>02</b>Find</p>
        {['RK', 'AS', 'MP'].map((m, i) => (
          <p key={m} className="hs-pro" style={{ '--i': i } as CSSProperties}>
            <b>{m}</b>
            <i />
            <u>Listed</u>
          </p>
        ))}
      </div>
      <div className="hs-card" aria-hidden="true" style={{ ...TYPE.mono, ...when(0.38, 0.52) }}>
        <p className="hs-card-t"><b>03</b>Compare</p>
        {['A', 'B', 'C'].map((q, i) => (
          <p key={q} className={`hs-q${i === 1 ? ' is-pick' : ''}`} style={{ '--i': i } as CSSProperties}>
            <span>{q}</span>
            <i />
          </p>
        ))}
      </div>
      <div className="hs-card" aria-hidden="true" style={{ ...TYPE.mono, ...when(0.5, 0.62) }}>
        <p className="hs-card-t"><b>04</b>Select</p>
        {['A', 'B', 'C'].map((q, i) => (
          <p key={q} className={`hs-sel${i === 1 ? ' is-pick' : ''}`} style={{ '--i': i } as CSSProperties}>
            <span>{q}</span>
            <i />
            {i === 1 && <u>Chosen</u>}
          </p>
        ))}
      </div>
      <div className="hs-card" aria-hidden="true" style={{ ...TYPE.mono, ...when(0.9, 1.5) }}>
        <p className="hs-card-t"><b>07</b>Record</p>
        <p className="hs-rec">
          {Array.from({ length: 6 }, (_, i) => (
            <i key={i} style={{ '--i': i } as CSSProperties} />
          ))}
        </p>
        <p className="hs-card-s">Kept for good</p>
      </div>

      {/* VERIFY: the stamp. */}
      <div className="hs-stamp" aria-hidden="true" style={TYPE.mono}>
        <b style={TYPE.display}>6 / 6</b>
        <span>Checks passed</span>
      </div>
    </div>
  );
}
