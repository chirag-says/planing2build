import { PageTransition } from "@/marketing/components/layout/PageTransition";
import { SmoothScroll } from "@/marketing/components/layout/SmoothScroll";

/**
 * Homeowner host. The public pages, `(marketing)`, and the signed-in screens, `(app)`, share
 * the page transition (the hoist plate) and smooth scrolling, so both keep running as a
 * visitor moves from the website into sign-in and their projects.
 */
export default function IhbLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <PageTransition />
      <SmoothScroll />
    </>
  );
}
