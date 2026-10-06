// Where a project page sits: a root list (the family's "My projects" by default, the review queue
// for operations), then the project, then (optionally) the current page.
import Link from "next/link";
import { Fragment } from "react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { getTranslator } from "@/lib/i18n";

type Crumb = { label: string; href?: string };

export function ProjectBreadcrumb({ trail, root }: { trail: Crumb[]; root?: Crumb }) {
  const t = getTranslator("Projects");
  const items = [root ?? { label: t("title"), href: "/projects" }, ...trail];
  return (
    <Breadcrumb aria-label={t("breadcrumb")}>
      <BreadcrumbList>
        {items.map((item, index) => (
          <Fragment key={item.label}>
            {index > 0 && <BreadcrumbSeparator />}
            <BreadcrumbItem>
              {item.href && index < items.length - 1 ? (
                <BreadcrumbLink asChild>
                  <Link href={item.href}>{item.label}</Link>
                </BreadcrumbLink>
              ) : (
                <BreadcrumbPage>{item.label}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
