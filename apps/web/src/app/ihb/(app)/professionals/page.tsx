import { SearchIcon, UsersRoundIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProfessionalCard } from "@/components/plan2build/professional-card";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";

export const metadata: Metadata = { title: getTranslator("Directory")("title") };

type Params = Record<"category" | "q" | "locality" | "project" | "cursor", string | string[] | undefined>;
const one = (value: string | string[] | undefined) => (typeof value === "string" && value ? value : undefined);
const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";

// The public directory (D-09): approved, listed professionals only, in a neutral daily shuffle
// (D-08). Anyone can browse; a signed-in family can narrow it to professionals covering a
// project's plot. Filters are a plain GET form, so the page works without JavaScript.
export default async function DirectoryPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const [category, q, locality, project, cursor] = [
    one(params.category), one(params.q), one(params.locality), one(params.project), one(params.cursor),
  ];
  const api = await serverApi();
  const [categories, me] = await Promise.all([
    api.GET("/api/v1/public/professional-categories"),
    api.GET("/api/v1/me"),
  ]);
  const projects = me.data
    ? ((await api.GET("/api/v1/projects")).data ?? []).filter((p) => p.status !== "DRAFT")
    : [];
  const page = project && me.data
    ? await api.GET("/api/v1/projects/{project_id}/professionals", {
        params: { path: { project_id: project }, query: { category, q, cursor } },
      })
    : await api.GET("/api/v1/public/professionals", { params: { query: { category, q, locality, cursor } } });
  const t = getTranslator("Directory");
  // From a project's service (Slice 3.4): the cards offer a connection request for it.
  const connect =
    project && category && me.data && page.data && (categories.data ?? []).some((c) => c.code === category && !c.parent_code)
      ? { projectId: project, category }
      : undefined;
  const items = page.data?.items ?? [];
  const next = page.data?.next_cursor;
  const query = new URLSearchParams(
    Object.entries({ category, q, locality, project }).filter((e): e is [string, string] => Boolean(e[1])),
  );

  return (
    <PageContainer width="wide">
      <PageHeader title={t("title")} description={t("intro")} />
      <form method="get" className="grid gap-4 rounded-lg border border-border p-4 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
        <div className="flex flex-col gap-2">
          <Label htmlFor="category">{t("category")}</Label>
          <select id="category" name="category" defaultValue={category ?? ""} className={SELECT}>
            <option value="">{t("anyCategory")}</option>
            {(categories.data ?? []).filter((c) => !c.parent_code).map((c) => (
              <option key={c.code} value={c.code}>{c.name}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="q">{t("q")}</Label>
          <Input id="q" name="q" defaultValue={q ?? ""} maxLength={80} />
        </div>
        {projects.length > 0 ? (
          <div className="flex flex-col gap-2">
            <Label htmlFor="project">{t("project")}</Label>
            <select id="project" name="project" defaultValue={project ?? ""} className={SELECT}>
              <option value="">{t("anyProject")}</option>
              {projects.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {t("projectOption", { code: p.code })}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <Label htmlFor="locality">{t("locality")}</Label>
            <Input id="locality" name="locality" defaultValue={locality ?? ""} maxLength={80} />
          </div>
        )}
        <div className="flex gap-2 lg:col-span-2">
          <Button type="submit">
            <SearchIcon aria-hidden="true" />
            {t("apply")}
          </Button>
          <Button asChild variant="ghost">
            <Link href="/professionals">{t("clear")}</Link>
          </Button>
        </div>
      </form>
      {connect && (
        <Notice tone="info">
          {getTranslator("Services")("directoryFor", {
            category: (categories.data ?? []).find((c) => c.code === category)?.name ?? "",
          })}
        </Notice>
      )}
      <Notice tone="info">{t("order")}</Notice>
      {items.length === 0 ? (
        <EmptyState icon={UsersRoundIcon} title={t("empty")} description={t("emptyBody")} />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label={t("title")}>
          {items.map((card) => (
            <li key={card.profile_id}>
              <ProfessionalCard card={card} connect={connect} />
            </li>
          ))}
        </ul>
      )}
      {next && (
        <Button asChild variant="outline" className="self-center">
          <Link href={`/professionals?${new URLSearchParams([...query, ["cursor", next]])}`}>{t("more")}</Link>
        </Button>
      )}
    </PageContainer>
  );
}
