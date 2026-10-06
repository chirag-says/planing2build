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
      <ul className="flex gap-1 lg:flex-col">
        {items.map((item) => {
          const current =
            pathname === item.href || (!item.exact && pathname.startsWith(`${item.href}/`));
          return (
            <li key={item.href} className="shrink-0">
              <Link
                href={item.href}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center rounded-md px-3 text-sm font-medium whitespace-nowrap transition-colors",
                  "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                  current
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
