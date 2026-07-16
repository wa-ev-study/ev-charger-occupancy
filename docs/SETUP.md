# Setup Guide (first-time, no technical background needed)

Follow these in order. Nothing here costs money. Where you create credentials,
write them on a single **shared credentials sheet** (a private doc) — not in
this repository.

Legend:  ☐ = your action.   Each step says what you should see when it worked.

---

## Step 1 — Create the shared project Google account  ☐

This keeps the whole project off your personal Gmail and lets Todd share it.

1. Sign out of Gmail (or use a private/incognito window).
2. Go to accounts.google.com → **Create account** → *For my personal use*.
3. Pick a project address, e.g. `ev.charging.data.wa@gmail.com`, and a strong
   password. (Google may ask for a phone number to verify — yours is fine; it
   does not link the accounts in any visible way.)

**Worked when:** you can log in to the new account and see an empty Gmail inbox.
Put the address + password on the shared credentials sheet.

> Use this one account as the hub for Steps 2–4.

## Step 2 — Get a free TomTom API key  ☐

1. While logged into the project Google account, go to
   `developer.tomtom.com` → **Register** (you can "Sign up with Google" using
   the project account).
2. After signing in, open the **Dashboard** → your default **API Key** is shown.
   (No credit card is requested. The free tier gives 2,500 requests/day.)
3. Copy the key onto the shared credentials sheet.

**Worked when:** you can see a long API key string in your TomTom dashboard.

## Step 3 — Get a free NREL API key  ☐

1. Go to `developer.nrel.gov/signup/` and request a key (instant, free).
2. Copy it to the shared credentials sheet.

**Worked when:** NREL emails/shows you an API key.

## Step 4 — Create the GitHub home for the project  ☐

1. While logged into the project Google account, go to `github.com` → sign up
   (use the project email). Verify the email.
2. Create a **free Organization** (Settings → *Your organizations* → New) —
   this lets you and Todd share equal admin later. Name it for the project.
3. Inside the org, **New repository** → name it (e.g., `ev-charger-occupancy`)
   → set it to **Public** → Create.
4. Upload the contents of this project folder to the repo (drag-and-drop the
   files via *Add file → Upload files*, or ask Claude to push them for you).

**Worked when:** the repo shows the `src/`, `.github/`, and `docs/` folders.

## Step 5 — Add the secret keys to the repo  ☐

1. In the repo: **Settings → Secrets and variables → Actions → New repository secret.**
2. Add two secrets (names must match exactly):
   - `TOMTOM_API_KEY`  = your TomTom key from Step 2
   - `NREL_API_KEY`    = your NREL key from Step 3

**Worked when:** both names appear under "Repository secrets." (The values are
hidden — that's correct; they're encrypted and never shown in logs.)

## Step 6 — Build the station list once  ☐

1. In the repo: **Actions** tab → enable workflows if prompted.
2. Open **Daily rollup** → **Run workflow** (this also builds the station list).
   Wait ~1–2 minutes.

**Worked when:** a new commit appears adding `data/master/stations.json`, and the
run is green. Open that file — you should see Bellevue/Seattle stations tagged
with `funded` and `multifamily` flags.

## Step 7 — Turn on collection  ☐

1. **Actions → Collect charger availability → Run workflow** to test it now.
2. It will also run automatically every 15 minutes from here on.

**Worked when:** within a few minutes a `data/raw/<today>.csv` file appears with
timestamped rows. You're collecting.

## Step 8 — Watch the first day  ☐

- The next morning, check that `data/raw/` has a file for the new day and that
  **Actions** runs are green.
- After ~9:30 PM Pacific, the nightly rollup adds rows to
  `data/summaries/daily_by_city.csv` — that's your headline data.

---

## Adding Todd

- **GitHub:** Org → People → invite Todd's email → set role to **Owner** (equal
  access) or **Member** with admin on the repo.
- **TomTom / Google:** share the project credentials sheet so he can log in.

## Going to the paid, broader view (later)

1. Add a payment method in the TomTom dashboard (**this is the only billing step**).
2. In `config.yaml`, set `seattle_census: enabled: true` and, if desired, lower
   `poll_minutes` and raise `budget.daily_request_cap`.
3. Commit the change. The system scales automatically.

## If something looks wrong

- A run is red in **Actions** → click it to read the log; the last lines say why.
- No new data → check the two secret names are spelled exactly as in Step 5.
- "Outside the allowed window" in the log is normal at night for daytime groups.
