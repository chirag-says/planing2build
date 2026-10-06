"use client";

// Claim or release a review item (API 18). Claiming says who is reviewing; it changes no project
// state. One person at a time: the API answers 409 if someone else holds it.
import type { components } from "@p2b/contracts";
import { HandIcon, UndoIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

type QueueItem = Pick<
  components["schemas"]["QueueItemOut"],
  "item_id" | "claimed_by_me" | "claimed_by_email"
>;

const t = getTranslator("Ops");
const common = getTranslator("Common");

export function ClaimControl({ item }: { item: QueueItem }) {
  const router = useRouter();
  const [busy, setBusy] = useState<"claim" | "release" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(action: "claim" | "release") {
    setBusy(action);
    setError(null);
    try {
      const params = { params: { path: { item_id: item.item_id } } };
      const { data, error: failure } =
        action === "claim"
          ? await browserApi.POST("/api/v1/ops/queue-items/{item_id}/claim", params)
          : await browserApi.POST("/api/v1/ops/queue-items/{item_id}/release", params);
      if (data) {
        router.refresh();
      } else {
        setError(
          errorCode(failure) === "STATE_CONFLICT" ? t("detail.claimConflict") : common("unavailable"),
        );
      }
    } catch {
      setError(common("unavailable"));
    } finally {
      setBusy(null);
    }
  }

  const status = item.claimed_by_me
    ? t("detail.claimedByYou")
    : item.claimed_by_email
      ? t("detail.claimedBy", { email: item.claimed_by_email })
      : t("detail.unclaimed");

  return (
    <div className="flex flex-col gap-4">
      <p role="status" className="text-base">
        {status}
      </p>
      {error && (
        <Notice tone="error" live="assertive">
          {error}
        </Notice>
      )}
      {item.claimed_by_me ? (
        <Button
          type="button"
          variant="outline"
          onClick={() => act("release")}
          disabled={busy !== null}
          className="sm:self-start"
        >
          {busy === "release" ? <Spinner /> : <UndoIcon aria-hidden="true" />}
          {busy === "release" ? t("detail.releasing") : t("detail.release")}
        </Button>
      ) : (
        !item.claimed_by_email && (
          <Button
            type="button"
            onClick={() => act("claim")}
            disabled={busy !== null}
            className="sm:self-start"
          >
            {busy === "claim" ? <Spinner /> : <HandIcon aria-hidden="true" />}
            {busy === "claim" ? t("detail.claiming") : t("detail.claim")}
          </Button>
        )
      )}
    </div>
  );
}
