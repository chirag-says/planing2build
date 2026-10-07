import { HeaderNav } from "@/components/plan2build/header-nav";
import { getTranslator } from "@/lib/i18n";
import { signedInProfessional } from "@/lib/professional";

// Professionals host shell: the shared header, with the professional's own pages once signed in.
export default async function ProLayout({ children }: { children: React.ReactNode }) {
  const t = getTranslator("Pro");
  let signedIn = false;
  try {
    signedIn = await signedInProfessional();
  } catch {
    // The API being unreachable must not take the shell down; pages show their own error.
  }
  const links = [
    { href: "/", label: t("nav.dashboard") },
    { href: "/connections", label: t("nav.connections") },
    { href: "/quotes", label: t("nav.quotes") },
    { href: "/build-plan", label: t("nav.buildPlan") },
    { href: "/inspections", label: t("nav.inspections") },
    { href: "/profile", label: t("nav.profile") },
    { href: "/portfolio", label: t("nav.portfolio") },
  ];
  return (
    <>
      <HeaderNav brand={t("title")} tag={t("tag")} signedIn={signedIn} links={signedIn ? links : []} />
      {children}
    </>
  );
}
