import { HomeownerShell } from "@/components/plan2build/homeowner-shell";

// The first steps of a requirement (the entry questions, the leads for families outside the
// service, the new project): the website-style header until the family has a project, then the
// app shell. Everything else signed in is the app shell from the first sign-in ((workspace)).
export default function EntryLayout({ children }: { children: React.ReactNode }) {
  return <HomeownerShell entry>{children}</HomeownerShell>;
}
