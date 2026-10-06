import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProfileForm } from "@/components/plan2build/pro-forms";
import { getTranslator } from "@/lib/i18n";
import { mapTiles } from "@/lib/map";
import { loadOwnProfile } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Pro")("profile.title") };

export default async function ProProfilePage() {
  const data = await loadOwnProfile("/profile");
  const t = getTranslator("Pro");
  return (
    <PageContainer>
      <PageHeader title={t("profile.title")} description={t("profile.intro")} />
      <ProfileForm data={data} tiles={mapTiles()} />
    </PageContainer>
  );
}
