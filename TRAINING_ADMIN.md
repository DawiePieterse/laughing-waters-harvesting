# Admin — Training Guide

For farm office staff managing workers, wages, reports, and settings.

---

## Signing in

Open the Admin app, enter your username and password, and tap **Sign
in**. If you're on a brand-new setup, the default login is username
`admin`, password `ChangeMe123!` — change that immediately under
**Settings → Change admin password** once you're in.

Once signed in, the top bar shows the farm name, today's date/time, and
current weather. Six tabs run across the top: **Dashboard**, **Analysis**,
**Master Data**, **Payments**, **Reports**, **Settings**.

---

## Dashboard — your daily overview

This is where you check how the harvest is moving.

1. Set the **Farm/Supplier** filter (or leave it on "All") and a
   **Period start/end** date range — or just tap **Today**, **This
   Week**, or **Season** for a quick preset (whichever one matches the
   current dates stays highlighted). Everything below refreshes the
   moment any filter changes — there's no separate Refresh button.
2. The KPI cards along the top summarize the period: teams/workers/
   blocks active, total kg and crates, averages, and a breakdown of
   Harvesting / In Transit / Received.
3. Below that, five expandable lists give the detail behind those
   numbers:
   - **Harvesting** — loads still being picked in the field.
   - **In Transit** — dispatched, not yet received at the pack house.
   - **Received** — already checked in; tap a row to open its crates.
   - **Workers** — per-worker totals for the period.
   - **Blocks** — per-block totals for the period, including yield per
     hectare.

Tap any list's header to expand or collapse it.

**Harvesting and In Transit use the same green/yellow/red color coding
as the Pack House screen** — red means a load has been waiting too long
and needs attention.

### Correcting a captured crate

Tapping a row in the **Received** list opens that load's crates —
time, block, worker, weight, deduction, and net kg — each with an
**Edit** link. Use this to fix a mistake made at capture time (wrong
worker scanned, mistyped weight): you can change the **Worker**,
**Weight (kg)**, and **Deduction (kg)** on that crate, and the lot's
totals recalculate immediately everywhere they're shown.

If wages were already calculated for the affected period, a warning
banner says so — re-run **Calculate Wages** in Payments for that period
afterward, since a correction doesn't rewrite a wage sheet that's
already been run.

---

## Analysis — this season vs. history

This is where you check how the season is doing against 2020–2025
historical records, not just today.

1. The KPI cards show **Season to Date** kg, and **vs 5-Yr Average Pace** —
   how far ahead or behind the season is running compared to the
   historical average at the same point (green = ahead, red = behind).
2. **Season Pace** — a chart of cumulative kg picked so far, starting
   1 August (when picking actually begins). Each historical year has its
   own color, the 5-year average is a dashed black line, and this season
   is highlighted in navy.
3. **Per-Block Yield** — a chart and table comparing each block's kg/ha
   (or kg/tree — switch with the dropdown, both chart and table follow) this
   season against its own historical average. A dashed red line marks the
   farm-wide average for the selected metric. The **vs Average** column is
   green or red so under-performing blocks stand out.
4. **Harvest Volume by Block and Season** — a bubble chart, one bubble per
   block per season sized by kg, blocks ranked top-to-bottom by total
   volume, with a **Total Harvest** bar alongside each block's row.
5. **Yield per Tree/Hectare by Block and Season** — a heatmap of every
   block against every season (switch metric with the dropdown), so you
   can scan a row for one block's history or a column for how a whole
   season compared.
6. **Variety Performance Over Time** — one stacked bar per season, split
   by variety color, showing **average kg per tree**. Use the dropdown to
   filter down to a single variety (starts on **All Varieties**).
7. **Harvest Season Length** — one bar per season spanning first pick to
   last pick, labelled with the span in days and how many of those days
   actually had picking (e.g. "118d span, 46 pick days"). The current
   season gets a row too, shown as "No picking yet" until it starts.
8. **Monthly Harvest Volume** — a heatmap of kg picked by month for every
   season (latest season at the top), each cell also showing that month's
   share of the season total. A **Total Kg (100%)** column after December
   shows each season's grand total, shaded blue on its own scale so the
   biggest season stands out.

Every chart has a small <i class="fa-solid fa-file-pdf"></i> button in its
top-right corner to download it as a one-page PDF.

A few blocks (8a/8b, 10a/10b, 17a/17b, 19a/19b) didn't exist separately
before this app — their historical figures are split from one combined
record by hectares, so they're an estimate. Those rows carry a small info
icon in the Per-Block Yield table as a reminder.

---

## Master Data — the farm's reference information

Five subtabs: **Workers**, **Teams**, **Blocks**, **Devices**,
**Suppliers**.

### Adding a worker

