import { DrawingDefs, DrawingLabels, DrawingStrokes } from '@/marketing/sections/home/Safety/DrawingParts';
import { DRAWING_HEIGHT, DRAWING_WIDTH } from '@/marketing/sections/home/Safety/drawing';
import { TYPE } from '@/marketing/lib/typography';

/**
 * The Safety section's elevation drawing, used as a hero's art instead of the house photo. It
 * draws itself once from the piles up on arrival (hero.css drives its `--dr`), rather than
 * with the scroll.
 */
export function HeroDrawing({ label }: { label: string }) {
  return (
    <div className="ph-dw" role="img" aria-label={label}>
      <svg className="safety-dw" viewBox={`0 0 ${DRAWING_WIDTH} ${DRAWING_HEIGHT}`} aria-hidden="true" focusable="false" style={TYPE.mono}>
        <DrawingDefs />
        <DrawingStrokes />
        <DrawingLabels />
      </svg>
    </div>
  );
}
