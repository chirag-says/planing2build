// The one visual vocabulary for business states (UI_DESIGN_SYSTEM.md section 9). Every state has a
// tone, an icon and a label, so it reads without colour. Screens never pick their own colours.
import type {
  BuildPlanState,
  ConnectionState,
  DesignGenerationState,
  DrawingSetState,
  DueState,
  EngagementState,
  FileState,
  ListingState,
  NeedState,
  OrderState,
  PackageState,
  PlanGenerationState,
  ProjectStatus,
  RefundRequestState,
  ReviewFlag,
  SpecLineState,
  StageState,
} from "@p2b/contracts";
import {
  ArchiveIcon,
  BanIcon,
  BadgeCheckIcon,
  CircleDollarSignIcon,
  ClockIcon,
  RotateCcwIcon,
  CircleAlertIcon,
  CircleCheckIcon,
  CircleDashedIcon,
  CirclePauseIcon,
  CircleXIcon,
  ClipboardCheckIcon,
  FileTextIcon,
  ListChecksIcon,
  PackageCheckIcon,
  ShieldCheckIcon,
  HammerIcon,
  KeyRoundIcon,
  PencilLineIcon,
  SearchIcon,
  SendIcon,
  ShieldAlertIcon,
  Trash2Icon,
  TriangleAlertIcon,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { getTranslator } from "@/lib/i18n";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

interface Look {
  tone: Tone;
  icon: LucideIcon | "spinner";
}

const PROJECT: Record<ProjectStatus, Look> = {
  DRAFT: { tone: "neutral", icon: PencilLineIcon },
  SUBMITTED: { tone: "info", icon: SendIcon },
  NEEDS_INFO: { tone: "warning", icon: CircleAlertIcon },
  ACCEPTED: { tone: "success", icon: CircleCheckIcon },
  PLANNING: { tone: "info", icon: CircleDashedIcon },
  PLAN_ISSUED: { tone: "info", icon: ClipboardCheckIcon },
  SOURCING: { tone: "info", icon: SearchIcon },
  CONTRACTED: { tone: "info", icon: CircleCheckIcon },
  BUILDING: { tone: "info", icon: HammerIcon },
  HANDOVER_PENDING: { tone: "warning", icon: KeyRoundIcon },
  COMPLETED: { tone: "success", icon: CircleCheckIcon },
  ARCHIVED: { tone: "neutral", icon: ArchiveIcon },
  ON_HOLD: { tone: "warning", icon: CirclePauseIcon },
  CANCELLED: { tone: "neutral", icon: BanIcon },
};

const FILE: Record<FileState, Look> = {
  PENDING_UPLOAD: { tone: "neutral", icon: CircleDashedIcon },
  UPLOADED: { tone: "info", icon: "spinner" },
  SCANNING: { tone: "info", icon: "spinner" },
  AVAILABLE: { tone: "success", icon: CircleCheckIcon },
  QUARANTINED: { tone: "danger", icon: ShieldAlertIcon },
  FAILED: { tone: "danger", icon: CircleXIcon },
  DELETED: { tone: "neutral", icon: Trash2Icon },
};

const STAGE: Record<StageState, Look> = {
  NOT_STARTED: { tone: "neutral", icon: CircleDashedIcon },
  IN_PROGRESS: { tone: "info", icon: HammerIcon },
  COMPLETION_REQUESTED: { tone: "warning", icon: ClipboardCheckIcon },
  COMPLETED: { tone: "success", icon: CircleCheckIcon },
  BLOCKED: { tone: "danger", icon: BanIcon },
  ON_HOLD: { tone: "warning", icon: CirclePauseIcon },
};

const LINE: Record<SpecLineState, Look> = {
  SPECIFIED: { tone: "neutral", icon: FileTextIcon },
  OPTIONS_ISSUED: { tone: "info", icon: ListChecksIcon },
  CHOSEN: { tone: "info", icon: CircleCheckIcon },
  PURCHASED: { tone: "info", icon: PackageCheckIcon },
  INSTALLED: { tone: "info", icon: HammerIcon },
  VERIFIED: { tone: "success", icon: ShieldCheckIcon },
};

const DESIGN: Record<DesignGenerationState, Look> = {
  QUEUED: { tone: "neutral", icon: CircleDashedIcon },
  RUNNING: { tone: "info", icon: "spinner" },
  SUCCEEDED: { tone: "success", icon: CircleCheckIcon },
  FAILED: { tone: "danger", icon: CircleXIcon },
};

// Concept floor plans (Checkpoint 1): INFEASIBLE is an answer, not a fault, so it warns.
const PLAN: Record<PlanGenerationState, Look> = {
  QUEUED: { tone: "neutral", icon: CircleDashedIcon },
  RUNNING: { tone: "info", icon: "spinner" },
  VALID: { tone: "success", icon: CircleCheckIcon },
  INFEASIBLE: { tone: "warning", icon: TriangleAlertIcon },
  FAILED: { tone: "danger", icon: CircleXIcon },
};

const LISTING: Record<ListingState, Look> = {
  DRAFT: { tone: "neutral", icon: PencilLineIcon },
  PENDING_REVIEW: { tone: "info", icon: SearchIcon },
  CHANGES_REQUESTED: { tone: "warning", icon: CircleAlertIcon },
  LISTED: { tone: "success", icon: ShieldCheckIcon },
  REJECTED: { tone: "neutral", icon: BanIcon },
  SUSPENDED: { tone: "warning", icon: CirclePauseIcon },
};

const ORDER: Record<OrderState, Look> = {
  AWAITING_PAYMENT: { tone: "warning", icon: ClockIcon },
  PART_PAID: { tone: "info", icon: CircleDollarSignIcon },
  PAID: { tone: "success", icon: CircleCheckIcon },
  CANCELLED: { tone: "neutral", icon: BanIcon },
  PARTLY_REFUNDED: { tone: "info", icon: RotateCcwIcon },
  REFUNDED: { tone: "neutral", icon: RotateCcwIcon },
};

const PACKAGE: Record<PackageState, Look> = {
  NOT_ACTIVE: { tone: "neutral", icon: CircleDashedIcon },
  ACTIVE: { tone: "success", icon: BadgeCheckIcon },
  CANCELLED: { tone: "neutral", icon: BanIcon },
  REFUNDED: { tone: "neutral", icon: RotateCcwIcon },
};

const DUE: Record<DueState, Look> = {
  DUE: { tone: "warning", icon: ClockIcon },
  PAID: { tone: "success", icon: CircleCheckIcon },
  CANCELLED: { tone: "neutral", icon: BanIcon },
};

const REFUND: Record<RefundRequestState, Look> = {
  REQUESTED: { tone: "warning", icon: ClockIcon },
  APPROVED: { tone: "info", icon: "spinner" },
  DECLINED: { tone: "neutral", icon: BanIcon },
  REFUNDED: { tone: "success", icon: RotateCcwIcon },
  FAILED: { tone: "danger", icon: CircleXIcon },
};

const CONNECTION: Record<ConnectionState, Look> = {
  SENT: { tone: "info", icon: ClockIcon },
  ACCEPTED: { tone: "success", icon: CircleCheckIcon },
  DECLINED: { tone: "neutral", icon: CircleXIcon },
  EXPIRED: { tone: "neutral", icon: CircleDashedIcon },
  WITHDRAWN: { tone: "neutral", icon: BanIcon },
};

const ENGAGEMENT: Record<EngagementState, Look> = {
  ACTIVE: { tone: "success", icon: HammerIcon },
  ENDED: { tone: "neutral", icon: ArchiveIcon },
};

const NEED: Record<NeedState, Look> = {
  UNDECIDED: { tone: "neutral", icon: CircleDashedIcon },
  NEEDED: { tone: "info", icon: CircleCheckIcon },
  NOT_NEEDED: { tone: "neutral", icon: BanIcon },
};

const BUILD_PLAN: Record<BuildPlanState, Look> = {
  DRAFT: { tone: "neutral", icon: PencilLineIcon },
  IN_REVIEW: { tone: "info", icon: SearchIcon },
  ISSUED: { tone: "info", icon: SendIcon },
  ACCEPTED: { tone: "success", icon: BadgeCheckIcon },
  CHANGES_REQUESTED: { tone: "warning", icon: CircleAlertIcon },
  SUPERSEDED: { tone: "neutral", icon: ArchiveIcon },
  WITHDRAWN: { tone: "neutral", icon: BanIcon },
};

const DRAWING_SET: Record<DrawingSetState, Look> = {
  DRAFT: { tone: "neutral", icon: PencilLineIcon },
  SUBMITTED: { tone: "warning", icon: ClockIcon },
  IN_CHECK: { tone: "info", icon: SearchIcon },
  CHANGES_REQUESTED: { tone: "warning", icon: CircleAlertIcon },
  APPROVED: { tone: "success", icon: ShieldCheckIcon },
  REJECTED: { tone: "neutral", icon: CircleXIcon },
  SUPERSEDED: { tone: "neutral", icon: ArchiveIcon },
};

const VARIANT = {
  neutral: "neutral",
  info: "info",
  success: "success",
  warning: "warning",
  danger: "destructive",
} as const;

type Props =
  | { kind: "project"; status: ProjectStatus; withLabel?: boolean }
  | { kind: "file"; status: FileState; withLabel?: boolean }
  | { kind: "stage"; status: StageState; withLabel?: boolean }
  | { kind: "line"; status: SpecLineState; withLabel?: boolean }
  | { kind: "design"; status: DesignGenerationState; withLabel?: boolean }
  | { kind: "listing"; status: ListingState; withLabel?: boolean }
  | { kind: "order"; status: OrderState; withLabel?: boolean }
  | { kind: "package"; status: PackageState; withLabel?: boolean }
  | { kind: "due"; status: DueState; withLabel?: boolean }
  | { kind: "refund"; status: RefundRequestState; withLabel?: boolean }
  | { kind: "connection"; status: ConnectionState; withLabel?: boolean }
  | { kind: "engagement"; status: EngagementState; withLabel?: boolean }
  | { kind: "need"; status: NeedState; withLabel?: boolean }
  | { kind: "buildPlan"; status: BuildPlanState; withLabel?: boolean }
  | { kind: "drawingSet"; status: DrawingSetState; withLabel?: boolean }
  | { kind: "plan"; status: PlanGenerationState; withLabel?: boolean };

/** `withLabel` prefixes a visually hidden "Status:" for places where the badge stands alone. */
export function StatusBadge(props: Props) {
  const t = getTranslator("Status");
  const [look, label] =
    props.kind === "project"
      ? [PROJECT[props.status], t(`project.${props.status}`)]
      : props.kind === "file"
        ? [FILE[props.status], t(`file.${props.status}`)]
        : props.kind === "stage"
          ? [STAGE[props.status], t(`stage.${props.status}`)]
          : props.kind === "line"
            ? [LINE[props.status], t(`line.${props.status}`)]
            : props.kind === "design"
              ? [DESIGN[props.status], t(`design.${props.status}`)]
              : props.kind === "listing"
                ? [LISTING[props.status], t(`listing.${props.status}`)]
                : props.kind === "order"
                  ? [ORDER[props.status], t(`order.${props.status}`)]
                  : props.kind === "package"
                    ? [PACKAGE[props.status], t(`package.${props.status}`)]
                    : props.kind === "due"
                      ? [DUE[props.status], t(`due.${props.status}`)]
                      : props.kind === "refund"
                        ? [REFUND[props.status], t(`refund.${props.status}`)]
                        : props.kind === "connection"
                          ? [CONNECTION[props.status], t(`connection.${props.status}`)]
                          : props.kind === "engagement"
                            ? [ENGAGEMENT[props.status], t(`engagement.${props.status}`)]
                            : props.kind === "need"
                              ? [NEED[props.status], t(`need.${props.status}`)]
                              : props.kind === "buildPlan"
                                ? [BUILD_PLAN[props.status], t(`buildPlan.${props.status}`)]
                                : props.kind === "drawingSet"
                                  ? [DRAWING_SET[props.status], t(`drawingSet.${props.status}`)]
                                  : [PLAN[props.status], t(`plan.${props.status}`)];
  const Icon = look.icon;
  return (
    <Badge variant={VARIANT[look.tone]} data-status={props.status}>
      {Icon === "spinner" ? <Spinner /> : <Icon aria-hidden="true" />}
      {props.withLabel && <span className="sr-only">{t("label")}: </span>}
      {label}
    </Badge>
  );
}

/** A review flag (operations only, never shown to the homeowner). Warning tone, icon and words. */
export function ReviewFlagBadge({ flag }: { flag: ReviewFlag }) {
  const t = getTranslator("Ops");
  return (
    <Badge variant="warning" data-flag={flag}>
      <TriangleAlertIcon aria-hidden="true" />
      {t(`flags.${flag}`)}
    </Badge>
  );
}
