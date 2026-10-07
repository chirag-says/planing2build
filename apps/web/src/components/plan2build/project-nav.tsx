"use client";

// The project dashboard's section links (PD-07). A column beside the content on wide screens and a
// scrolling row above it on phones; the current section carries aria-current. Only sections that
// have content are passed in, so nothing unbuilt is shown.
import { cn } from "cn";
import Link from "next/link";
import { usePathname } from "next/navigation";

export interface ProjectNavItem {
  href: string;
  label: string;
  /** Current only on this exact path (the overview), not on pages below it. */
  exact?: boolean;
}

export function ProjectNav({ label, items }: { label: string; items: ProjectNavItem[] }) {
  const pathname = usePathname();
  return (
    <nav aria-label={label} className="-mx-4 overflow-x-auto px-4 lg:mx-0 lg:overflow-visible lg:px-0">
      <ul className="flex gap-1 lg:flex-col lg:border-t-2 lg:border-foreground">
        {items.map((item, index) => {
          const current =
            pathname === item.href || (!item.exact && pathname.startsWith(`${item.href}/`));
          return (
            <li key={item.href} className="shrink-0">
              <Link
                href={item.href}
                aria-current={current ? "page" : undefined}
                // The website's step rail: a mono number, the label in caps, the brass square on the
                // current section.
                className={cn(
                  "group flex min-h-11 items-center gap-2.5 rounded-md px-3 font-mono text-xs tracking-widest whitespace-nowrap uppercase transition-colors lg:rounded-none lg:border-b lg:border-foreground/15",
                  "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                  current
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <span aria-hidden="true" className={cn("tabular-nums", current ? "text-brand" : "text-muted-foreground")}>
                  {String(index + 1).padStart(2, "0")}
                </span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
