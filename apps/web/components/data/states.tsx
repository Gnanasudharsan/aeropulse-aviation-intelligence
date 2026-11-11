"use client";

import { AlertTriangle, Clock, DatabaseZap, Inbox, RotateCw, Unplug, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function ErrorState({
  error,
  onRetry,
  title,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  className?: string;
}) {
  const apiErr = error instanceof ApiError ? error : null;
  const notConfigured = apiErr?.code === "not_configured";
  const Icon = notConfigured ? Unplug : apiErr?.code === "network_error" ? WifiOff : apiErr?.code === "database_unavailable" ? DatabaseZap : AlertTriangle;
  const message = notConfigured
    ? "This deployment is not connected to a live AeroPulse API, so no operational data is shown — nothing is simulated in its place."
    : apiErr?.code === "network_error"
      ? "The AeroPulse API could not be reached. Live data is unavailable right now."
      : apiErr?.code === "database_unavailable"
        ? "The database is temporarily unavailable. No data is shown rather than outdated figures."
        : apiErr?.code === "contract_mismatch"
          ? "The API returned data in an unexpected format, so it was not displayed."
          : apiErr?.message ?? "Something went wrong while loading this data.";
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-ap-line p-8 text-center", className)}>
      <Icon className="size-6 text-ap-crit" aria-hidden />
      <div>
        <p className="font-medium text-ap-text">{notConfigured ? "Live API not connected" : (title ?? "Data unavailable")}</p>
        <p className="mt-1 max-w-md text-sm text-ap-text-2">{message}</p>
      </div>
      {onRetry && !notConfigured && (
        <Button size="sm" variant="outline" onClick={onRetry} className="gap-1.5">
          <RotateCw className="size-3.5" /> Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, children, icon, className }: { title: string; children?: ReactNode; icon?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-ap-line p-8 text-center", className)}>
      {icon ?? <Inbox className="size-6 text-ap-text-3" aria-hidden />}
      <p className="font-medium text-ap-text">{title}</p>
      {children && <div className="max-w-md text-sm text-ap-text-2">{children}</div>}
    </div>
  );
}

export function StaleNotice({ children }: { children: ReactNode }) {
  return (
    <div role="status" className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" style={{ borderColor: "color-mix(in srgb, var(--ap-warn) 35%, transparent)", background: "color-mix(in srgb, var(--ap-warn) 8%, transparent)", color: "var(--ap-warn)" }}>
      <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="text-ap-text-2">{children}</div>
    </div>
  );
}

export function PanelSkeleton({ className, lines = 3 }: { className?: string; lines?: number }) {
  return (
    <div className={cn("ap-panel space-y-3 p-5", className)} aria-busy="true" aria-label="Loading">
      <Skeleton className="h-4 w-1/3 bg-white/5" />
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className="h-3 bg-white/5" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}
