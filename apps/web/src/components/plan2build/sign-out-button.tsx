"use client";

import { LogOutIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Account");

export function SignOutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await browserApi.POST("/api/v1/auth/logout");
        } finally {
          router.refresh();
          setBusy(false);
        }
      }}
    >
      {busy ? <Spinner /> : <LogOutIcon aria-hidden="true" />}
      {t("signOut")}
    </Button>
  );
}
