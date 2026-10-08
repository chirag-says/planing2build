// Page and section headings with one spacing and type scale (UI_DESIGN_SYSTEM.md section 3).
import { cn } from "cn";
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  size = "default",
  className,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** "compact" inside the app shell's dashboards, where the top bar already says where you are. */
  size?: "default" | "compact";
  className?: string;
}) {
  return (
    <header className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="flex min-w-0 flex-col gap-3">
        {eyebrow && (
          <div className="flex items-center gap-2.5 font-mono text-xs tracking-widest text-muted-foreground uppercase">
            <span aria-hidden="true" className="size-2 shrink-0 bg-brand ring-1 ring-foreground" />
            {eyebrow}
          </div>
        )}
        {/* The website's headline reveal: the title rises out of its line, then the brass beam. */}
        <h1
          className={cn(
            "p2b-rise-clip font-heading leading-none font-extrabold text-balance uppercase",
            size === "compact" ? "text-3xl sm:text-4xl" : "text-4xl sm:text-5xl",
          )}
        >
          <span className="p2b-rise-in">{title}</span>
        </h1>
        <span aria-hidden="true" className="p2b-beam" />
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
          className={cn(
            "font-heading font-extrabold uppercase",
            level === 2 ? "text-2xl leading-none" : "text-xl leading-none",
          )}
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
  width?: "narrow" | "default" | "wide";
  className?: string;
}) {
  const max = { narrow: "max-w-md", default: "max-w-3xl", wide: "max-w-5xl" }[width];
  return (
    <main
      id="main"
      className={cn("mx-auto flex w-full flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12", max, className)}
    >
      {children}
    </main>
  );
}

/** The website's eyebrow: a brass square and mono caps. */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("flex items-center gap-2.5 font-mono text-xs tracking-widest text-muted-foreground uppercase", className)}>
      <span aria-hidden="true" className="size-2 shrink-0 bg-brand ring-1 ring-foreground" />
      {children}
    </p>
  );
}

/** A section of the story: an ink rule over it, its heading in the display face. */
export function RuledSection({
  id,
  title,
  aside,
  children,
  className,
}: {
  id: string;
  title: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-labelledby={id} className={cn("flex flex-col gap-4 border-t-2 border-foreground pt-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={id} className="font-heading text-2xl leading-none">
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
