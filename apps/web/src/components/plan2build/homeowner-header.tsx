// The homeowner host's shell header (UI_DESIGN_SYSTEM.md section 10): brand, the estimator, the
// professional directory, the projects, and the account. Until the first project exists the
// projects link is "Start your build plan" instead: there is nothing to list yet. The session is
// read server-side (GET /api/v1/me, never throwing: an unreachable API leaves the header offering
// sign-in); the interactive parts (current page, account menu, phone menu) are a client island.
import { HeaderNav } from "@/components/plan2build/header-nav";
import { getTranslator } from "@/lib/i18n";
import { currentUser, ownProjects } from "@/lib/session";

export async function HomeownerHeader() {
  const user = await currentUser();
  const projects = user ? await ownProjects() : null;
  const t = getTranslator("Nav");
  const home =
    !user
      ? { href: "/sign-in", label: t("start") }
      : (projects?.length ?? 0) === 0
        ? { href: "/start", label: t("start") }
        : { href: "/projects", label: t("projects") };
  return (
    <HeaderNav
      brand={getTranslator("App")("name")}
      tag={t("tag")}
      signedIn={Boolean(user)}
      links={[{ href: "/professionals", label: t("professionals") }, home]}
      accountLinks={[home, { href: "/account/billing", label: t("billing") }]}
    />
  );
}
