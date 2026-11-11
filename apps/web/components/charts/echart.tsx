"use client";

import type { EChartsOption } from "echarts";
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import ReactEChartsCore from "echarts-for-react/lib/core";
import { Table2 } from "lucide-react";
import { useState, type ReactNode } from "react";

import { HEX } from "@/lib/domain";
import { cn } from "@/lib/utils";

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  ScatterChart,
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  DataZoomComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

/** Shared recessive axis / grid / tooltip styling (thin marks, quiet chrome). */
export const baseOption: EChartsOption = {
  backgroundColor: "transparent",
  textStyle: { fontFamily: "var(--font-geist-sans), system-ui, sans-serif", color: HEX.text2 },
  animationDuration: 500,
  grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
  tooltip: {
    trigger: "axis",
    backgroundColor: "#12203a",
    borderColor: HEX.lineStrong,
    textStyle: { color: HEX.text, fontSize: 12 },
    axisPointer: { type: "line", lineStyle: { color: HEX.lineStrong } },
    confine: true,
  },
  legend: { top: 0, right: 0, textStyle: { color: HEX.text2, fontSize: 11 }, itemWidth: 12, itemHeight: 3, icon: "rect" },
};

export const axisStyle = {
  axisLine: { lineStyle: { color: HEX.lineStrong } },
  axisTick: { show: false },
  axisLabel: { color: HEX.text3, fontSize: 11 },
  splitLine: { lineStyle: { color: HEX.line } },
  nameTextStyle: { color: HEX.text3, fontSize: 11 },
} as const;

export interface TableView {
  columns: string[];
  rows: (string | number | null)[][];
}

/**
 * ECharts canvas with an accessible alternative: every chart carries an aria-label
 * summary and a toggleable data table.
 */
export function EChart({
  option,
  height = 260,
  ariaLabel,
  table,
  className,
  actions,
}: {
  option: EChartsOption;
  height?: number;
  ariaLabel: string;
  table?: TableView;
  className?: string;
  actions?: ReactNode;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <div className={cn("relative", className)}>
      {(table || actions) && (
        <div className="absolute right-0 top-0 z-10 flex items-center gap-1">
          {actions}
          {table && (
            <button
              type="button"
              onClick={() => setShowTable((v) => !v)}
              className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-ap-text-3 hover:bg-white/5 hover:text-ap-text"
              aria-pressed={showTable}
            >
              <Table2 className="size-3.5" aria-hidden /> {showTable ? "Chart" : "Table"}
            </button>
          )}
        </div>
      )}
      {showTable && table ? (
        <div className="max-h-[360px] overflow-auto rounded-lg border border-ap-line" style={{ minHeight: height }}>
          <table className="w-full text-left text-xs">
            <caption className="sr-only">{ariaLabel}</caption>
            <thead className="sticky top-0 bg-ap-surface-2 text-ap-text-2">
              <tr>
                {table.columns.map((c) => (
                  <th key={c} scope="col" className="px-3 py-2 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular text-ap-text">
              {table.rows.map((r, i) => (
                <tr key={i} className="border-t border-ap-line">
                  {r.map((v, j) => (
                    <td key={j} className="px-3 py-1.5">
                      {v ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div role="img" aria-label={ariaLabel}>
          <ReactEChartsCore
            echarts={echarts}
            option={{ ...baseOption, ...option }}
            style={{ height, width: "100%" }}
            notMerge
            lazyUpdate
            opts={{ renderer: "canvas" }}
          />
        </div>
      )}
    </div>
  );
}
