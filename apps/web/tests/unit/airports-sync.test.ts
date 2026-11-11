import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { MONITORED_AIRPORTS } from "@/lib/airports";

describe("monitored airports", () => {
  it("match the API seed file", () => {
    const csv = readFileSync(resolve(process.cwd(), "../../services/api/app/data/airports.csv"), "utf8");
    const codes = csv.trim().split("\n").slice(1).map((l) => l.split(",")[0]);
    expect([...MONITORED_AIRPORTS]).toEqual(codes);
  });
});
