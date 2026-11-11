import { cn } from "@/lib/utils";

/** AeroPulse mark: a heading chevron riding a pulse line. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn("size-7", className)}>
      <defs>
        <linearGradient id="ap-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3ED4E8" />
          <stop offset="1" stopColor="#49DBAA" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="9" fill="#16263E" stroke="rgba(168,190,211,0.25)" />
      <path
        d="M5 19h5l2.5-6 4 11 3-8 1.6 3H27"
        fill="none"
        stroke="url(#ap-g)"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M20 7.5l4.5 2.2-4.5 2.2" fill="none" stroke="#3ED4E8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-tight text-ap-text">
        Aero<span className="text-ap-accent">Pulse</span>
      </span>
    </span>
  );
}
