# Power BI — AeroPulse Airport Performance

| Artifact | Status |
|---|---|
| `data/*.parquet` — star schema exported from PostgreSQL by the BTS pipeline (24 months) | ✅ Real BTS data |
| `AeroPulse.SemanticModel/` — TMDL: 7 tables (incl. `DimDirection`), 10 relationships, 46 DAX measures; Power Query reads the Parquet files from their public GitHub URLs (refreshable in the Power BI service without a gateway) | ✅ Generated · ✅ integrity-checked |
| `AeroPulse.Report/` — enhanced report format (PBIR): 4 pages, 33 visuals, dark AeroPulse theme, default arrivals filter | ✅ Generated · ✅ validated against Microsoft's official JSON schemas |
| `AeroPulse.pbip` — project entry point | ✅ Generated |
| `../dax/measures.dax` — measures as a reviewable script | ✅ Generated |
| Opened in Power BI Desktop / DAX evaluated by the engine | ⚠️ Not yet — requires Power BI Desktop (Windows) or the Power BI service |
| Published / "Publish to web" URL | ❌ Requires the owner's Microsoft (work/school) account |

`validate_pbip.py` (also run in CI) checks: every report file against the Microsoft schema it
declares; the theme against Microsoft's report-theme schema; every visual/filter field, DAX
`[Measure]`/`Table[Column]` reference, relationship (incl. matching data types) and sort-by
column against the TMDL model; and that every Parquet URL is reachable with columns matching
the model. It does **not** run Microsoft's Analysis Services engine, so DAX is not evaluated
until the report is opened in Power BI.

## Report pages

1. **Executive Performance Overview** — direction / date range / state slicers; cards for
   flights, on-time %, YoY change (pts), cancellation rate, average delay, data-through;
   monthly on-time trend vs. all monitored airports; airports ranked by on-time %.
2. **Airport Comparison** — scorecard table (flights, on-time, cancellations, delay, rank),
   airport × month on-time matrix, delay-distribution columns.
3. **Delay Drivers** — weather/NAS share cards, 100% stacked cause mix by airport,
   cancellations by cause, weather and NAS minutes by month.
4. **Seasonal and Temporal Insights** — on-time by calendar month × year, by weekday, by
   scheduled local hour, and by reporting carrier.

## Publish without Windows (Power BI Git integration, browser only)

Each item folder carries a `.platform` file (Fabric Git format), so a Power BI workspace can
create the semantic model and report straight from this repository:

1. app.powerbi.com → **Workspaces → New workspace** (license mode: *Fabric trial* or
   *Premium per user* — Git integration needs one of these).
2. Workspace **settings → Git integration → GitHub** → connect your GitHub account → repository
   `aeropulse-aviation-intelligence`, branch `main`, folder `analytics/powerbi` → **Connect and sync**.
3. Semantic model **AeroPulse Airport Performance → Settings → Data source credentials** → each
   web source: *Anonymous*, privacy *Public* → **Refresh now**.
4. Open the report → **File → Embed report → Publish to web (public)** (needs the tenant setting
   enabled by your admin) → copy the `https://app.powerbi.com/view?r=…` URL into
   `NEXT_PUBLIC_POWERBI_REPORT_URL`.

## Finish the report (Windows, Power BI Desktop)

1. Clone the repository (or copy `analytics/powerbi/`) to a Windows machine.
2. Open `AeroPulse.pbip` in Power BI Desktop (Developer Mode / PBIP support enabled).
3. **Refresh.** Data loads from the public GitHub URLs (parameter `DataUrl`); no local path is needed.
4. Verify: `Total Flights` for the full period should equal
   `SELECT sum(flights) FROM airport_performance_daily WHERE direction = 'arrival'` in
   PostgreSQL (the API's `/api/v1/analytics/overview?start=…&end=…` returns the same figures).
5. Review the four pages (already built) and adjust formatting if desired.
6. Save (PBIP keeps everything as text; commit the changes).

## Refresh

The Parquet files are regenerated monthly by the BTS pipeline and committed. The data source
is anonymous web access to those public files, so scheduled refresh in the Service needs no
gateway. The model deliberately does **not** connect to the live operational
PostgreSQL database: Publish-to-web cannot query a private database, and live operations are
served by the web app.

## Publishing and embedding — options evaluated

| Option | Licensing | Auth for viewers | Suitable for a public portfolio site |
|---|---|---|---|
| **Publish to web** | Power BI Pro (or trial) and tenant setting enabled by an admin | None — public | ✅ Yes (data is public BTS data). Not for confidential data. |
| Secure embed (`/reportEmbed`) | Pro/PPU per viewer | Microsoft Entra sign-in | ❌ Visitors would need accounts |
| Power BI Embedded (app-owns-data) | Azure A-SKU / Fabric capacity (paid) + service principal | App token minted by our backend | ✅ but incurs Azure cost — requires explicit approval |

**Recommended:** Publish to web, then set `NEXT_PUBLIC_POWERBI_REPORT_URL` (e.g.
`https://app.powerbi.com/view?r=…`) in the web app's environment. The `/analytics` page embeds
only `https://*.powerbi.com` URLs and otherwise shows the integration state, never a
screenshot.
