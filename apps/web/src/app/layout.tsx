import type { Metadata, Viewport } from "next";

import { fontVariables } from "@/fonts";
import { getTranslator } from "@/lib/i18n";

// Token file first, then the brand kit shared by the public website and the signed-in screens
// (buttons, eyebrow, headline reveal, focus rings; UI_DESIGN_SYSTEM.md 16).
import "./globals.css";
import "@/marketing/styles/kit.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = getTranslator("App");
  return { title: { default: t("name"), template: `%s | ${t("name")}` } };
}

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fontVariables} h-full antialiased`} suppressHydrationWarning>
      <body className="flex min-h-full flex-col bg-background text-foreground">{children}</body>
    </html>
  );
}
