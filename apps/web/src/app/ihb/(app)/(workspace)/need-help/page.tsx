import type { Metadata } from "next";

import { EnquiryPage } from "@/components/plan2build/enquiry-page";
import { getTranslator } from "@/lib/i18n";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Enquiry")("helpTitle") };

export default function NeedHelpPage() {
  const t = getTranslator("Enquiry");
  return <EnquiryPage kind="COMING_SOON_HELP" title={t("helpTitle")} intro={t("helpIntro")} />;
}
