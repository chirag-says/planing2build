/**
 * One requestAnimationFrame loop shared by every animated part of the page.
 *
 * Each frame runs three phases in order:
 *   pre   – advance smooth scrolling (Lenis), so positions are current
 *   read  – measure layout (getBoundingClientRect, innerHeight)
 *   write – apply styles
 * Keeping all reads before all writes means one layout per frame no matter how many sections
 * are listening. The loop stops itself when nothing is subscribed.
 */
export type FrameCallback = (time: number) => void;

type Phases = {
  write: FrameCallback;
  read?: FrameCallback;
  pre?: FrameCallback;
};

const pre = new Set<FrameCallback>();
const reads = new Set<FrameCallback>();
const writes = new Set<FrameCallback>();
let frame = 0;

function tick(time: number) {
  pre.forEach((fn) => fn(time));
  reads.forEach((fn) => fn(time));
  writes.forEach((fn) => fn(time));
  frame = pre.size || reads.size || writes.size ? requestAnimationFrame(tick) : 0;
}

/** Runs the callbacks every frame until the returned function is called. */
export function onFrame({ write, read, pre: before }: Phases): () => void {
  if (typeof window === 'undefined') return () => {};
  writes.add(write);
  if (read) reads.add(read);
  if (before) pre.add(before);
  if (!frame) frame = requestAnimationFrame(tick);
  return () => {
    writes.delete(write);
    if (read) reads.delete(read);
    if (before) pre.delete(before);
  };
}

export const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
