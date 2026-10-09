// A professional's way to a listing (PROFESSIONALS_FLOW section 44.2): profile, service,
// portfolio, the trade's verification requirements, listed. Drawn as the homeowner journey rail
// (journey-rail.css); every state comes from readinessOf (lib/pro-console.ts), the one place the
// rules live, and each step links to the screen where it is done.
import type { components } from "@p2b/contracts";
import { cn } from "cn";
import Link from "next/link";
import type { CSSProperties } from "react";

import { getTranslator } from "@/lib/i18n";
import { readinessOf, type Checkpoint } from "@/lib/pro-console";
import "./journey-rail.css";

type Dashboard = components["schemas"]["OwnDashboardOut"];

/** The rail's step names for the console's checkpoint keys (Pro.onboarding.steps). */
const STEP: Record<Checkpoint["key"], "profile" | "category" | "portfolio" | "evidence" | "listed"> = {
  profile: "profile",
  services: "category",
  portfolio: "portfolio",
  evidence: "evidence",
  listed: "listed",
};

export function OnboardingRail({ data }: { data: Dashboard }) {
  const t = getTranslator("Pro");
  const { checkpoints } = readinessOf(data);
  return (
    <section aria-labelledby="onboarding-title" className="jr">
      <h2 id="onboarding-title" className="sr-only">
        {t("onboarding.title")}
      </h2>
      <div className="jr-scroll" role="region" tabIndex={0} aria-labelledby="onboarding-title">
        <ol className="jr-rail jr-rail-5">
          {checkpoints.map((checkpoint, index) => {
            const { state } = checkpoint;
            const name = t(`onboarding.steps.${STEP[checkpoint.key]}.name`);
            const look = state === "attention" || state === "review" ? "current" : state;
            return (
              <li
                key={checkpoint.key}
                className={cn("jr-step", `is-${look}`)}
                aria-current={look === "current" ? "step" : undefined}
                style={{ "--i": index } as CSSProperties}
              >
                <span className="jr-bar" aria-hidden="true" />
                <p className="jr-top font-mono" aria-hidden="true">
                  <b>{String(index + 1).padStart(2, "0")}</b>
                  <span>{t(`onboarding.states.${state}`)}</span>
                </p>
                <p className="jr-name font-heading">
                  <Link href={checkpoint.href} className="rounded-sm underline-offset-4 hover:underline">
                    <span aria-hidden="true">{name}</span>
                    <span className="sr-only">{t(`onboarding.sr.${state}`, { step: name })}</span>
                  </Link>
                </p>
                <p className="jr-items">{t(`onboarding.steps.${STEP[checkpoint.key]}.text`)}</p>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
