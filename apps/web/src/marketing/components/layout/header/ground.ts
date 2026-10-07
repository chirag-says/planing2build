/**
 * Decides whether the page under the header bar is light or dark, so the bar can switch between
 * concrete-and-ink and night-and-white.
 */

/** Opaque-enough backgrounds only; a faint tint says nothing about the ground. */
const MIN_ALPHA = 0.5;
/** Relative luminance above which a background counts as light. */
const LIGHT_LUMINANCE = 0.4;

/** WCAG relative luminance of a computed `background-color`, or null when it is see-through. */
function luminance(color: string): number | null {
  let channels: number[] | null = null;
  let alpha = 1;
  const rgb = color.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
  if (rgb) {
    channels = [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
    if (rgb[4] !== undefined) alpha = parseFloat(rgb[4]);
  } else {
    // color-mix() results compute to color(srgb r g b / a) with 0–1 channels.
    const srgb = color.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)/);
    if (srgb) {
      channels = [Number(srgb[1]) * 255, Number(srgb[2]) * 255, Number(srgb[3]) * 255];
      if (srgb[4] !== undefined) alpha = parseFloat(srgb[4]);
    }
  }
  if (!channels || alpha < MIN_ALPHA) return null;
  const linear = (value: number) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const [r = 0, g = 0, b = 0] = channels.map(linear);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Light (true), dark (false) or unknown (null) at one viewport point, ignoring the header itself.
 * Explicit markers win: `.gd-lt` is light, `.gd-dark` and media are dark; otherwise the first
 * element with an opaque background decides by its luminance.
 */
function groundAt(x: number, y: number, header: Element): boolean | null {
  for (const element of document.elementsFromPoint(x, y)) {
    if (header.contains(element)) continue;
    if (element.closest('.gd-lt')) return true;
    if (element.closest('.gd-dark') || ['IMG', 'VIDEO', 'CANVAS'].includes(element.tagName)) return false;
    const value = luminance(getComputedStyle(element).backgroundColor);
    if (value !== null) return value > LIGHT_LUMINANCE;
  }
  return null;
}

/**
 * Samples just under the bar's middle line (32px compact, 38px desktop), at the centre first and
 * then towards each side, and takes the first point that gives an answer. Unknown counts as light.
 */
export function isGroundLight(header: Element): boolean {
  const width = window.innerWidth;
  const y = width < 1100 ? 32 : 38;
  for (const fraction of [0.5, 0.15, 0.85]) {
    const light = groundAt(Math.round(width * fraction), y, header);
    if (light !== null) return light;
  }
  return true;
}
