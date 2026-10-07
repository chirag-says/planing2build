"use client";

// Generate My Design and the project's gallery (Slice 3.1; PD-05, PD-22; F-08). The server owns
// the quota, the provider and the prompt: this component sends only the view and shows what the
// API says. While a design is waiting or generating it polls the list; each request keeps one
// idempotency key until it succeeds, so a double click or a retry never asks twice.
import type { components } from "@p2b/contracts";
import { CoinsIcon, ImageIcon, SparklesIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { FormFieldset } from "@/components/plan2build/form-field";
import { ChoiceGroup } from "@/components/plan2build/form-field";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

type DesignList = components["schemas"]["DesignListOut"];
type Design = components["schemas"]["DesignOut"];
type View = Design["view"];

const t = getTranslator("Designs");
const billing = getTranslator("Billing");
const POLL_MS = 2500;

function inFlight(list: DesignList): boolean {
  return list.items.some((item) => item.state === "QUEUED" || item.state === "RUNNING");
}

export function IllustrativeBadge() {
  return (
    <Badge variant="warning" className="shadow-sm">
      <ImageIcon aria-hidden="true" />
      {t("illustrative")}
    </Badge>
  );
}

/** The image with its "Illustrative" badge; a link to the design when `href` is given. */
/**
 * One design. `index` staggers the website's image unmask (kit .gd-um): the first row opens
 * from the bottom and settles from 1.28x; later images only fade in, so the gallery has one
 * reveal, not one per card.
 */
export function DesignThumbnail({ design, href, index = 0 }: { design: Design; href?: string; index?: number }) {
  const viewLabel = t(`viewShort.${design.view}`);
  const frame =
    `group relative block overflow-hidden rounded-md border border-foreground/20 bg-muted outline-none focus-visible:ring-3 focus-visible:ring-ring/50 ${index < 3 ? "p2b-unmask" : "p2b-fade"}`;
  const content = (
    <>
      {design.image_url ? (
        // Signed, short-lived links to private storage: no image optimiser in between.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={design.image_url}
          alt={t("imageAlt", { view: viewLabel, number: design.sequence })}
          className="p2b-unmask-img aspect-[4/3] w-full object-cover"
          loading="lazy"
        />
      ) : (
        <div className="flex aspect-[4/3] w-full items-center justify-center text-muted-foreground">
          {design.state === "FAILED" ? (
            <ImageIcon aria-hidden="true" className="size-8" />
          ) : (
            <span aria-hidden="true" className="p2b-hazard-run h-2 w-16" />
          )}
          <span className="sr-only">{t("designNumber", { number: design.sequence })}</span>
        </div>
      )}
      {design.image_url && (
        <span className="absolute top-2 left-2">
          <IllustrativeBadge />
        </span>
      )}
    </>
  );
  const order = { "--i": Math.min(index, 2) } as React.CSSProperties;
  return href ? (
    <Link href={href} className={frame} style={order}>
      {content}
    </Link>
  ) : (
    <div className={frame} style={order}>
      {content}
    </div>
  );
}

function DesignCard({
  design,
  projectId,
  onRetry,
  canRetry,
}: {
  design: Design;
  projectId: string;
  onRetry: (view: View) => void;
  canRetry: boolean;
}) {
  const href = `/projects/${projectId}/designs/${design.design_id}`;
  return (
    <li>
      <Card size="sm" className="h-full gap-3 py-3">
        <CardContent className="flex flex-col gap-3 px-3">
          <DesignThumbnail design={design} href={href} index={design.sequence - 1} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link href={href} className="text-sm font-medium underline-offset-4 hover:underline">
              {t("designNumber", { number: design.sequence })} · {t(`viewShort.${design.view}`)}
            </Link>
            <StatusBadge kind="design" status={design.state} />
          </div>
          <p className="text-xs text-muted-foreground">
            {t("requested", { date: formatDate(design.created_at) })}
          </p>
          {design.reference && <Badge variant="info">{t("referenceBadge")}</Badge>}
          {design.state === "FAILED" && (
            <div className="flex flex-col gap-2 text-sm">
              <p>
                {t(
                  `failure.${
                    design.failure_reason === "PROVIDER_TIMEOUT" ||
                    design.failure_reason === "PROVIDER_UNAVAILABLE" ||
                    design.failure_reason === "STALE"
                      ? design.failure_reason
                      : "default"
                  }`,
                )}{" "}
                {t("failedNotCounted")}
              </p>
              {canRetry && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="self-start"
                  onClick={() => onRetry(design.view)}
                >
                  {t("tryAgain")}
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </li>
  );
}

export function DesignGallery({ projectId, initial }: { projectId: string; initial: DesignList }) {
  const [list, setList] = useState(initial);
  const [view, setView] = useState<View>("EXTERIOR");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<{ view: View; paid: boolean; key: string } | null>(null);
  const { quota } = list;

  const reload = useCallback(async () => {
    const { data } = await browserApi.GET("/api/v1/projects/{project_id}/designs", {
      params: { path: { project_id: projectId } },
    });
    if (data) setList(data);
  }, [projectId]);

  useEffect(() => {
    if (!inFlight(list)) return;
    const timer = setTimeout(() => void reload(), POLL_MS);
    return () => clearTimeout(timer);
  }, [list, reload]);

  /** `useCredit` only from the family's explicit "Use 1 AI credit" choice; never otherwise. */
  async function generate(chosen: View, useCredit = false) {
    if (!key.current || key.current.view !== chosen || key.current.paid !== useCredit) {
      key.current = { view: chosen, paid: useCredit, key: crypto.randomUUID() };
    }
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await browserApi.POST(
        "/api/v1/projects/{project_id}/designs",
        {
          params: {
            path: { project_id: projectId },
            header: { "Idempotency-Key": key.current.key },
          },
          body: { view: chosen, use_credit: useCredit },
        },
      );
      if (data) {
        key.current = null;
        await reload();
        return;
      }
      const code = errorCode(failure);
      if (code === "QUOTA_EXHAUSTED" || code === "STATE_CONFLICT" || code === "NO_CREDIT") {
        key.current = null;
        await reload(); // the server's quota explains why
      } else {
        setError(
          code === "RATE_LIMITED" || code === "PROVIDER_UNAVAILABLE"
            ? t(`errors.${code}`)
            : t("errors.default"),
        );
      }
    } catch {
      setError(t("errors.default"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card size="sm">
        <CardContent className="flex flex-col gap-4">
          <FormFieldset id="design-view" legend={t("viewLabel")} required>
            {({ legendId }) => (
              <ChoiceGroup
                id="design-view"
                labelledBy={legendId}
                value={view}
                onValueChange={(value) => setView(value as View)}
                options={(["EXTERIOR", "INTERIOR"] as const).map((value) => ({
                  value,
                  label: t(`views.${value}`),
                }))}
              />
            )}
          </FormFieldset>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm font-medium" data-testid="free-remaining">
              {t("remaining", { remaining: quota.free_remaining, total: quota.free_total })}
            </p>
            <Button
              type="button"
              size="lg"
              onClick={() => void generate(view)}
              disabled={busy || !quota.can_generate}
            >
              {busy ? <Spinner /> : <SparklesIcon aria-hidden="true" />}
              {busy ? t("requesting") : t("generate")}
            </Button>
          </div>
          <div aria-live="polite" className="flex flex-col gap-3">
            {quota.in_progress > 0 && (
              <p className="text-sm text-muted-foreground">
                {t("inProgress", { count: quota.in_progress })}
              </p>
            )}
            {quota.block && <Notice tone="info">{t(`blocks.${quota.block}`)}</Notice>}
            {quota.block === "FREE_QUOTA_USED" && (
              <div className="flex flex-col gap-3 rounded-md border border-border p-3">
                <p className="text-sm font-medium" data-testid="credit-balance">
                  {billing("account.balance", { count: quota.credit_balance })}
                </p>
                {quota.paid_block && quota.paid_block !== "FREE_QUOTA_USED" ? (
                  <p className="text-sm text-muted-foreground">{t(`blocks.${quota.paid_block}`)}</p>
                ) : quota.can_use_credit ? (
                  <>
                    <p className="text-sm text-muted-foreground">{t("paidNote")}</p>
                    <Button
                      type="button"
                      variant="outline"
                      className="sm:self-start"
                      onClick={() => void generate(view, true)}
                      disabled={busy}
                    >
                      {busy ? <Spinner /> : <CoinsIcon aria-hidden="true" />}
                      {t("useCredit")}
                    </Button>
                  </>
                ) : (
                  <Button asChild variant="outline" className="sm:self-start">
                    <Link href={`/account/ai-credits/buy?project=${projectId}`}>
                      <CoinsIcon aria-hidden="true" />
                      {billing("account.buyCredit")}
                    </Link>
                  </Button>
                )}
              </div>
            )}
          </div>
          {error && (
            <Notice tone="error" live="assertive">
              {error}
            </Notice>
          )}
        </CardContent>
      </Card>

      {list.items.length === 0 ? (
        <EmptyState
          icon={ImageIcon}
          title={t("empty")}
          description={t("emptyBody", { total: quota.free_total })}
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label={t("title")}>
          {list.items.map((design) => (
            <DesignCard
              key={design.design_id}
              design={design}
              projectId={projectId}
              canRetry={quota.can_generate && !busy}
              onRetry={(retryView) => void generate(retryView)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
