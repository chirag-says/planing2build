import { UsersIcon } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("staff.title") };

// Staff accounts for ADMIN (API 18), read only: accounts are created from the command line, so
// there is no form here.
export default async function AdminStaffPage() {
  const staff = await requireVerifiedStaff("/admin/staff");
  if (!staff.roles.includes("ADMIN")) notFound();
  const t = getTranslator("Ops");
  const { data, error } = await (await serverApi()).GET("/api/v1/admin/staff");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("staff.title")} description={t("staff.intro")} />
      {!data ? (
        <Notice tone="error" title={t("staff.error")}>{error?.error?.message}</Notice>
      ) : data.length === 0 ? (
        <EmptyState icon={UsersIcon} title={t("staff.empty")} />
      ) : (
        <Card size="sm">
          <CardContent>
            {/* A list, not a table: each row is one account and its badges label themselves, so it
                reads on a phone without a sideways-scrolling region. Columns line up from sm. */}
            <ul className="flex flex-col divide-y divide-border">
              {data.map((member) => (
                <li key={member.user_id} data-testid="staff-member"
                  className="grid gap-2 py-3 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto_auto] sm:items-center sm:gap-4">
                  <span className="font-medium break-all">{member.email}</span>
                  <span className="flex flex-wrap gap-1" aria-label={t("staff.roles")}>
                    {member.roles.map((role) => (
                      <Badge key={role} variant="outline">{t(`staff.roleNames.${role}`)}</Badge>
                    ))}
                  </span>
                  <Badge variant={member.status === "ACTIVE" ? "success" : "neutral"}>
                    {t(`staff.statuses.${member.status}`)}
                  </Badge>
                  <Badge variant={member.mfa_enabled ? "success" : "warning"}>
                    {member.mfa_enabled ? t("staff.mfaOn") : t("staff.mfaOff")}
                  </Badge>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </PageContainer>
  );
}
