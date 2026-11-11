import { Unplug } from "lucide-react";

import { API_CONFIGURED } from "@/lib/api/client";

/** Shown on deployments built without NEXT_PUBLIC_API_BASE_URL. */
export function ConnectionNotice() {
  if (API_CONFIGURED) return null;
  return (
    <div role="status" className="border-b border-ap-line bg-ap-surface/70">
      <p className="mx-auto flex max-w-[1440px] items-start gap-2 px-4 py-2 text-xs text-ap-text-2 sm:px-6">
        <Unplug className="mt-0.5 size-3.5 shrink-0 text-ap-warn" aria-hidden />
        <span>
          Front-end preview: this deployment is not connected to the AeroPulse data API, so live panels show their
          unavailable states instead of data.{" "}
          <a
            className="text-ap-accent underline underline-offset-2"
            href="https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence#screenshots"
            target="_blank"
            rel="noreferrer"
          >
            Screenshots of the running system
          </a>{" "}
          ·{" "}
          <a
            className="text-ap-accent underline underline-offset-2"
            href="https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence#local-installation"
            target="_blank"
            rel="noreferrer"
          >
            run it locally
          </a>
        </span>
      </p>
    </div>
  );
}
