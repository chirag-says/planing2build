import { SignOutButton } from "@/components/plan2build/sign-out-button";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";

/** Reads the session through the real API (GET /api/v1/me), server-side. */
export async function AccountStatus() {
  const t = getTranslator("Account");
  let state: "in" | "out" | "unavailable";
  try {
    const { data, response } = await (await serverApi()).GET("/api/v1/me");
    state = data ? "in" : response.status === 401 ? "out" : "unavailable";
  } catch {
    state = "unavailable";
  }
  const message = { in: t("signedIn"), out: t("signedOut"), unavailable: t("unavailable") }[state];
  return (
    <div className="flex flex-wrap items-center gap-4">
      <p role="status" className="text-sm text-muted-foreground">
        {message}
      </p>
      {state === "in" && <SignOutButton />}
    </div>
  );
}
