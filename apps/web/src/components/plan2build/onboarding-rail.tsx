// A professional's way to a listing (PROFESSIONALS_FLOW section 44.2): profile, category,
// evidence and review, portfolio, listed. Drawn as the homeowner journey rail (journey-rail.css);
// every state comes from the profile the dashboard already loaded, and each step links to the
// screen where it is done.
import type { components } from "@p2b/contracts";
import { cn } from "cn";
import Link from "next/link";
import type { CSSProperties } from "react";

import { getTranslator } from "@/lib/i18n";
import "./journey-rail.css";

type Dashboard = components["schemas"]["OwnDashboardOut"];
type StepState = "done" | "current" | "next" | "attention" | "review";
type Step = { key: "profile" | "category" | "evidence" | "portfolio" | "listed"; href: string; done: boolean; state?: StepState };

export function OnboardingRail({ data }: { data: Dashboard }) {
  const t = getTranslator("Pro");
  const states = data.categories.map((category) => category.listing_state);
  const draft = data.categories.find((category) => category.listing_state === "DRAFT" || category.listing_state === "CHANGES_REQUESTED");
  const submitted = states.some((state) => state !== "DRAFT");
  const listed = states.includes("LISTED");
  const steps: Step[] = [
    { key: "profile", href: "/profile", done: data.profile.missing.length === 0 },
    { key: "category", href: "/services#add", done: data.categories.length > 0 },
    {
      key: "evidence",
      href: draft ? `/categories/${draft.code}` : "/services",
      done: submitted && !states.includes("CHANGES_REQUESTED"),
      state: states.includes("CHANGES_REQUESTED") ? "attention" : undefined,
    },
    { key: "portfolio", href: "/portfolio", done: data.portfolio.length > 0 },
    { key: "listed", href: "/services", done: listed, state: !listed && states.includes("PENDING_REVIEW") ? "review" : undefined },
  ];
  // The first step not done is the one to do now; a step with its own state keeps it.
  const firstOpen = steps.findIndex((step) => !step.done);
  return (
    <section aria-labelledby="onboarding-title" className="jr">
      <h2 id="onboarding-title" className="sr-only">
        {t("onboarding.title")}
      </h2>
      <div className="jr-scroll" role="region" tabIndex={0} aria-labelledby="onboarding-title">
        <ol className="jr-rail jr-rail-5">
          {steps.map((step, index) => {
            const state: StepState = step.done ? "done" : (step.state ?? (index === firstOpen ? "current" : "next"));
            const name = t(`onboarding.steps.${step.key}.name`);
            const look = state === "attention" || state === "review" ? "current" : state;
            return (
              <li
                key={step.key}
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
                  <Link href={step.href} className="rounded-sm underline-offset-4 hover:underline">
                    <span aria-hidden="true">{name}</span>
                    <span className="sr-only">{t(`onboarding.sr.${state}`, { step: name })}</span>
                  </Link>
                </p>
                <p className="jr-items">{t(`onboarding.steps.${step.key}.text`)}</p>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
