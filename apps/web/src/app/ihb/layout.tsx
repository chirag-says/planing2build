import { HomeownerHeader } from "@/components/plan2build/homeowner-header";

export default function IhbLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <HomeownerHeader />
      {children}
    </>
  );
}
