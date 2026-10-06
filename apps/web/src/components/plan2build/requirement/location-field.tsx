"use client";

// The plot pin: tap the map, use the device location, or type coordinates. The last two keep the
// question answerable without a pointer and without a map provider. The map itself stays Leaflet;
// everything around it uses the design system.
import type { Question } from "@p2b/contracts";
import { LocateFixedIcon, MapPinIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useRef, useState } from "react";

import { FormFieldset } from "@/components/plan2build/form-field";
import type { MapTiles, Point } from "@/components/plan2build/requirement/plot-map";
import { LoadingState, Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Requirement");
const common = getTranslator("Common");

const PlotMap = dynamic(() => import("@/components/plan2build/requirement/plot-map"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-72 w-full sm:h-96" />
      <LoadingState label={common("loading")} />
    </div>
  ),
});

const round = (value: number) => Math.round(value * 1e6) / 1e6;

export function LocationField({
  question,
  value,
  onChange,
  tiles,
  errors,
}: {
  question: Pick<Question, "key" | "label" | "required">;
  value: Point | null;
  onChange: (point: Point) => void;
  tiles: MapTiles | null;
  errors?: string[];
}) {
  const [locating, setLocating] = useState(false);
  const [geoFailed, setGeoFailed] = useState(false);
  const latInput = useRef<HTMLInputElement>(null);
  const lngInput = useRef<HTMLInputElement>(null);
  const id = `q-${question.key}`;

  const pick = (point: Point) => onChange({ lat: round(point.lat), lng: round(point.lng) });

  function locate() {
    if (!("geolocation" in navigator)) {
      setGeoFailed(true);
      return;
    }
    setLocating(true);
    setGeoFailed(false);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        pick({ lat: position.coords.latitude, lng: position.coords.longitude });
      },
      () => {
        setLocating(false);
        setGeoFailed(true);
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  function applyTyped() {
    const lat = Number(latInput.current?.value);
    const lng = Number(lngInput.current?.value);
    const filled = latInput.current?.value && lngInput.current?.value;
    if (filled && Number.isFinite(lat) && Number.isFinite(lng)) pick({ lat, lng });
  }

  return (
    <FormFieldset
      id={id}
      legend={question.label}
      required={question.required}
      description={tiles ? t("map.hint") : undefined}
      errors={errors}
    >
      {() => (
        <div className="flex flex-col gap-4">
          {tiles ? (
            <PlotMap tiles={tiles} value={value} onPick={pick} label={t("map.label")} />
          ) : (
            <Notice tone="info">{t("map.noMap")}</Notice>
          )}
          <p aria-live="polite" className="flex min-h-6 items-center gap-2 text-sm font-medium">
            {value && (
              <>
                <MapPinIcon aria-hidden="true" className="size-4 text-info" />
                {t("map.pinned", { lat: value.lat.toFixed(5), lng: value.lng.toFixed(5) })}
              </>
            )}
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={locate}
            disabled={locating}
            className="sm:self-start"
          >
            {locating ? <Spinner /> : <LocateFixedIcon aria-hidden="true" />}
            {locating ? t("map.locating") : t("map.useLocation")}
          </Button>
          {geoFailed && (
            <Notice tone="warning" live="assertive">
              {t("map.locationFailed")}
            </Notice>
          )}
          {/* Keyed on the pin so the boxes show it after every change, while staying editable. */}
          <div
            key={value ? `${value.lat},${value.lng}` : "none"}
            className="grid grid-cols-2 items-end gap-3 sm:flex sm:flex-wrap"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor={`${id}-lat`} className="text-sm">
                {t("map.lat")}
              </Label>
              <Input
                id={`${id}-lat`}
                ref={latInput}
                type="number"
                step="any"
                min={-90}
                max={90}
                defaultValue={value?.lat}
                className="tabular-nums sm:w-40"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor={`${id}-lng`} className="text-sm">
                {t("map.lng")}
              </Label>
              <Input
                id={`${id}-lng`}
                ref={lngInput}
                type="number"
                step="any"
                min={-180}
                max={180}
                defaultValue={value?.lng}
                className="tabular-nums sm:w-40"
              />
            </div>
            <Button type="button" variant="outline" onClick={applyTyped} className="col-span-2">
              {t("map.apply")}
            </Button>
          </div>
        </div>
      )}
    </FormFieldset>
  );
}
