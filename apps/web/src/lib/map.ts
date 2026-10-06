// Map tiles for pin pickers: configured per environment (M-01); none means typed coordinates only.
import type { MapTiles } from "@/components/plan2build/requirement/plot-map";

export function mapTiles(): MapTiles | null {
  const url = process.env.P2B_MAP_TILE_URL;
  return url ? { url, attribution: process.env.P2B_MAP_TILE_ATTRIBUTION ?? "" } : null;
}
