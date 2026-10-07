// The figures of an indicative estimate, shared by the public estimator and a project's estimate
// (PD-04: an estimate is never a quote and never the package fee). Demonstration figures get a
// dashed, warning-marked card, a "Demo data" badge and a warning above the numbers, so they never
// look like Plan2Build pricing.
import { cn } from "cn";
import { FlaskConicalIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Notice } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatInr } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

export type EstimateFiguresData = {
  total_low: string;
  total_high: string;
  per_sqft_low: string;
  per_sqft_high: string;
  duration_months: number;
  stages: { stage_number: number; stage_name?: string | null; share_pct: string; amount: string }[];
  rate_card: { is_demo: boolean };
};

export function EstimateFigures({
  figures,
  title,
  level = 2,
  description,
  footer,
}: {
  figures: EstimateFiguresData;
  title: string;
  level?: 2 | 3;
  description?: ReactNode;
  footer?: ReactNode;
}) {
  const t = getTranslator("Estimate");
  const demo = figures.rate_card.is_demo;
  const Heading = level === 2 ? "h2" : "h3";
  const SubHeading = level === 2 ? "h3" : "h4";
  return (
    <Card className={cn(demo && "border-2 border-dashed border-warning ring-0")}>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-lg">
            <Heading>{title}</Heading>
          </CardTitle>
          {demo && (
            <Badge variant="warning">
              <FlaskConicalIcon aria-hidden="true" />
              {t("demoBadge")}
            </Badge>
          )}
        </div>
        {description && <div className="text-sm text-muted-foreground">{description}</div>}
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {demo && (
          <Notice tone="warning" title={t("demoTitle")}>
            {t("demoBanner")}
          </Notice>
        )}
        <div className="flex flex-col gap-1">
          <p className="font-heading text-4xl leading-none tabular-nums sm:text-5xl">
            {formatInr(figures.total_low)} to {formatInr(figures.total_high)}
          </p>
          <p className="text-sm text-muted-foreground tabular-nums">
            {t("perSqft", {
              low: formatInr(figures.per_sqft_low),
              high: formatInr(figures.per_sqft_high),
            })}
          </p>
          <p className="text-sm text-muted-foreground">
            {t("duration", { months: figures.duration_months })}
          </p>
        </div>
        <div className="flex flex-col gap-3">
          <SubHeading className="font-heading text-lg font-semibold">{t("stages")}</SubHeading>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">{t("stage")}</TableHead>
                <TableHead scope="col" className="text-right">
                  {t("share")}
                </TableHead>
                <TableHead scope="col" className="text-right">
                  {t("amount")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {figures.stages.map((stage) => (
                <TableRow key={stage.stage_number}>
                  <TableCell className="whitespace-normal">
                    {stage.stage_name ?? t("stageFallback", { number: stage.stage_number })}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {Number(stage.share_pct)}%
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatInr(stage.amount)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
      {footer && <CardFooter>{footer}</CardFooter>}
    </Card>
  );
}
