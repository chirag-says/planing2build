// The stages and the specification lines, created when the project passed Plan2Build's initial
// review. Stages show their status and schedule; planned dates appear only when approved ones
// exist (2.9). Lines appear by group (A, B, C: groupings, never products, PD-09); a line's
// criteria appear only when the API sends them (open point F-09). Structural lines show that an
// engineer's sign-off is still pending (2.4).
import type { components } from "@p2b/contracts";
import { ShieldIcon, TimerIcon } from "lucide-react";

import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

type Workspace = components["schemas"]["WorkspaceOut"];
type Stage = components["schemas"]["WorkspaceStageOut"];

const FLOOR_KEYS = { "-1": "basement", "0": "ground", "1": "first", "2": "second", "3": "third" } as const;

function floorLabel(floor: number | null | undefined): string {
  const t = getTranslator("Workspace");
  if (floor === null || floor === undefined) return "";
  const key = FLOOR_KEYS[String(floor) as keyof typeof FLOOR_KEYS];
  return key ? t(`floors.${key}`) : String(floor);
}

function schedule(stage: Stage): string {
  const t = getTranslator("Workspace");
  if (!stage.planned_start || !stage.planned_end) return t("scheduleTbc");
  return `${formatDate(stage.planned_start)} – ${formatDate(stage.planned_end)}`;
}

export function StagesTable({ workspace }: { workspace: Workspace }) {
  const t = getTranslator("Workspace");
  return (
    <Card size="sm">
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">{t("stage")}</TableHead>
              <TableHead scope="col">{t("status")}</TableHead>
              <TableHead scope="col" className="hidden sm:table-cell">
                {t("schedule")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {workspace.stages.map((stage) => (
              <TableRow key={`${stage.stage_number}:${stage.floor ?? ""}`}>
                <TableCell className="whitespace-normal">
                  <span className="flex flex-col gap-1">
                    <span className="font-medium">
                      {stage.stage_number}. {stage.name}
                    </span>
                    <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      {stage.floor !== null && stage.floor !== undefined && (
                        <span>{floorLabel(stage.floor)}</span>
                      )}
                      {stage.is_gate && (
                        <span className="inline-flex items-center gap-1">
                          <ShieldIcon aria-hidden="true" className="size-3" />
                          {t("gate")}
                        </span>
                      )}
                      <span className="sm:hidden">{schedule(stage)}</span>
                    </span>
                  </span>
                </TableCell>
                <TableCell>
                  <StatusBadge kind="stage" status={stage.state} />
                </TableCell>
                <TableCell className="hidden text-muted-foreground sm:table-cell">
                  {schedule(stage)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export function SpecificationGroups({ workspace }: { workspace: Workspace }) {
  const t = getTranslator("Workspace");
  return (
    <div className="flex flex-col gap-4">
      {!workspace.criteria_visible && <Notice tone="info">{t("criteriaHidden")}</Notice>}
      {workspace.groups.map((group) => (
        <Card key={group.code} size="sm">
          <CardHeader className="border-b">
            <CardTitle className="text-base">
              <h3>{t("group", { code: group.code, name: group.name })}</h3>
            </CardTitle>
            <CardDescription>
              {t("issued", { issued: group.issued })} · {t("count", { count: group.lines.length })}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <ul className="divide-y divide-border">
              {group.lines.map((line) => (
                <li key={line.code} className="flex items-start gap-3 py-2.5 sm:gap-4">
                  <span className="w-10 shrink-0 font-mono text-sm text-muted-foreground tabular-nums">
                    {line.code}
                  </span>
                  {/* Phones: badges under the item; wider screens: badges on the right. */}
                  <span className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-start sm:gap-4">
                    <span className="flex flex-1 flex-col gap-1">
                      <span className="text-sm font-medium">{line.item}</span>
                      {line.performance_specification && (
                        <span className="text-sm text-muted-foreground">
                          {line.performance_specification}
                        </span>
                      )}
                    </span>
                    <span className="flex flex-wrap gap-1 sm:justify-end">
                      {line.is_long_lead && (
                        <Badge variant="warning">
                          <TimerIcon aria-hidden="true" />
                          {t("longLead")}
                        </Badge>
                      )}
                      {line.is_structural && (
                        <Badge variant="neutral">
                          <ShieldIcon aria-hidden="true" />
                          {t("structural")}
                        </Badge>
                      )}
                      {line.engineer_signoff === "PENDING" && (
                        <Badge variant="neutral">{t("signoffPending")}</Badge>
                      )}
                      <StatusBadge kind="line" status={line.state} />
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
