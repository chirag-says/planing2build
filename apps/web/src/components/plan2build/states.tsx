// Empty, error, loading and result states, so every screen shows them the same way
// (UI_DESIGN_SYSTEM.md section 8).
import { CircleAlertIcon, CircleCheckIcon, InfoIcon, TriangleAlertIcon, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Empty className="border border-dashed border-border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon aria-hidden="true" />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        {description && <EmptyDescription>{description}</EmptyDescription>}
      </EmptyHeader>
      {action && <EmptyContent>{action}</EmptyContent>}
    </Empty>
  );
}

const NOTICE = {
  info: { icon: InfoIcon, variant: "info" },
  success: { icon: CircleCheckIcon, variant: "success" },
  warning: { icon: TriangleAlertIcon, variant: "warning" },
  error: { icon: CircleAlertIcon, variant: "destructive" },
} as const;

/**
 * A message box with a tone. `live` decides how assistive technology hears it: "assertive" for a
 * new problem (role alert), "polite" for a result (role status), none for a standing notice.
 */
export function Notice({
  tone,
  title,
  children,
  live,
  className,
}: {
  tone: keyof typeof NOTICE;
  title?: ReactNode;
  children?: ReactNode;
  live?: "assertive" | "polite";
  className?: string;
}) {
  const { icon: Icon, variant } = NOTICE[tone];
  const role = live === "assertive" ? "alert" : live === "polite" ? "status" : undefined;
  return (
    <Alert variant={variant} role={role} className={className}>
      <Icon aria-hidden="true" />
      {title && <AlertTitle>{title}</AlertTitle>}
      {children && <AlertDescription>{children}</AlertDescription>}
    </Alert>
  );
}

export function LoadingState({ label }: { label: string }) {
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner />
      {label}
    </p>
  );
}
