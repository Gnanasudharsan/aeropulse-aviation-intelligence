import { ExternalLink, ImageIcon, Lock } from "lucide-react";
import Image from "next/image";

import { Panel } from "@/components/layout/page";

const REPORT_URL = process.env.NEXT_PUBLIC_POWERBI_REPORT_URL ?? "";
/** Secure link to the published report in the owner's Power BI workspace (sign-in + access required). */
const SECURE_REPORT_LINK =
  "https://app.powerbi.com/groups/23d536df-4aa2-4bef-8298-894694515e72/reports/3c20ba41-0c12-4fd1-9656-bc0fe5cfd677";
const REPO = "https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence/tree/main/analytics/powerbi";
const CAPTURED = "2026-11-11";

const PAGES = [
  { file: "executive", title: "Executive Performance Overview" },
  { file: "comparison", title: "Airport Comparison" },
  { file: "drivers", title: "Delay Drivers" },
  { file: "temporal", title: "Seasonal and Temporal Insights" },
];

/** Only https URLs on Microsoft's Power BI hosts are embedded. */
export function isEmbeddableReportUrl(url: string): boolean {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && /(^|\.)powerbi\.com$/.test(u.hostname);
  } catch {
    return false;
  }
}

export function PowerBiPanel() {
  if (REPORT_URL && isEmbeddableReportUrl(REPORT_URL)) {
    return (
      <Panel title="Power BI report" description="Embedded Power BI report built on the AeroPulse BTS star schema." bodyClassName="p-0 sm:p-0">
        <div className="aspect-[16/10] w-full overflow-hidden rounded-b-xl bg-ap-bg">
          <iframe
            title="AeroPulse Power BI airport performance report"
            src={REPORT_URL}
            className="h-full w-full border-0"
            allowFullScreen
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        </div>
      </Panel>
    );
  }
  return (
    <Panel
      title="Power BI report — published in the Power BI service"
      description={`The report is live in a Power BI workspace (refreshing from the same BTS star schema). Public "Publish to web" embedding is disabled by the account's organization, so the pages below are screenshots captured from the Power BI service on ${CAPTURED} — not interactive. The charts further down are AeroPulse's own interactive views of the same data.`}
      actions={
        <div className="flex flex-wrap gap-3 text-xs">
          <a href={SECURE_REPORT_LINK} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ap-accent hover:underline">
            <Lock className="size-3" aria-hidden /> Open interactive report (access required) <ExternalLink className="size-3" aria-hidden />
          </a>
          <a href={REPO} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ap-accent hover:underline">
            Power BI project on GitHub <ExternalLink className="size-3" aria-hidden />
          </a>
        </div>
      }
    >
      <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {PAGES.map((p) => (
          <li key={p.file}>
            <figure className="overflow-hidden rounded-lg border border-ap-line bg-ap-bg">
              <a href={`/powerbi/${p.file}.jpg`} target="_blank" rel="noreferrer" aria-label={`Open full-size screenshot: ${p.title}`}>
                <Image
                  src={`/powerbi/${p.file}.jpg`}
                  alt={`Screenshot of the Power BI report page "${p.title}" (captured ${CAPTURED})`}
                  width={800}
                  height={600}
                  className="h-auto w-full"
                  sizes="(min-width: 768px) 50vw, 100vw"
                />
              </a>
              <figcaption className="flex items-center gap-1.5 px-3 py-2 text-xs text-ap-text-2">
                <ImageIcon className="size-3.5 shrink-0 text-ap-text-3" aria-hidden />
                {p.title} <span className="text-ap-text-3">· screenshot, {CAPTURED}</span>
              </figcaption>
            </figure>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
