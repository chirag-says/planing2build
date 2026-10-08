"use client";

// Plays a section's entrance once, when it first scrolls into view (the activity timeline, the
// progress marks). Content is visible without script: only a section still below the fold when the
// page loads is held back ("is-armed") until it arrives ("is-in"). Reduced motion ends the
// entrance at once (globals.css).
import { cn } from "cn";
import { useEffect, useRef, useState, type ElementType, type ReactNode } from "react";

export function RevealOnView({
  as: Tag = "div",
  className,
  children,
  ...rest
}: {
  as?: ElementType;
  className?: string;
  children: ReactNode;
} & Record<string, unknown>) {
  const ref = useRef<HTMLElement>(null);
  const [state, setState] = useState<"idle" | "armed" | "in">("idle");

  useEffect(() => {
    const node = ref.current;
    if (!node || !("IntersectionObserver" in window)) return;
    // Already on screen at load: the page's own entrance covers it.
    if (node.getBoundingClientRect().top < window.innerHeight * 0.9) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setState("in");
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -12% 0px" },
    );
    // Held back only once the observer is watching, so it can never stay hidden.
    const frame = requestAnimationFrame(() => {
      setState("armed");
      observer.observe(node);
    });
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);

  return (
    <Tag ref={ref} className={cn(className, state === "armed" && "is-armed", state === "in" && "is-in")} {...rest}>
      {children}
    </Tag>
  );
}
