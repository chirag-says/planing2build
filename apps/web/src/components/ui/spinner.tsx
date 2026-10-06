import { cn } from "cn"
import { Loader2Icon } from "lucide-react"

function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    // Decorative: the text next to it says what is happening (UI_DESIGN_SYSTEM.md, loading states).
    <Loader2Icon data-slot="spinner" aria-hidden="true" className={cn("size-4 animate-spin", className)} {...props} />
  )
}

export { Spinner }
