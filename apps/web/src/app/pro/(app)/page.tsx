import type { Metadata } from "next";

import {
  ActiveWork,
  AttentionBoard,
  Greeting,
  InspectionsStrip,
  Pipeline,
  ProfileNotice,
  RecordPanel,
} from "@/components/plan2build/pro-console";
import { getTranslator } from "@/lib/i18n";
import { buildConsole, type Console } from "@/lib/pro-console";
import { previewAllowed, previewInput } from "@/lib/pro-console-preview";
import { loadConsole, loadOwnProfile } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Console")("title") };

// The professional's home: their work first. Projects on site and requests to review lead (the
// projects first once there are any); the listing is a slim notice above them until it is done,
// then it leaves the page. Listing is per category (D-06); approval alone lists a category and
// nothing here is paid (D-03).

async function consoleFor(preview: unknown): Promise<{ console: Console; preview: string | null }> {
  if (previewAllowed(preview)) {
    const dashboard = await loadOwnProfile("/");
    return { console: buildConsole(previewInput(preview, dashboard, new Date())), preview };
  }
  return { console: await loadConsole("/"), preview: null };
}

export default async function ProDashboardPage({ searchParams }: { searchParams: Promise<{ preview?: string }> }) {
  const { preview: asked } = await searchParams;
  const { console: c, preview } = await consoleFor(asked);
  const t = getTranslator("Console");
  const now = new Date();
  const working = c.state === "working";
  const started = c.state === "working" || c.state === "listed";
  return (
    <main id="main" className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-6 sm:px-6 sm:py-8 lg:gap-12 lg:px-8">
      <ProfileNotice console={c} />
      {preview && (
        <p role="status" className="self-start bg-brand px-2 py-1 font-mono text-xs tracking-widest text-brand-foreground uppercase">
          {t("preview", { state: preview })}
        </p>
      )}
      <Greeting console={c} now={now} />
      {working ? (
        <>
          <ActiveWork console={c} />
          <AttentionBoard console={c} />
        </>
      ) : (
        <>
          <AttentionBoard console={c} />
          <ActiveWork console={c} />
        </>
      )}
      <InspectionsStrip console={c} />
      {started && <Pipeline console={c} />}
      {c.record.length > 0 && <RecordPanel console={c} />}
    </main>
  );
}
