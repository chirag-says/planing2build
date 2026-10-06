"use client";

// Leaflet map for the plot pin (R-3; IHB_FLOW 12.2). Loaded only in the browser. The tile
// provider is configuration (P2B_MAP_TILE_URL): the public OpenStreetMap tiles are for development
// only, and the production provider is open (AQ-19). A circle marker avoids Leaflet's image icons.
import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useRef, useState } from "react";

export interface MapTiles {
  url: string;
  attribution: string;
}

export interface Point {
  lat: number;
  lng: number;
}

// Where the map opens before a pin exists: central Raipur, the only city in version 1.
const RAIPUR: L.LatLngTuple = [21.2514, 81.6296];

export default function PlotMap({
  tiles,
  value,
  onPick,
  label,
}: {
  tiles: MapTiles;
  value: Point | null;
  onPick: (point: Point) => void;
  label: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.CircleMarker | null>(null);
  const pick = useRef(onPick);
  const [initial] = useState(value);

  useEffect(() => {
    pick.current = onPick;
  }, [onPick]);

  useEffect(() => {
    if (!container.current) return;
    const instance = L.map(container.current, {
      center: initial ? [initial.lat, initial.lng] : RAIPUR,
      zoom: initial ? 17 : 12,
    });
    L.tileLayer(tiles.url, { attribution: tiles.attribution, maxZoom: 19 }).addTo(instance);
    instance.on("click", (event: L.LeafletMouseEvent) =>
      pick.current({ lat: event.latlng.lat, lng: event.latlng.lng }),
    );
    map.current = instance;
    return () => {
      instance.remove();
      map.current = null;
      marker.current = null;
    };
  }, [tiles.url, tiles.attribution, initial]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    if (!value) {
      marker.current?.remove();
      marker.current = null;
      return;
    }
    const point: L.LatLngTuple = [value.lat, value.lng];
    if (marker.current) {
      marker.current.setLatLng(point);
    } else {
      // Colour from the tokens through the p2b-pin class (globals.css), not a literal here.
      marker.current = L.circleMarker(point, {
        radius: 9,
        weight: 3,
        fillOpacity: 0.5,
        className: "p2b-pin",
      }).addTo(instance);
    }
    if (!instance.getBounds().contains(point)) instance.setView(point, 17);
  }, [value]);

  return (
    <div
      ref={container}
      role="region"
      aria-label={label}
      className="z-0 h-72 w-full rounded-md border border-input sm:h-96"
    />
  );
}
