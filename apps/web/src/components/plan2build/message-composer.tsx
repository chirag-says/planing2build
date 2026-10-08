"use client";

// The message box under a thread. PREVIEW: messaging is not connected yet (OQ-025; decided
// 2026-10-08), so nothing is sent; pressing Send says so and points to the call instead.
import { PhoneIcon, SendIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Inbox");

export function MessageComposer({ name, phoneHref }: { name: string; phoneHref: string | null }) {
  const [text, setText] = useState("");
  const [tried, setTried] = useState(false);
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        setTried(true);
      }}
    >
      <label htmlFor="message" className="sr-only">
        {t("messages.write")}
      </label>
      <Textarea
        id="message"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={t("messages.write")}
        rows={3}
        className="bg-background"
      />
      {tried && (
        <p role="status" className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          {phoneHref ? t("messages.notSent", { name }) : t("messages.notSentNoPhone")}
          {phoneHref && (
            <a href={phoneHref} className="inline-flex items-center gap-1.5 font-medium text-foreground underline underline-offset-4">
              <PhoneIcon aria-hidden="true" className="size-4" />
              {name}
            </a>
          )}
        </p>
      )}
      <Button type="submit" disabled={!text.trim()} className="self-end">
        <SendIcon aria-hidden="true" data-icon="inline-start" />
        {t("messages.send")}
      </Button>
    </form>
  );
}
