// Converts public-domain boundary data (US Census via us-atlas, Natural Earth via
// world-atlas) into small GeoJSON files used as the custom MapLibre basemap.
// Run: node scripts/build-geo.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { feature, mesh } from "topojson-client";

const require = createRequire(import.meta.url);
const round = (geom) => JSON.parse(JSON.stringify(geom, (_, v) => (typeof v === "number" ? Math.round(v * 1e3) / 1e3 : v)));

const states = JSON.parse(readFileSync(require.resolve("us-atlas/states-10m.json"), "utf8"));
const nation = feature(states, states.objects.nation);
const stateLines = mesh(states, states.objects.states, (a, b) => a !== b);
writeFileSync("public/geo/us-nation.json", JSON.stringify(round(nation)));
writeFileSync("public/geo/us-state-lines.json", JSON.stringify(round(stateLines)));

const world = JSON.parse(readFileSync(require.resolve("world-atlas/land-110m.json"), "utf8"));
const land = feature(world, world.objects.land);
writeFileSync("public/geo/world-land.json", JSON.stringify(round(land)));
console.log("geo written");
