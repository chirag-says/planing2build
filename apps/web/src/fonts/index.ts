// Brand typefaces (UI_DESIGN_SYSTEM.md 3.2), self-hosted through next/font so they are served
// from /_next/static and never from a font service. Each face has a latin file and a latin-ext
// file: latin covers the copy, latin-ext carries the rupee sign. Each variable holds only its
// family (no generated fallback), and globals.css stacks latin, then ext, then system fonts, so
// a glyph latin lacks comes from the ext face and the ext file is fetched only when needed.
import localFont from "next/font/local";

const display = localFont({
  src: "./big-shoulders-display-500-900-latin.woff2",
  weight: "500 900",
  display: "swap",
  variable: "--p2b-display",
  adjustFontFallback: false,
});

const displayExt = localFont({
  src: "./big-shoulders-display-500-900-latin-ext.woff2",
  weight: "500 900",
  display: "swap",
  preload: false,
  adjustFontFallback: false,
  variable: "--p2b-display-ext",
});

const body = localFont({
  src: [
    { path: "./barlow-400-latin.woff2", weight: "400" },
    { path: "./barlow-500-latin.woff2", weight: "500" },
    { path: "./barlow-600-latin.woff2", weight: "600" },
    { path: "./barlow-700-latin.woff2", weight: "700" },
  ],
  display: "swap",
  variable: "--p2b-body",
  adjustFontFallback: false,
});

const bodyExt = localFont({
  src: [
    { path: "./barlow-400-latin-ext.woff2", weight: "400" },
    { path: "./barlow-500-latin-ext.woff2", weight: "500" },
    { path: "./barlow-600-latin-ext.woff2", weight: "600" },
    { path: "./barlow-700-latin-ext.woff2", weight: "700" },
  ],
  display: "swap",
  preload: false,
  adjustFontFallback: false,
  variable: "--p2b-body-ext",
});

const mono = localFont({
  src: "./reddit-mono-400-600-latin.woff2",
  weight: "400 600",
  display: "swap",
  variable: "--p2b-mono",
  adjustFontFallback: false,
});

const monoExt = localFont({
  src: "./reddit-mono-400-600-latin-ext.woff2",
  weight: "400 600",
  display: "swap",
  preload: false,
  adjustFontFallback: false,
  variable: "--p2b-mono-ext",
});

/** Class names that define the font variables; set on <html>. */
export const fontVariables = [display, displayExt, body, bodyExt, mono, monoExt].map((font) => font.variable).join(" ");
