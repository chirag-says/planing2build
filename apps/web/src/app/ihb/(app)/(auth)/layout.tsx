import { HomeownerHeader } from "@/components/plan2build/homeowner-header";

// Sign-in sits outside the app shell: before the email there is no account and no dashboard,
// only the website header. A signed-in visitor never sees it (the page sends them on).
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <HomeownerHeader />
      <div className="p2b-ground flex flex-1 flex-col">{children}</div>
    </>
  );
}
