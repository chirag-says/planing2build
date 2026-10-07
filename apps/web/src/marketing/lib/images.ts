import type { Photo } from '@/marketing/content/types';

/**
 * Starts loading and decoding a section's lazy images once it is within one and a half
 * viewports, so photos are ready before they scroll in instead of popping in.
 */
export function decodeImagesAhead(section: HTMLElement) {
  const observer = new IntersectionObserver(
    ([entry]) => {
      if (!entry?.isIntersecting) return;
      observer.disconnect();
      section.querySelectorAll('img').forEach((img) => {
        img.loading = 'eager';
        img.decode().catch(() => {});
      });
    },
    { rootMargin: '150% 0px 150% 0px' },
  );
  observer.observe(section);
}

/** Drawn in place of a missing photo: the reference's grey frame-in-frame card. */
export const PHOTO_PLACEHOLDER =
  "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20viewBox%3D'0%200%20400%20500'%20preserveAspectRatio%3D'xMidYMid%20slice'%3E%3Crect%20width%3D'400'%20height%3D'500'%20fill%3D'%23D3D8E2'%2F%3E%3Crect%20x%3D'120'%20y%3D'170'%20width%3D'160'%20height%3D'160'%20rx%3D'8'%20fill%3D'none'%20stroke%3D'%23AEB6C6'%20stroke-width%3D'1.5'%2F%3E%3Crect%20x%3D'100'%20y%3D'150'%20width%3D'200'%20height%3D'200'%20rx%3D'10'%20fill%3D'none'%20stroke%3D'%23C3CAD8'%20stroke-width%3D'1'%20stroke-dasharray%3D'2%206'%2F%3E%3C%2Fsvg%3E";

/** Widths the reference picked a target from before rounding up to a CDN rendition. */
const TARGET_WIDTHS = [160, 320, 480, 800, 1200, 1600];
/** The downscaled renditions Framer's image CDN serves. */
const RENDITIONS = [512, 1024, 2048];

export type ImageSource = { src: string; srcSet?: string; sizes?: string };

/**
 * The width a `sizes` value needs, estimated the way the reference did: from its last (default)
 * entry, twice a px length, or a vw share of a 1600px screen at 1.25x.
 */
function neededWidth(sizes: string | undefined): number {
  const last = sizes?.split(',').pop() ?? '';
  const px = last.match(/(\d+(?:\.\d+)?)px/);
  const vw = last.match(/(\d+(?:\.\d+)?)vw/);
  if (px) return parseFloat(px[1] ?? '0') * 2;
  if (vw) return (parseFloat(vw[1] ?? '0') / 100) * 1600 * 1.25;
  return 1600;
}

/**
 * `src` / `srcSet` / `sizes` for a photo on Framer's image CDN, matching the renditions the
 * reference requested: the needed width rounds up to a target width, then to a rendition.
 * Without `sizes` the full-width rendition is used. Other URLs pass through unchanged; a missing
 * photo shows the placeholder.
 */
export function framerPhoto(photo: Photo | string | null | undefined, sizes?: string): ImageSource {
  const url = typeof photo === 'string' ? photo : (photo?.src ?? '');
  if (!url) return { src: PHOTO_PLACEHOLDER };
  if (!/framerusercontent\.com\/images\//.test(url)) return { src: url };
  const base = url.split('?')[0] ?? url;
  const needed = neededWidth(sizes);
  const target = TARGET_WIDTHS.find((width) => width >= needed) ?? 1600;
  const rendition = RENDITIONS.find((width) => width >= target) ?? 2048;
  return {
    src: `${base}?scale-down-to=${rendition}`,
    srcSet: RENDITIONS.map((width) => `${base}?scale-down-to=${width} ${width}w`).join(', '),
    ...(sizes ? { sizes } : {}),
  };
}
