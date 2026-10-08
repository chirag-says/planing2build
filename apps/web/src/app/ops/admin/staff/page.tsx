import { UsersIcon } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">{t("staff.email")}</TableHead>
                  <TableHead scope="col">{t("staff.roles")}</TableHead>
                  <TableHead scope="col">{t("staff.status")}</TableHead>
                  <TableHead scope="col">{t("staff.mfa")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((member) => (
                  <TableRow key={member.user_id} data-testid="staff-member">
                    <TableCell className="font-medium break-all whitespace-normal">
                      {member.email}
                    </TableCell>
                    <TableCell>
                      <span className="flex flex-wrap gap-1">
                        {member.roles.map((role) => (
                          <Badge key={role} variant="outline">{t(`staff.roleNames.${role}`)}</Badge>
                        ))}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant={member.status === "ACTIVE" ? "success" : "neutral"}>
                        {t(`staff.statuses.${member.status}`)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={member.mfa_enabled ? "success" : "warning"}>
                        {member.mfa_enabled ? t("staff.mfaOn") : t("staff.mfaOff")}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </PageContainer>
  );
}
