"use client";

import { animate, useReducedMotion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function AnimatedNumber({ value, format = (n) => Math.round(n).toLocaleString("en-US") }: { value: number; format?: (n: number) => string }) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const prev = useRef(value);
  useEffect(() => {
    if (reduce || prev.current === value) {
      prev.current = value;
      setDisplay(value);
      return;
    }
    const controls = animate(prev.current, value, {
      duration: 0.6,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: setDisplay,
    });
    prev.current = value;
    return () => controls.stop();
  }, [value, reduce]);
  return <span className="tabular">{format(display)}</span>;
}

export function KpiTile({
  label,
  value,
  icon: Icon,
  tone = "neutral",
  hint,
  footer,
  loading,
  className,
}: {
  label: string;
  value: number | null;
  icon?: LucideIcon;
  tone?: "neutral" | "accent" | "ok" | "warn" | "crit";
  hint?: string;
  footer?: ReactNode;
  loading?: boolean;
  className?: string;
}) {
  const toneColor = {
    neutral: "var(--ap-text-2)",
    accent: "var(--ap-accent)",
    ok: "var(--ap-ok)",
    warn: "var(--ap-warn)",
    crit: "var(--ap-crit)",
  }[tone];
  return (
    <div className={cn("ap-panel group relative overflow-hidden p-4 sm:p-5", className)}>
      <div
        className="pointer-events-none absolute -right-10 -top-10 size-28 rounded-full opacity-[0.07] blur-2xl transition-opacity group-hover:opacity-[0.12]"
        style={{ background: toneColor }}
        aria-hidden
      />
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] text-ap-text-2" title={hint}>
          {label}
        </p>
        {Icon && <Icon className="size-4 shrink-0" style={{ color: toneColor }} aria-hidden />}
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-ap-text sm:text-[34px]">
        {loading || value === null ? <Skeleton className="h-9 w-16 bg-white/5" /> : <AnimatedNumber value={value} />}
      </div>
      {footer && <div className="mt-2 text-xs text-ap-text-3">{footer}</div>}
    </div>
  );
}
