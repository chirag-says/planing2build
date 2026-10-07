'use client';

import { useEffect, useRef, type RefObject } from 'react';
import type { TradeService } from './TradesSection';
import { cx } from '@/marketing/lib/cx';
import { onFrame } from '@/marketing/lib/ticker';
import { framerPhoto } from '@/marketing/lib/images';

/** Fraction of the remaining distance to the pointer the hook covers each frame. */
const FOLLOW = 0.16;
/** Degrees of tilt per px the hook trails the pointer horizontally (negative: swings back). */
const TILT_PER_PX = -0.22;
const MAX_TILT = 16;
/** Fraction of the remaining tilt applied each frame, slower than the follow so it swings. */
const TILT_EASE = 0.12;
/** Px the rig needs under the pointer: the 62px cable and the 280px photo, plus a margin. */
const DROP = 62 + 280 + 16;
/** Px of extra room needed before a flipped photo drops back down, so it doesn't flicker. */
const FLIP_HYSTERESIS = 40;

type HangingPhotoProps = {
  /** The element whose pointer movement the photo follows. */
  areaRef: RefObject<HTMLElement | null>;
  services: TradeService[];
  /** Index of the hovered service, -1 for none. */
  active: number;
  onLeave: () => void;
};

/**
 * The hovered service's photo hanging from the cursor on a cable. The hook eases toward the
 * pointer and the whole rig tilts against the direction of travel, so fast sideways moves make
 * the photo swing and settle. Near the bottom of the section the rig flips and the photo is held
 * above the pointer instead, so it is never cut off.
 */
export function HangingPhoto({ areaRef, services, active, onLeave }: HangingPhotoProps) {
  const rigRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const area = areaRef.current;
    const rig = rigRef.current;
    if (!area || !rig) return;

    const pointer = { x: 0, y: 0, targetX: 0, targetY: 0, tilt: 0 };
    let stopFrames: (() => void) | null = null;
    let up = false;
    // The section clips the rig at its edges, as does the viewport.
    const clipper = area.closest('section') ?? area;

    /** Hangs the photo above the pointer when there is no room below and more room above. */
    const place = (y: number) => {
      const box = clipper.getBoundingClientRect();
      const below = Math.min(window.innerHeight, box.bottom) - y;
      const above = y - Math.max(0, box.top);
      const next = (up ? below < DROP + FLIP_HYSTERESIS : below < DROP) && above > below;
      if (next === up) return;
      up = next;
      // An attribute, not a class: React rewrites className whenever the hovered row changes.
      rig.toggleAttribute('data-up', up);
    };

    const follow = () => {
      const lag = pointer.targetX - pointer.x;
      pointer.x += lag * FOLLOW;
      pointer.y += (pointer.targetY - pointer.y) * FOLLOW;
      const tilt = Math.max(-MAX_TILT, Math.min(MAX_TILT, lag * TILT_PER_PX));
      pointer.tilt += (tilt - pointer.tilt) * TILT_EASE;
      rig.style.transform = `translate3d(${pointer.x.toFixed(1)}px,${pointer.y.toFixed(1)}px,0) rotate(${pointer.tilt.toFixed(2)}deg)`;
    };
    const onMove = (event: PointerEvent) => {
      pointer.targetX = event.clientX;
      pointer.targetY = event.clientY;
      place(event.clientY);
      if (stopFrames) return;
      // Entering: jump to the pointer instead of flying in from the last exit point.
      pointer.x = pointer.targetX;
      pointer.y = pointer.targetY;
      stopFrames = onFrame({ write: follow });
    };
    // Leaving freezes the rig where it is while the photo folds away.
    const onPointerLeave = () => {
      stopFrames?.();
      stopFrames = null;
      onLeave();
    };

    area.addEventListener('pointermove', onMove, { passive: true });
    area.addEventListener('pointerleave', onPointerLeave);
    return () => {
      stopFrames?.();
      area.removeEventListener('pointermove', onMove);
      area.removeEventListener('pointerleave', onPointerLeave);
    };
  }, [areaRef, onLeave]);

  return (
    <div ref={rigRef} className={cx('trades-hang', active >= 0 && 'is-on')} aria-hidden="true">
      <i className="trades-hang-l" />
      <i className="trades-hang-h" />
      <div className="trades-hang-p">
        {services.map((service, index) => {
          const image = framerPhoto(service.photo, '320px');
          return (
            <img
              key={service.slug}
              className={cx(index === active && 'is-on')}
              src={image.src}
              srcSet={image.srcSet}
              sizes={image.sizes}
              alt=""
              loading="lazy"
              decoding="async"
              draggable={false}
            />
          );
        })}
      </div>
    </div>
  );
}
