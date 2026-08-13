# Owner View — Guide

A read-only way to check on harvest progress — no username/password,
nothing to remember.

---

## Opening your dashboard

You'll have been sent a link that looks like:

```
https://.../owner/?key=...
```

Open it in any browser, on any phone, tablet, or computer. That's the
whole login process — the long code at the end of the link *is* your
access, so there's no separate username/password to enter.

**Worth bookmarking it** (or adding it to your home screen) so you don't
need to dig up the link again next time.

### If you're checking this from off the farm

If you'll normally open this away from the farm itself (from home, an
office, etc.), you'll also need **Tailscale** installed and connected on
whatever device you use — ask the farm office to set this up for you
once, it's a one-time thing. The link's code proves you're allowed to
see the dashboard, but reaching the farm's server from outside its own
network needs Tailscale regardless — the two aren't the same thing. If
you're always on the farm's own Wi-Fi when you check, you can skip this.

If the link ever stops working, ask the farm office for a new one — see
"If something looks wrong" below.

---

## What you're looking at

At the top: the farm name, the current date/time, and today's weather.
Below that, two tabs — **Dashboard** (today's activity) and **Analysis**
(this season vs. 2020-2025 history) — covered in turn below.

### Dashboard tab

Below the header, a filter bar:
- **Farm / Supplier** — narrow the view to one farm/supplier, or leave it
  on "All farms / suppliers."
- **Period start / Period end** — the date range you're looking at, or
  tap **Today**, **This Week**, or **Season** for a quick preset (whichever
  one matches the current dates stays highlighted).

Changing any of these pulls fresh numbers straight away — there's no
separate Refresh button to look for.

Then the numbers themselves:

- **KPI cards** — teams/workers/blocks active, total kg and crates,
  averages, and a Harvesting/In Transit/Received breakdown, all for the
  selected date range.
- **Harvesting / In Transit / Received** — tap any of these to expand
  the actual list of loads. Harvesting and In Transit are color-coded:
  🟢 green (recent), 🟡 yellow (been a while), 🔴 red (waiting too
  long) — the same color scheme used throughout the farm's own app.
- **Workers** — tap to expand a per-worker breakdown: crates, kg, and
  average yield per crate for the period (no wage/amount-due figures —
  see "What this doesn't show" below).
- **Blocks** — tap to expand a per-block breakdown: crates, kg, and
  average yield per crate, per tree, and per hectare for the period.

### Analysis tab

The same Analysis tab the farm office sees in Admin - how this season is
doing against 2020-2025 history, not filtered by date range (it always
covers the full history plus whatever's been picked so far this season):

- **Season Pace** — cumulative kg picked so far, one line per year plus a
  5-year average, so you can see at a glance whether the season is running
  ahead or behind.
- **Per-Block Yield** — each block's yield this season against its own
  history (switch between kg/hectare and kg/tree), with a farm-wide
  average line and red/green coloring for under/over-performing blocks.
- **Harvest Volume by Block and Season** and **Yield per Tree/Hectare by
  Block and Season** — a bubble chart and a heatmap covering every block
  against every season at once.
- **Variety Performance Over Time** — average kg per tree by variety,
  season by season (filter to a single variety with the dropdown).
- **Harvest Season Length** — when each season started and ended, and how
  many of those days actually had picking.
- **Monthly Harvest Volume** — a heatmap of kg picked by month, with each
  season's grand total alongside.

Every chart has a small <i class="fa-solid fa-file-pdf"></i> button in its
top-right corner to download it as a one-page PDF, headed with the farm
name and the chart's title.

---

## What this doesn't show

This link is deliberately limited to progress information — it doesn't
show individual worker pay, contact details, or anything you could
change. There's no way to edit data from this view; it's read-only by
design. If you need more detail than this covers, ask the farm office
directly.

---

## If something looks wrong

- **The link shows "This link isn't valid"** — this is about the link
  itself, not your connection. It may have been regenerated (this happens
  if it needed to be revoked and reissued) or mistyped/cut off when it
  was shared with you. Ask the farm office for the current link.
- **An amber bar says you're offline** — this one *is* the connection.
  The page shows the last figures it saved for whatever date range/farm
  is selected, labeled with how old they are (e.g. *"Offline - showing
  figures from 12 min ago"*), rather than just freezing whatever happened
  to be on screen. If it's never loaded that particular combination
  before, it says so plainly instead of guessing. It updates itself once
  it can reach the farm again. Check **Tailscale** is connected (below).
- **Numbers look outdated** — drag down from the top of the page and let
  go, or double-check the date range at the top actually covers the
  period you're expecting (changing any filter also pulls fresh numbers
  automatically).
- **Nothing loads at all, and you're off the farm** — check that
  **Tailscale** is open and shows **"Connected"** first (see "If you're
  checking this from off the farm" above) - this is the most common
  cause. If Tailscale is connected and it still won't load, check your
  own internet connection, then let the farm office know if it persists.
