// User-facing strings live in messages/ (ADR-022: English only at the MVP, externalised so Hindi is
// a translation, not a code change). use-intl is the framework-agnostic core of next-intl, with the
// same ICU message format; it is used directly because next-intl's Next.js plugin now requires a
// native SWC binary (baseline deviation recorded in FOUNDATION_PLAN).
import { createTranslator } from "use-intl/core";

import messages from "../../messages/en.json";

export const LOCALE = "en";

type Messages = typeof messages;

export function getTranslator<N extends keyof Messages>(namespace: N) {
  return createTranslator<Messages, N>({ locale: LOCALE, messages, namespace });
}
