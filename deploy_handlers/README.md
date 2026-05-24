# Pterodactyl Deployment Guide

This folder contains the deployment artifacts for hosting **Golden IQ MUSIC Bot** on a [Pterodactyl Panel](https://pterodactyl.io/).

## Files

- `egg-golden-iq-music-bot.json` — Pterodactyl egg. Import this from your panel.
- `start.sh` — runtime start script. The installer copies it to `/home/container/start.sh`; the runtime startup command also self-heals from this file if `/home/container/start.sh` is ever missing, so a partial install or accidental delete can no longer brick the server.

## Troubleshooting: `start.sh: No such file or directory` / exit code 127

If the console loops on:

```
container~ /home/container/start.sh
/entrypoint.sh: line 20: /home/container/start.sh: No such file or directory
```

the install step never finished writing `start.sh`. On the **current egg version** the runtime now self-heals: it will clone the repo (if `GIT_ADDRESS` is set) and restore `start.sh` from `deploy_handlers/start.sh` on the next boot. If you are on an **older egg** that lacks the self-heal startup, just **Reinstall** the server from the panel — that re-runs the installer.

## One-time setup (admin side)

1. Open the Pterodactyl **admin panel**.
2. Go to **Nests** -> pick or create a nest (e.g. "Discord Bots").
3. Click **Import Egg** -> select `egg-golden-iq-music-bot.json` -> Import.
4. The egg "Golden IQ MUSIC Bot" is now available when creating new servers.

## Creating a server

1. **Admin -> Servers -> Create New**.
2. Pick the new egg "Golden IQ MUSIC Bot".
3. Select the **docker image**:
   - `Python 3.14 (default)` — matches the version you tested locally
   - or fall back to 3.13 / 3.12 / 3.11 if a dependency does not yet have a 3.14 wheel
4. **Resources** — recommended minimum:
   - **CPU:** 100% (1 core)
   - **RAM:** 1024 MB (more if `RUN_LOCAL_LAVALINK=true`)
   - **Disk:** 3000 MB (the venv + Lavalink.jar + JDK takes ~1.5 GB)
5. **Variables** — fill in at least:
   - `TOKEN` — your Discord bot token (required)
   - `GIT_ADDRESS` — **pre-filled** with the official repo
     (`https://github.com/goldeniq-official/Golden-IQ-MUSIC-Bot-Discord.git`).
     The installer clones it automatically — **no SFTP upload needed**.
     Replace this only if you maintain a private fork. For private repos,
     embed credentials in the URL: `https://<user>:<token>@github.com/...`.
   - `AUTO_UPDATE` — defaults to `1`. Every restart force-syncs the working
     tree to the latest commit on `BRANCH`.
   - Everything else has sensible defaults.

## Updating the bot

By default, every new server uses the official repo + auto-update, so you
get fresh code on every restart with no action needed. Two options:

- **Manual:** upload changed files via SFTP / file manager, then restart.
- **Automatic (default):** `GIT_ADDRESS` is pre-filled and `AUTO_UPDATE=1`.
  Every start the
  container does `git fetch` + `git reset --hard origin/<BRANCH>`, so the
  working tree is always force-synced to the latest commit on the configured
  branch. Any local edits you made to **tracked** files (e.g. `main.py`,
  `requirements.txt`) will be overwritten — this is intentional, otherwise
  one accidental SFTP edit silently blocks every future pull. Untracked /
  gitignored files (`.env`, `local_database/`, `Lavalink.jar`,
  `application.yml`, `lavalink.ini`, logs) are preserved.

  Look at the server console on boot — you will see one of:
  - `[update] Already up to date at <sha>.`
  - `[update] Successfully updated to <sha> (<commit message>).`
  - `[update] ERROR: ...` — read the message; common causes are a bad
    `GIT_ADDRESS`, the wrong `BRANCH`, or a private repo that needs a token
    in the URL (`https://<user>:<token>@github.com/...`).

To skip the (slow) pip install on every start once your venv is warm, set `SKIP_PIP_ON_START=1`.

> If `AUTO_UPDATE=1` reports `WARNING: ... no .git directory found`, the
> server was created without `GIT_ADDRESS`. Re-install with `GIT_ADDRESS`
> filled in so the container clones the repo and gains a `.git` folder.

## Troubleshooting

### "No space left on device" during install

The Pterodactyl allocation is too small. Either:

- Raise the server's **Disk** allocation in the admin panel (recommended: 3000 MB+).
- Comment out the heavy optional deps in `requirements.txt`:
  - `nodriver`
  - `undetected-chromedriver`

  These two pull in selenium + Chrome driver (~200 MB) and are **only** used to auto-refresh the YouTube po_token. The bot starts fine without them.

### "Cog named 'Music' already loaded"

This happens when one of the files in `modules/` got overwritten with the contents of `music.py`. Re-upload the original file (most often it is `modules/misc.py`, which should be ~1,000 lines and end with `bot.add_cog(GuildLog(bot))`).

The safest way to avoid this is to upload the entire project as a **single zip** and extract it inside the panel, or use the `GIT_ADDRESS` egg variable.

### Lavalink fails to start

Java 17 is installed by the egg's install script. If the bot still cannot find Java, set `RUN_LOCAL_LAVALINK=false` and configure a remote node by editing `lavalink.ini` (copy `lavalink.ini.example`).

### Bot says "PRIVILEGED INTENTS REQUIRED"

In the [Discord Developer Portal](https://discord.com/developers/applications/), open your bot -> **Bot** tab -> enable **Message Content Intent**, **Server Members Intent**, and **Presence Intent** as needed.

## Local Windows testing

Use `source_start_windows.bat` from the project root. It creates a venv, installs deps, and restarts the bot on crash. This is the recommended workflow before pushing to the panel.