1. Master Data → Workers → **+ Add Worker**.
2. Fill in Employee Number, First Name, Last Name, SA ID Number, Bank,
   Account Number, WhatsApp Number, and which Farm/Supplier they belong
   to (leave as "(none)" for your own farm's workers).
3. Optionally take or upload a **Photo** right there.
4. Make sure **Active** is ticked, then **Save**.

### Printing worker badges

Workers scan a QR badge to identify themselves in the Field app — there's
no other way to select a worker, so every active picker needs one.

1. Master Data → Workers.
2. Use **Print Badges (filtered)** to print everyone currently shown in
   the table, **Print Badges (selected)** for just the ones you've
   ticked, or **Print Badges (all)** for the whole list.

Reprint a badge any time a worker's is lost, damaged, or a new worker
joins.

### Teams, Blocks, Devices, Suppliers

- **Teams** — ID (e.g. "A"), name, induna. Add/edit with the same
  pattern as Workers.
- **Blocks** — each block's variety, tree count, hectares, and
  active/inactive. Use **Export .xlsx** / **Import** to bulk-edit many
  blocks at once from a spreadsheet rather than one at a time. Tick
  **"Replace all"** before importing only when the file is meant to
  completely replace the block list (e.g. after re-dividing a block) —
  it retires any block not in the file instead of leaving it behind.
- **Devices** — every phone/tablet/PC that can access the app must be
  added here first, with its role (Field, Pack House, or Admin), station
  name, and team. A device shows "Unknown device id" until you've added
  it here.
- **Suppliers** — other farms that use your pack house, with their
  contact details and packing rate. Their loads stay separate from your
  own harvest everywhere in the Dashboard and Reports.

---

## Payments — calculating wages

1. Payments tab.
2. Set the Farm/Supplier filter and date range (or Today/This Week/
   Season).
3. Tap **Calculate Wages** to see each worker's kg and amount due for
   that period, based on the current rate.
4. Tap **Export Wage Sheet** to download it for payroll.

---

## Reports — downloadable spreadsheets

1. Reports tab.
2. Set the date range and, if needed, a Farm/Supplier filter — **both
   dates must be filled in** or the report won't generate.
3. Tap the report you want. Each one downloads as an `.xlsx` file:

| Report | What it contains |
|---|---|
| Daily Harvest Summary | Crates/kg by block and team for one day (always just the start date — a wider range gets flagged "Daily report only") |
| Lot & Receiving Report | Every load dispatched in the range, with receiving detail |
| Plukstrokies / Picking Notes | One row per dispatched load — block(s), crates sent vs. received, driver, condition, notes, weather |
| Span Pluklys / Team Picking List | One row per team per day, matching the paper picking slip — blocks picked and loads dispatched that day |
| Daaglikse Oesdata / Daily Harvest Data | Kg by block vs. date over a range, with block and day totals |
| Harvesting List | Loads still being picked |
| In Transit List | Dispatched but not yet received |
| Pakhuis Ontvangstes / Pack House Receivables | Already received loads, matching the paper receiving slip — date/time, block, and rejected kg included |
| Worker Harvest Report | Per-worker crates/kg/amount due |
| Lietsjie Lone / Litchi Wages | Per-worker crates harvested vs. crates received per day — flags fruit that never made it off its lot before wages are paid |
| Block Harvest Report | Per-block crates/kg/averages |
| Historical Harvest Data | The full multi-year block x date pivot, 2020 through the current season, in one file. Ignores the date range above — there's only ever one. |

---

## Settings

- **Data Backup** — **Backup Now** creates an immediate downloadable
  backup; one also happens automatically every night at 02:00 (only if
  the server is running at the time). Download backups regularly and
  keep a copy somewhere off the server — the last 14 are kept
  automatically, which protects against mistakes but not a hardware
  failure.
- **Farm settings** — farm name, location, current harvest season year,
  the green→yellow and yellow→red timing thresholds used for the
  color-coded queues, and GPS coordinates (enables the weather widget).
- **Harvest rate** — the current rate per kg used for wage calculations.
- **Change admin password** — do this immediately after first login if
  you haven't already.
- **Owner View** — a read-only dashboard link for an owner or other
  interested party who just wants to check progress, no login needed.
  It shows the same Workers/Blocks breakdown as the full Dashboard, just
  without amount-due wage figures. Tap **Copy** to grab the link and send
  it directly to them, or **Regenerate Link** if it was ever shared more
  widely than intended — that immediately breaks the old link.

---

## If something looks wrong

- **"Could not generate report" / a toast about picking dates first** —
  make sure both the start and end date are filled in before tapping a
  report.
- **A device shows "Unknown device id"** — it hasn't been added in
  Master Data → Devices yet; add it there first. Once added (and marked
  active) it appears in the dropdown on that device's setup screen as
  soon as the page is reloaded.
- **A screen shows an older version number than you expect** (top
  corner, e.g. "v1.1") — fully close and reopen the app (not just switch
  away from it) to pick up the latest update. Each screen updates
  separately, so do this on every device, not just one.
- **An amber "Offline" bar appears** — the screen can't reach the server.
  Whatever is on screen stays put rather than blanking out, and refreshes
  itself once the connection is back. A brief drop does not sign you out;
  only a genuinely expired session does, and that says so.
- **Anything else unexpected** — a full page refresh often clears minor
  glitches; if it persists, note exactly what you were doing and check
  with whoever manages the server.
