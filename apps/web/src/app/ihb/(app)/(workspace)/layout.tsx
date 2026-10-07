import { HomeownerShell } from "@/components/plan2build/homeowner-shell";

// Projects, the estimator, the directory, billing and help: the shell with the workspace sidebar
// once signed in, the website-style header before.
export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return <HomeownerShell>{children}</HomeownerShell>;
}
