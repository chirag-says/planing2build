import { HeaderNav } from "@/components/plan2build/header-nav";
import { getTranslator } from "@/lib/i18n";
import { staffSession } from "@/lib/staff";

// Operations host shell: the same header component as the homeowner host, with operations links
// shown only once the session holds the OPS role and a fresh second factor.
export default async function OpsLayout({ children }: { children: React.ReactNode }) {
  const t = getTranslator("Ops");
  let staff = null;
  try {
    staff = await staffSession();
  } catch {
    // The API being unreachable must not take the shell down; pages show their own error.
  }
  const verified = Boolean(staff?.mfa_verified);
  const ops = verified && Boolean(staff?.roles.includes("OPS"));
  const admin = verified && Boolean(staff?.roles.includes("ADMIN"));
  const links = [
    ...(ops ? [{ href: "/queue", label: t("nav.queue") }] : []),
    ...(ops || admin ? [{ href: "/professionals", label: t("nav.professionals") }] : []),
    ...(ops || admin ? [{ href: "/billing", label: t("nav.billing") }] : []),
    ...(ops || admin ? [{ href: "/build-plan", label: t("nav.buildPlan") }] : []),
    ...(ops || admin ? [{ href: "/rfqs", label: t("nav.rfqs") }] : []),
    ...(ops || admin ? [{ href: "/execution", label: t("nav.execution") }] : []),
    ...(ops || admin ? [{ href: "/assurance", label: t("nav.assurance") }] : []),
    ...(admin ? [{ href: "/admin/billing", label: t("nav.configuration") }] : []),
  ];
  return (
    <>
      <HeaderNav brand={t("title")} tag={t("tag")} signedIn={Boolean(staff)} links={links} />
      {children}
    </>
  );
}
