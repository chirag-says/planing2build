import { HomeownerShell } from "@/components/plan2build/homeowner-shell";

// The first steps of a requirement that have a page of their own (the welcome choice, the entry
// questions, the new project): the website-style header until the family has a project, then the
// app shell. The leads for families outside the service and everything else signed in are the app
// shell from the first sign-in ((workspace)). A family on its dashboard answers the entry
// questions there, in place.
export default function EntryLayout({ children }: { children: React.ReactNode }) {
  return <HomeownerShell entry>{children}</HomeownerShell>;
}
