// The homeowner host's shell header (UI_DESIGN_SYSTEM.md section 10): brand, the estimator, the
// professional directory, the projects, and the account. The session is read server-side through GET /api/v1/me; the
// interactive parts (current page, account menu, phone menu) are a client island.
import { HeaderNav } from "@/components/plan2build/header-nav";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";

export async function HomeownerHeader() {
  let signedIn = false;
  try {
    const { data } = await (await serverApi()).GET("/api/v1/me");
    signedIn = Boolean(data);
  } catch {
    // The API being unreachable must not take the page down; the header offers sign-in.
  }
  const t = getTranslator("Nav");
  return (
    <HeaderNav
      brand={getTranslator("App")("name")}
      signedIn={signedIn}
      links={[
        { href: "/estimate", label: t("estimate") },
        { href: "/professionals", label: t("professionals") },
        { href: "/projects", label: t("projects") },
      ]}
      accountLinks={[
        { href: "/projects", label: t("projects") },
        { href: "/account/billing", label: t("billing") },
      ]}
    />
  );
}
