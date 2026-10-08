"use client";

// The project at the top of the sidebar: its code and locality, and a menu to move to another of
// the family's projects, all projects, or a new one (the workspace switcher of most dashboards).
import { cn } from "cn";
import { CheckIcon, ChevronsUpDownIcon, FolderOpenIcon, PlusIcon } from "lucide-react";
import Link from "next/link";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getTranslator } from "@/lib/i18n";

const shell = getTranslator("Shell");

export interface SwitcherProject {
  id: string;
  code: string;
  locality: string | null;
}

export function ProjectSwitcher({
  current,
  projects,
  status,
}: {
  current: SwitcherProject;
  projects: SwitcherProject[];
  /** The status label, already translated. */
  status: string;
}) {
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger
        className={cn(
          "group flex w-full items-center gap-3 rounded-md bg-foreground/5 px-3 py-2 text-left ring-1 ring-foreground/10 transition-colors",
          "outline-none hover:bg-foreground/10 focus-visible:ring-3 focus-visible:ring-ring/50",
        )}
      >
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="flex items-center gap-2 font-mono text-[0.6875rem] tracking-widest text-muted-foreground uppercase">
            <span aria-hidden="true" className="size-1.5 bg-brand" />
            {shell("project")} · {status}
          </span>
          {/* Two lines, so it sits inside the top bar. */}
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="shrink-0 font-heading text-xl leading-none">{current.code}</span>
            {current.locality && <span className="truncate text-sm text-muted-foreground">{current.locality}</span>}
          </span>
        </span>
        <ChevronsUpDownIcon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground group-hover:text-foreground" />
        <span className="sr-only">{shell("switchProject")}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-60 min-w-60">
        <DropdownMenuLabel className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
          {shell("switchProject")}
        </DropdownMenuLabel>
        {projects.map((project) => (
          <DropdownMenuItem key={project.id} asChild>
            <Link href={`/projects/${project.id}`} className="flex items-start gap-2 py-2 text-base">
              <CheckIcon
                aria-hidden="true"
                className={cn("mt-0.5", project.id === current.id ? "opacity-100" : "opacity-0")}
              />
              <span className="flex min-w-0 flex-col">
                <span className="font-medium">{project.code}</span>
                {project.locality && <span className="truncate text-sm text-muted-foreground">{project.locality}</span>}
              </span>
            </Link>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="py-2 text-base">
          <Link href="/projects">
            <FolderOpenIcon aria-hidden="true" />
            {shell("allProjects")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild className="py-2 text-base">
          <Link href="/start">
            <PlusIcon aria-hidden="true" />
            {shell("newProject")}
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
