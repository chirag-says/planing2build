import type { Metadata, Viewport } from "next";

import { getTranslator } from "@/lib/i18n";

import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = getTranslator("App");
  return { title: { default: t("name"), template: `%s | ${t("name")}` } };
}

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-background text-foreground">{children}</body>
    </html>
  );
}
