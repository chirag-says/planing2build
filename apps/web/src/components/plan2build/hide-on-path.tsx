"use client";

// Renders its children everywhere but on one exact path: the project's header steps aside on the
// overview, which opens with its own greeting and the home.
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function HideOnPath({ path, children }: { path: string; children: ReactNode }) {
  return usePathname() === path ? null : children;
}
