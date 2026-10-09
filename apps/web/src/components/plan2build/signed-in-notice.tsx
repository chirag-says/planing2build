"use client";

// Shown on a sign-in page when a session already exists in this browser. Sign-in never skips
// ahead on its own (decided 2026-10-08): the person is told someone is signed in, and chooses to
// carry on as that account or to sign out and use another email. The email form stays below.
import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("SignIn");

export function SignedInNotice({ name, continueHref }: { name: string | null; continueHref: string }) {
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    try {
      await browserApi.POST("/api/v1/auth/logout");
    } finally {
      // A full load, so the page and its cookies start clean.
      window.location.reload();
    }
  }
  return (
    <Notice tone="info" title={name ? t("alreadyAs", { name }) : t("alreadyIn")}>
      <p>{t("alreadyHelp")}</p>
      <div className="mt-3 flex flex-wrap gap-3">
        <Button asChild size="sm">
          <Link href={continueHref}>
            {t("continueAs")}
            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
          </Link>
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void signOut()}>
          {busy && <Spinner />}
          {t("useAnother")}
        </Button>
      </div>
    </Notice>
  );
}
