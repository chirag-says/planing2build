"use client";

// A concept floor plan for viewing only (operations, Checkpoint 3 read path): the same PlanDrawing
// the owner's workspace draws, with zoom, pan, units and the validator's checks, and no selection
// or editing of any kind. The interactive PlanCanvas needs the owner's editor state (`editing`),
// which the operations detail does not carry, so this view drives PlanDrawing directly.
import { MaximizeIcon, ZoomInIcon, ZoomOutIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from "react";

import { PlanDrawing } from "@/components/plan2build/plan/plan-drawing";
import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";
import type { Units } from "@/lib/plan/editor";
import { flaggedEntities } from "@/lib/plan/editor";
import { issueText } from "@/lib/plan/messages";
import { renderModel } from "@/lib/plan/render-model";
import type { HousePlan, PlanGeometry, ValidationIssue, ValidationReport } from "@/lib/plan/types";
import { fitViewBox, panViewBox, pxPerMm, zoomViewBox, type Point, type ScreenRect, type ViewBox } from "@/lib/plan/viewport";

const t = getTranslator("Plan");
const MARGIN_MM = 2500; // as the workspace: room for the dimensions and the road caption

export function PlanViewer({
  document: doc,
  geometry,
  validation,
}: {
  document: HousePlan;
  geometry: PlanGeometry;
  validation: ValidationReport | null;
}) {
  const model = useMemo(() => renderModel(geometry), [geometry]);
  const box = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState<ScreenRect>({ left: 0, top: 0, width: 800, height: 600 });
  const [vb, setVb] = useState<ViewBox>(() => fitViewBox(geometry.bounds, 4 / 3, MARGIN_MM));
  const [units, setUnits] = useState<Units>("m");
  const pan = useRef<{ start: Point; vb: ViewBox } | null>(null);
  const fitted = useRef(false);
  const issues: ValidationIssue[] = useMemo(
    () => [...(validation?.errors ?? []), ...(validation?.warnings ?? [])],
    [validation],
  );
  const flagged = useMemo(() => flaggedEntities(issues), [issues]);

  const fit = useCallback(() => {
    const r = box.current?.getBoundingClientRect();
    const aspect = r && r.height > 0 ? r.width / r.height : 4 / 3;
    setVb(fitViewBox(geometry.bounds, aspect, MARGIN_MM));
  }, [geometry.bounds]);

  const zoom = (factor: number) => setVb((v) => zoomViewBox(v, factor, { x: v.x + v.w / 2, y: v.y + v.h / 2 }));

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      setRect({ left: r.left, top: r.top, width: r.width, height: r.height });
      if (!fitted.current && r.width > 0 && r.height > 0) {
        fitted.current = true;
        setVb(fitViewBox(geometry.bounds, r.width / r.height, MARGIN_MM));
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [geometry.bounds]);

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    pan.current = { start: { x: e.clientX, y: e.clientY }, vb };
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const g = pan.current;
    if (!g) return;
    const s = pxPerMm(rect, g.vb);
    setVb(panViewBox(g.vb, -(e.clientX - g.start.x) / s, -(e.clientY - g.start.y) / s));
  }

  return (
    <div className="flex flex-col gap-4" data-plan-viewer="">
      <div role="toolbar" aria-label={t("toolbar")} className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="icon" onClick={() => zoom(1.25)} aria-label={t("zoomIn")}>
          <ZoomInIcon aria-hidden="true" />
        </Button>
        <Button variant="outline" size="icon" onClick={() => zoom(0.8)} aria-label={t("zoomOut")}>
          <ZoomOutIcon aria-hidden="true" />
        </Button>
        <Button variant="outline" size="icon" onClick={fit} aria-label={t("fit")}>
          <MaximizeIcon aria-hidden="true" />
        </Button>
        <div role="group" aria-label={t("unitsLabel")} className="flex gap-1">
          {(["m", "ft"] as const).map((u) => (
            <Button
              key={u}
              variant={units === u ? "secondary" : "ghost"}
              aria-pressed={units === u}
              onClick={() => setUnits(u)}
            >
              {u === "m" ? t("unitMetres") : t("unitFeet")}
            </Button>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div
          ref={box}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={() => (pan.current = null)}
          onPointerCancel={() => (pan.current = null)}
          className="h-[60vh] min-h-80 touch-none overflow-hidden rounded-lg border bg-background lg:h-[72vh]"
        >
          <PlanDrawing
            model={model}
            viewBox={vb}
            pxPerMm={pxPerMm(rect, vb)}
            units={units}
            flagged={flagged}
            titleId="ops-plan-title"
            descId="ops-plan-desc"
          />
        </div>
        <section aria-labelledby="ops-plan-checks" className="flex flex-col gap-2 rounded-lg border p-3">
          <h3 id="ops-plan-checks" className="text-sm font-medium">
            {t("issues")}
          </h3>
          {issues.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("issuesNone")}</p>
          ) : (
            <ul className="list-disc pl-5 text-sm">
              {issues.map((issue, i) => (
                <li key={`${issue.code}-${i}`}>{issueText(issue, doc, geometry, units)}</li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
