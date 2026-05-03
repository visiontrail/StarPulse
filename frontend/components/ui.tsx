import * as Select from "@radix-ui/react-select";
import { Check, ChevronDown, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Button({
  className,
  children,
  busy,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button
      className={cn(
        "inline-flex h-9 items-center justify-center gap-2 rounded border border-warm bg-surface-soft px-3 text-sm font-medium text-ink shadow-panel transition hover:border-warm-strong hover:text-accent disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "succeeded" || status === "online" || status === "ready" || status === "passed"
      ? "border-ok/25 bg-ok/10 text-ok"
      : status === "failed" ||
          status === "offline" ||
          status === "error" ||
          status === "blocked" ||
          status === "verification_failed"
        ? "border-error/25 bg-error/10 text-error"
        : status === "running" || status === "testing" || status === "verifying" || status === "queued"
          ? "border-info/25 bg-info/10 text-info"
          : "border-warn/25 bg-warn/10 text-warn";
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded border px-2 font-mono text-[11px] uppercase",
        tone
      )}
    >
      {status}
    </span>
  );
}

export function EmptyState({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center gap-3 rounded border border-dashed border-warm bg-paper p-8 text-center text-muted">
      <div className="text-ink">{icon}</div>
      <p className="text-sm font-medium text-ink">{title}</p>
    </div>
  );
}

export function FieldLabel({ children }: { children: ReactNode }) {
  return <span className="font-mono text-[11px] uppercase text-muted">{children}</span>;
}

export function DatastoreSelect({
  value,
  onValueChange
}: {
  value: string;
  onValueChange: (value: string) => void;
}) {
  return (
    <Select.Root value={value} onValueChange={onValueChange}>
      <Select.Trigger className="inline-flex h-9 min-w-32 items-center justify-between gap-2 rounded border border-warm bg-paper px-3 text-sm text-ink outline-none transition hover:border-warm-strong">
        <Select.Value />
        <Select.Icon>
          <ChevronDown className="h-4 w-4" />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content className="overflow-hidden rounded border border-warm bg-paper shadow-lg">
          <Select.Viewport className="p-1">
            {["running", "candidate", "startup"].map((datastore) => (
              <Select.Item
                key={datastore}
                value={datastore}
                className="relative flex h-8 cursor-default select-none items-center rounded px-8 text-sm text-ink outline-none data-[highlighted]:bg-surface"
              >
                <Select.ItemIndicator className="absolute left-2">
                  <Check className="h-4 w-4" />
                </Select.ItemIndicator>
                <Select.ItemText>{datastore}</Select.ItemText>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
