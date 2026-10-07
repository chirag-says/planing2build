import { MarketingShell } from "@/marketing/MarketingShell";

/** The public website: loader, site header, and the page column the footer lifts off. */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return <MarketingShell>{children}</MarketingShell>;
}
