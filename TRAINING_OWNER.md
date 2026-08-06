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

Below that, a filter bar:
- **Farm / Supplier** — narrow the view to one farm/supplier, or leave it
  on "All farms / suppliers."
- **Period start / Period end** — the date range you're looking at, or
  tap **Today**, **This Week**, or **Season** for a quick preset.
- **Refresh** — pull the latest numbers for whatever range is selected.

Then the numbers themselves:

- **KPI cards** — teams/workers/blocks active, total kg and crates,
  averages, and a Harvesting/In Transit/Received breakdown, all for the
  selected date range.
- **Harvesting / In Transit / Received** — tap any of these to expand
  the actual list of loads. Harvesting and In Transit are color-coded:
  🟢 green (recent), 🟡 yellow (been a while), 🔴 red (waiting too
  long) — the same color scheme used throughout the farm's own app.
- **Blocks** — tap to expand a per-block breakdown: crates, kg, and
  average yield per crate and per tree for the period.

---

## What this doesn't show

This link is deliberately limited to progress information — it doesn't
show individual worker pay, contact details, or anything you could
change. There's no way to edit data from this view; it's read-only by
design. If you need more detail than this covers, ask the farm office
directly.

---

## If something looks wrong

- **The link shows "This link isn't valid"** — the link may have been
  regenerated (this happens if it needed to be revoked and reissued) or
  mistyped/cut off when it was shared with you. Ask the farm office for
  the current link.
- **Numbers look outdated** — tap **Refresh**, or double-check the date
  range at the top actually covers the period you're expecting.
- **Nothing loads at all, and you're off the farm** — check that
  **Tailscale** is open and shows **"Connected"** first (see "If you're
  checking this from off the farm" above) - this is the most common
  cause. If Tailscale is connected and it still won't load, check your
  own internet connection, then let the farm office know if it persists.
