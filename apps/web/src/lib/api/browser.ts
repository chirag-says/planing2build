// API access from client components: same origin (ADR-016), cookies sent by the browser, the CSRF
// header added by the generated client. Never holds a token.
import { createApiClient, type ErrorResponse } from "@p2b/contracts";

export const browserApi = createApiClient({ baseUrl: "" });

/** The error code from the API's envelope, or null when the body is not an envelope. */
export function errorCode(error: unknown): string | null {
  const code = (error as ErrorResponse | undefined)?.error?.code;
  return typeof code === "string" ? code : null;
}
