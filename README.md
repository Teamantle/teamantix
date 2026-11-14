# Teamantix

One-click teams for **cemantle**, **cémantix**, **pedantle** and **pédantix** (certitudes.org).

These games have a *Collaborate* feature (☁️) for playing together: one person starts a team, gets a code and shares it; the others paste it into *Join*. Teamantix automates the creation of those codes.

🔗 **Website:** https://teamantle.github.io/teamantix/

## Two pages

| Page | For | What it does |
|---|---|---|
| [`index.html`](https://teamantle.github.io/teamantix/) | Everyone | Generates a fresh team code on demand for each of the 4 games. |
| [`team.html`](https://teamantle.github.io/teamantix/team.html) | Our team | Shows today's codes, generated automatically every day and protected by a passphrase. |

Each code is a random 20-character key: a visitor on `index.html` creates their own team and cannot land in ours.

## Usage

**Join today's team**

1. Open the team link (shared privately): `https://teamantle.github.io/teamantix/team.html#k=…`
2. Click **Copier** next to the game, then **jouer ↗**.
3. In the game: ☁️ → paste the code → **Join**.

The passphrase is remembered on the device after the first visit; from then on, `team.html` is enough.

**Create a one-off team**: open `index.html`, click *Générer le code* (or *Générer tous les codes*) and share the resulting code.

## How it works

### Creating a team

The script does exactly what the site's *Start* button does: it creates a `g/<puzzle number>/<key>` entry with `_users = 1` in the game's Firebase Realtime Database. The displayed code is that key, with every `-` replaced by `Ô`.

A team is only valid for the current puzzle number: a new code is needed every day.

### Automatic generation (`team.html`)

```
GitHub Actions (daily, 07:00 UTC)
  └─ generate.py
       ├─ reads today's puzzle number from each game page (data-puzzle-number)
       │    └─ fallback: computed from a reference date
       ├─ creates the 4 teams in Firebase
       ├─ encrypts the codes (AES-256-GCM, key derived with PBKDF2-SHA256)
       └─ commits codes.json
team.html
  └─ downloads codes.json and decrypts it in the browser with the passphrase
```

`codes.json` is public but unreadable without the passphrase. The passphrase passed in the link (`#k=…`) is never sent to the server: everything after `#` stays in the browser.

### Puzzle number (`index.html`)

A browser cannot read certitudes.org pages from another site. `index.html` therefore computes the number from a reference (`REF` in the code) and adds 1 at each daily rollover, set to 01:00 UTC. If it drifts, the number can still be edited by hand.

## Repository layout

```
.
├── .github/workflows/codes.yml   # daily scheduled job + manual trigger
├── generate.py                   # creates and encrypts the codes
├── codes.json                    # today's encrypted codes (generated automatically)
├── index.html                    # public generator
├── team.html                     # private team page
└── README.md
```

## Setting it up on another account

1. Create a **public** repository and add the files above.
2. **Settings → Pages**: *Deploy from a branch*, branch `main`, folder `/ (root)`.
3. **Settings → Secrets and variables → Actions**: add a `TEAM_PASSPHRASE` secret (a long phrase).
4. **Settings → Actions → General**: *Workflow permissions* → **Read and write permissions**.
5. **Actions → Codes du jour → Run workflow** for a first test.

The schedule is set by the `cron` line in `codes.yml`. GitHub cron runs in UTC: `0 7 * * *` means 08:00 in Paris in winter and 09:00 in summer.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `PERMISSION_DENIED` | Wrong puzzle number for that game (the database only accepts the current day). |
| "Invalid code" in the game | Code from another day, or the team was deleted (the site removes it when its last member leaves the page). |
| `team.html` says the codes are not updated today | The scheduled job has not run yet (GitHub can delay it by several tens of minutes). |
| The *Publier codes.json* step fails | *Workflow permissions* is not set to *Read and write*. |
| "Phrase secrète incorrecte" | The passphrase differs from `TEAM_PASSPHRASE`, or the secret was changed. |

> GitHub disables scheduled workflows in a repository with no activity for 60 days. Here, the daily `codes.json` commit keeps the repository active.

## Disclaimer

Unofficial personal project, not affiliated with certitudes.org. It uses the *Collaborate* feature as the site provides it, without bypassing anything.
