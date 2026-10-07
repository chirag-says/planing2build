import { HomeownerHeader } from "@/components/plan2build/homeowner-header";

export default function IhbLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <HomeownerHeader />
      {/* The website's blueprint ground under every signed-in screen. */}
      <div className="p2b-ground flex flex-1 flex-col">{children}</div>
    </>
  );
}
