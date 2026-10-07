import { HeaderNav } from "@/components/plan2build/header-nav";
import { getTranslator } from "@/lib/i18n";

// Sign-in sits outside the app shell: before the email there is no account and no dashboard,
// only the website header. A signed-in professional never sees it (the page sends them on).
export default function ProAuthLayout({ children }: { children: React.ReactNode }) {
  const t = getTranslator("Pro");
  return (
    <>
      <HeaderNav brand={t("title")} tag={t("tag")} signedIn={false} links={[]} />
      {/* The website's blueprint ground under every professional screen. */}
      <div className="p2b-ground flex flex-1 flex-col">{children}</div>
    </>
  );
}
