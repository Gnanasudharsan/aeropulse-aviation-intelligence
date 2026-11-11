"use client";

import type { EChartsOption } from "echarts";

import { axisStyle, EChart } from "@/components/charts/echart";
import type { WeatherObservation } from "@/lib/api/schemas";
import { HEX } from "@/lib/domain";
import { formatUtc } from "@/lib/format";

/** Observation-level charts. Separate charts per unit — never a dual axis. */
export function ObservationCharts({ observations }: { observations: WeatherObservation[] }) {
  const obs = [...observations].sort((a, b) => a.observed_at.localeCompare(b.observed_at));
  const t = (o: WeatherObservation) => o.observed_at;
  const time = { type: "time" as const, ...axisStyle, splitLine: { show: false } };

  const temp: EChartsOption = {
    xAxis: time,
    yAxis: { type: "value", name: "°C", scale: true, ...axisStyle },
    legend: { show: true, ...{ top: 0, right: 64 } },
    series: [
      { name: "Temperature", type: "line", showSymbol: false, lineStyle: { width: 2, color: HEX.accent }, itemStyle: { color: HEX.accent }, data: obs.map((o) => [t(o), o.temperature_c]) },
      { name: "Dew point", type: "line", showSymbol: false, lineStyle: { width: 2, color: HEX.series[2] }, itemStyle: { color: HEX.series[2] }, data: obs.map((o) => [t(o), o.dewpoint_c]) },
    ],
  };
  const wind: EChartsOption = {
    xAxis: time,
    yAxis: { type: "value", name: "kt", min: 0, ...axisStyle },
    legend: { show: true, top: 0, right: 64 },
    series: [
      { name: "Sustained", type: "line", step: "end", showSymbol: false, lineStyle: { width: 2, color: HEX.accent }, itemStyle: { color: HEX.accent }, areaStyle: { color: "rgba(62,212,232,0.08)" }, data: obs.map((o) => [t(o), o.wind_speed_kt]) },
      { name: "Gust", type: "scatter", symbolSize: 8, itemStyle: { color: HEX.warn, borderColor: HEX.surface, borderWidth: 2 }, data: obs.filter((o) => o.wind_gust_kt).map((o) => [t(o), o.wind_gust_kt]) },
    ],
  };
  const vis: EChartsOption = {
    xAxis: time,
    yAxis: { type: "value", name: "SM", min: 0, ...axisStyle },
    series: [
      {
        name: "Visibility",
        type: "line",
        step: "end",
        showSymbol: false,
        lineStyle: { width: 2, color: HEX.mvfr },
        itemStyle: { color: HEX.mvfr },
        data: obs.map((o) => [t(o), o.visibility_sm]),
        markArea: {
          silent: true,
          itemStyle: { opacity: 0.08 },
          data: [
            [{ yAxis: 0, itemStyle: { color: HEX.lifr } }, { yAxis: 1 }],
            [{ yAxis: 1, itemStyle: { color: HEX.ifr } }, { yAxis: 3 }],
          ],
        },
      },
    ],
  };
  const table = {
    columns: ["Observed (UTC)", "Cat", "Temp °C", "Dew °C", "Wind kt", "Gust kt", "Vis SM", "Ceiling ft"],
    rows: [...obs].reverse().map((o) => [formatUtc(o.observed_at), o.flight_category, o.temperature_c, o.dewpoint_c, o.wind_speed_kt, o.wind_gust_kt, o.visibility_sm, o.ceiling_ft]),
  };
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div>
        <h3 className="mb-1 text-xs font-medium text-ap-text-2">Temperature & dew point</h3>
        <EChart option={temp} height={200} ariaLabel={`Temperature and dew point over ${obs.length} observations`} table={table} />
      </div>
      <div>
        <h3 className="mb-1 text-xs font-medium text-ap-text-2">Wind speed & gusts</h3>
        <EChart option={wind} height={200} ariaLabel="Sustained wind and gusts in knots" table={table} />
      </div>
      <div>
        <h3 className="mb-1 text-xs font-medium text-ap-text-2">Visibility <span className="text-ap-text-3">(shaded: IFR &lt; 3 SM, LIFR &lt; 1 SM)</span></h3>
        <EChart option={vis} height={200} ariaLabel="Visibility in statute miles" table={table} />
      </div>
    </div>
  );
}
