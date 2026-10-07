// Lengths and areas for display, from canonical millimetres (never measured from the SVG). The
// unit strings live in messages/en.json (namespace Plan.units).
import { getTranslator } from "@/lib/i18n";

import type { Units } from "./editor";

const t = getTranslator("Plan");

export function formatLength(mm: number, units: Units): string {
  if (units === "ft") {
    const inches = Math.round(mm / 25.4);
    return t("units.feetInches", { feet: Math.floor(inches / 12), inches: inches % 12 });
  }
  return t("units.metres", { value: (mm / 1000).toFixed(2) });
}

export function formatDims(w: number, d: number, units: Units): string {
  return t("units.dims", { w: formatLength(w, units), d: formatLength(d, units) });
}

export function formatArea(mm2: number, units: Units): string {
  if (units === "ft") return t("units.squareFeet", { value: Math.round(mm2 / 92_903.04) });
  return t("units.squareMetres", { value: (mm2 / 1_000_000).toFixed(1) });
}
