// The dashboard's "at a glance" row (UI_DESIGN_SYSTEM.md section 9): up to four figures, each with
// a label, a caption saying what it counts, and, where there is one, the page it opens.
import { cn } from "cn";
import { ArrowUpRightIcon } from "lucide-react";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import "./stat-tile.css";

export interface Stat {
  label: string;
  value: ReactNode;
  caption?: ReactNode;
  href?: string;
  /** "lead" for the figure that matters most now; "attention" when something waits. */
  tone?: "default" | "lead" | "attention";
}

export function StatGrid({ id, title, stats }: { id: string; title: string; stats: Stat[] }) {
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="sr-only">
        {title}
      </h2>
      <ul className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        {stats.map((stat, index) => (
          <li key={stat.label} className="min-w-0">
            <StatTile {...stat} index={index} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function StatTile({ label, value, caption, href, tone = "default", index }: Stat & { index: number }) {
  const body = (
    <>
      <span aria-hidden="true" className="st-bar" />
      <span className="pr-6 font-mono text-xs tracking-widest text-muted-foreground uppercase sm:text-sm">{label}</span>
      <span className="st-value font-heading text-3xl leading-none sm:text-4xl">
        <span>{value}</span>
      </span>
      {caption && <span className="text-sm text-muted-foreground sm:text-base">{caption}</span>}
      {href && <ArrowUpRightIcon aria-hidden="true" className="st-arrow size-4" />}
    </>
  );
  const className = cn("st-tile", tone !== "default" && `is-${tone}`);
  const style = { "--i": index } as CSSProperties;
  return href ? (
    <Link href={href} className={cn(className, "outline-none focus-visible:ring-3 focus-visible:ring-ring/50")} style={style}>
      {body}
    </Link>
  ) : (
    <div className={className} style={style}>
      {body}
    </div>
  );
}
