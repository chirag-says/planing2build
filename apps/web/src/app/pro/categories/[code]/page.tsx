import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { CategoryHeaderBadge, CategoryWorkspace } from "@/components/plan2build/pro-forms";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { getTranslator } from "@/lib/i18n";
import { loadOwnProfile } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Pro")("dashboard.categories") };

// One category: what Plan2Build checks for it (versioned requirements, D-02), the evidence
// supplied, and submitting, hiding or showing it. Listing is per category (D-06).
export default async function ProCategoryPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const data = await loadOwnProfile(`/categories/${code}`);
  const category = data.categories.find((c) => c.code === code);
  if (!category) notFound();
  const t = getTranslator("Pro");
  return (
    <PageContainer>
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb root={{ label: t("category.back"), href: "/" }} trail={[{ label: category.name }]} />
        <PageHeader title={category.name} actions={<CategoryHeaderBadge category={category} />} />
      </div>
      <CategoryWorkspace data={data} category={category} />
    </PageContainer>
  );
}
