import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function PageContainer({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-[1440px] px-4 sm:px-6", className)}>{children}</div>;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 pb-6 pt-8 sm:pt-10 md:flex-row md:items-end md:justify-between">
      <div className="space-y-2">
        {eyebrow && <p className="ap-eyebrow">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight text-ap-text sm:text-3xl">{title}</h1>
        {description && <p className="max-w-2xl text-sm leading-relaxed text-ap-text-2 sm:text-[15px]">{description}</p>}
        {meta && <div className="pt-1">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({
  title,
  description,
  children,
  className,
  actions,
  bodyClassName,
  id,
}: {
  title?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
  bodyClassName?: string;
  id?: string;
}) {
  return (
    <section id={id} className={cn("ap-panel flex min-w-0 flex-col", className)} aria-label={typeof title === "string" ? title : undefined}>
      {(title || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-4 sm:px-5">
          <div>
            {title && <h2 className="text-sm font-semibold text-ap-text">{title}</h2>}
            {description && <p className="mt-0.5 text-xs leading-relaxed text-ap-text-3">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className={cn("min-w-0 flex-1 p-4 sm:p-5", bodyClassName)}>{children}</div>
    </section>
  );
}
