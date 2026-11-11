import Link from "next/link";

import { Logo } from "@/components/brand/logo";

import { NAV_ITEMS } from "./nav-config";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-ap-line bg-ap-bg-elevated/60">
      <div className="mx-auto grid max-w-[1440px] gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="space-y-3">
          <Logo />
          <p className="max-w-sm text-sm leading-relaxed text-ap-text-2">
            Intelligence in Motion. Live FAA NAS Status and NOAA Aviation Weather Center data for 50 major U.S.
            airports, with historical performance analytics.
          </p>
          <p className="max-w-sm text-xs leading-relaxed text-ap-text-3">
            Not for operational or flight-planning use. Always consult official FAA and NWS sources.
          </p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-2 text-sm">
          {NAV_ITEMS.map((item) => (
            <Link key={item.href} href={item.href} className="text-ap-text-2 hover:text-ap-text">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="space-y-2 text-sm text-ap-text-2">
          <p className="ap-eyebrow">Data sources</p>
          <a className="block hover:text-ap-text" href="https://nasstatus.faa.gov/" target="_blank" rel="noreferrer">
            FAA NAS Status
          </a>
          <a className="block hover:text-ap-text" href="https://aviationweather.gov/data/api/" target="_blank" rel="noreferrer">
            NOAA Aviation Weather Center
          </a>
          <a className="block hover:text-ap-text" href="https://www.transtats.bts.gov/" target="_blank" rel="noreferrer">
            Bureau of Transportation Statistics
          </a>
          <a
            className="block hover:text-ap-text"
            href="https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence"
            target="_blank"
            rel="noreferrer"
          >
            Source on GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
