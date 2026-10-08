import type { StyleWithVars } from '@/marketing/lib/css';
import { DRAWING, drawDelay, labelDelay } from './drawing';
import './safety.css';

/** `--a`: the draw progress at which this part of the drawing appears. */
const appearAt = (delay: string): StyleWithVars => ({ '--a': delay });

/** The hatch fills the drawing's foundations and highlights use. */
export function DrawingDefs() {
  return (
    <defs>
      <pattern id="safety-hy" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="9" height="9" fill="var(--gd-brass)" opacity=".34" />
        <rect width="4" height="9" fill="var(--gd-brass)" />
      </pattern>
      <pattern id="safety-hc" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="1" height="5" fill="var(--gd-ink)" opacity=".55" />
      </pattern>
    </defs>
  );
}

/** Every line of the drawing, each drawn in (stroke-dashoffset) once `--dr` passes its `--a`. */
export function DrawingStrokes() {
  return (
    <g className="safety-ln">
      {DRAWING.strokes.map((stroke, index) => (
        <path key={index} d={stroke.d} pathLength={1} className={`k-${stroke.kind}`} style={appearAt(drawDelay(stroke.y))} />
      ))}
    </g>
  );
}

/** Level names, the height dimension and the grid axis letters. */
export function DrawingLabels() {
  return (
    <g className="safety-tx">
      {DRAWING.labels.map((label, index) => (
        <text
          key={index}
          x={label.x}
          y={label.y}
          textAnchor={label.anchor}
          transform={label.vertical ? `rotate(-90 ${label.x} ${label.y})` : undefined}
          style={appearAt(labelDelay(label))}
        >
          {label.text}
        </text>
      ))}
    </g>
  );
}
