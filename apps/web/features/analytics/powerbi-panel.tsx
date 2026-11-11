import { BarChart3, CheckCircle2, CircleDashed, ExternalLink } from "lucide-react";

import { Panel } from "@/components/layout/page";

const REPORT_URL = process.env.NEXT_PUBLIC_POWERBI_REPORT_URL ?? "";
const REPO = "https://github.com/Gnanasudharsan/aeropulse-aviation-intelligence/tree/main";

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
  const done = [
    "Complete report: 4 pages, 33 visuals, AeroPulse theme (Power BI Project / PBIR)",
    "Semantic model: 7 tables, 10 relationships, 46 DAX measures (TMDL)",
    "Validated against Microsoft's official report schemas, plus model-integrity checks in CI",
    "Data source: public Parquet star schema — refreshable in the Power BI service",
  ];
  const todo = [
    "Open AeroPulse.pbip in Power BI Desktop, or upload it to a Power BI workspace",
    "Publish to the owner's Power BI workspace (Microsoft work/school account)",
    "File → Embed report → Publish to web, then set NEXT_PUBLIC_POWERBI_REPORT_URL",
  ];
  return (
    <Panel
      title="Power BI report — built, awaiting publication"
      description="The Power BI report is built and validated, but it has not been published to Power BI yet, so nothing is embedded here. The analytics below are AeroPulse's own interactive charts over the same data model — they are not Power BI."
    >
      <div className="grid gap-6 md:grid-cols-[auto_1fr_1fr]">
        <BarChart3 className="size-10 text-ap-accent" aria-hidden />
        <div>
          <p className="mb-2 text-xs font-medium text-ap-text-2">Prepared in the repository</p>
          <ul className="space-y-1.5 text-sm text-ap-text-2">
            {done.map((d) => (
              <li key={d} className="flex gap-2"><CheckCircle2 className="mt-0.5 size-4 shrink-0 text-ap-ok" aria-hidden />{d}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-2 text-xs font-medium text-ap-text-2">Requires the owner&apos;s Microsoft account</p>
          <ul className="space-y-1.5 text-sm text-ap-text-2">
            {todo.map((d) => (
              <li key={d} className="flex gap-2"><CircleDashed className="mt-0.5 size-4 shrink-0 text-ap-text-3" aria-hidden />{d}</li>
            ))}
          </ul>
          <a href={`${REPO}/analytics/powerbi`} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs text-ap-accent hover:underline">
            Power BI artifacts on GitHub <ExternalLink className="size-3" aria-hidden />
          </a>
        </div>
      </div>
    </Panel>
  );
}
