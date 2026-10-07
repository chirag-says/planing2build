// Page and section headings with one spacing and type scale (UI_DESIGN_SYSTEM.md section 3).
import { cn } from "cn";
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="flex min-w-0 flex-col gap-2">
        {eyebrow && <div className="text-sm text-muted-foreground">{eyebrow}</div>}
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-balance sm:text-3xl">
          {title}
        </h1>
        {description && (
          <div className="max-w-prose text-base text-pretty text-muted-foreground">{description}</div>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function SectionHeader({
  id,
  title,
  description,
  action,
  level = 2,
}: {
  id?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  level?: 2 | 3;
}) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex min-w-0 flex-col gap-1">
        <Heading
          id={id}
          className={cn("font-heading font-semibold", level === 2 ? "text-xl" : "text-lg")}
        >
          {title}
        </Heading>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}

/** The content column for every homeowner page: full width on phones, a readable width above. */
export function PageContainer({
  children,
  width = "default",
  className,
}: {
  children: ReactNode;
  width?: "narrow" | "default" | "wide" | "full";
  className?: string;
}) {
  const max = { narrow: "max-w-md", default: "max-w-3xl", wide: "max-w-5xl", full: "max-w-7xl" }[width];
  return (
    <main
      id="main"
      className={cn("mx-auto flex w-full flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12", max, className)}
    >
      {children}
    </main>
  );
}
