// The hanging card of the public website's "Plan a project" section, used as the frame for
// sign-in and the form screens (UI_DESIGN_SYSTEM.md 11: lowered once on load). The card, its
// slings, hazard edge, header row and numbered steps are the website's own styles
// (marketing/styles/card.css); hanging-card.css adds the night backdrop and the load-time drop.
import type { CSSProperties, ReactNode } from "react";

import photo from "@/marketing/assets/house-blueprint.webp";
import "@/marketing/styles/card.css";
import "./hanging-card.css";

export function HangingCard({
  title,
  description,
  eyebrow,
  label,
  note,
  children,
}: {
  /** The page's h1, beside the card on wide screens and above it on phones. */
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  /** Mono label on the card's header row ("Sign in"). */
  label: ReactNode;
  /** Right-hand note on the header row ("Takes one minute"). */
  note?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main id="main" className="hc gd-dark">
      <div className="bid-bg" aria-hidden="true">
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative backdrop, static import */}
        <img src={photo.src} alt="" decoding="async" draggable={false} />
      </div>
      <div className="bid-shade" aria-hidden="true" />
      <div className="bid-grid" aria-hidden="true" />
      <div className="hc-wrap">
        <div className="hc-copy">
          {eyebrow && (
            <p className="hc-eb font-mono">
              <i aria-hidden="true" />
              {eyebrow}
            </p>
          )}
          <h1 className="hc-h font-heading">{title}</h1>
          {description && <div className="hc-sub">{description}</div>}
        </div>
        <div className="hc-bay">
          <div className="bid-rig hc-rig">
            <span className="bid-sl is-l" aria-hidden="true" />
            <span className="bid-sl is-r" aria-hidden="true" />
            <div className="bid-card hc-card gd-lt">
              <span className="bid-haz" aria-hidden="true" />
              <p className="bid-top font-mono">
                <span>
                  <i aria-hidden="true" />
                  {label}
                </span>
                {note && <span>{note}</span>}
              </p>
              {children}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

/** One numbered step on the card: an ink number chip and a caps question, then its controls. */
export function CardStep({
  number,
  title,
  children,
}: {
  number: number;
  title: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="bid-step hc-step" style={{ "--i": number } as CSSProperties}>
      <p className="bid-st">
        <b className="font-mono" aria-hidden="true">
          {String(number).padStart(2, "0")}
        </b>
        <span className="font-heading font-extrabold">{title}</span>
      </p>
      {children}
    </div>
  );
}

/**
 * The same card for long forms (the requirement wizard): hazard edge and header row, without the
 * slings and the drop, which suit a short card only.
 */
export function CardSheet({ label, note, children }: { label: ReactNode; note?: ReactNode; children: ReactNode }) {
  return (
    <div className="bid-card hc-sheet gd-lt">
      <span className="bid-haz" aria-hidden="true" />
      <p className="bid-top font-mono">
        <span>
          <i aria-hidden="true" />
          {label}
        </span>
        {note && <span>{note}</span>}
      </p>
      <div className="pt-4">{children}</div>
    </div>
  );
}
