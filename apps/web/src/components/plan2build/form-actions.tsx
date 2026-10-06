// The action row at the end of a form. On phones it sticks to the bottom of the screen so the
// primary action and the save state stay in reach of a thumb; from sm up it sits in the flow.
import { cn } from "cn";
import type { ReactNode } from "react";

export function FormActions({
  children,
  status,
  sticky = false,
  className,
}: {
  children: ReactNode;
  status?: ReactNode;
  sticky?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
        sticky &&
          "sticky bottom-0 z-10 -mx-4 border-t border-border bg-background/95 px-4 py-3 backdrop-blur-sm sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-none",
        className,
      )}
    >
      {status && <div className="text-sm text-muted-foreground">{status}</div>}
      <div className="flex gap-2 sm:ml-auto [&>*]:flex-1 sm:[&>*]:flex-none">
        {children}
      </div>
    </div>
  );
}
