#!/bin/bash
# Golden IQ MUSIC Bot — Pterodactyl runtime start script.
#
# This file is the source of truth. The Pterodactyl install step copies it to
# /home/container/start.sh. The runtime startup command also falls back to
# copying it from here if /home/container/start.sh is missing for any reason
# (e.g. a partial install), so the bot can self-heal without a reinstall.

set -u
cd /home/container

# Pterodactyl: always trust panel env vars. Wipe any .env that may have been
# left behind by previous installs / git pulls so dotenv_values() in
# config_loader.py does not shadow os.environ.
rm -f .env config.json

# --- Auto-update from Git -------------------------------------------------
# Robust replacement for `git pull --ff-only`. Fetches + hard-resets to
# origin/<branch> so local drift (e.g. requirements.txt rewritten by this
# script) cannot pin the server to an old commit. Untracked files (.env,
# local_database/, *.jar, application.yml, etc.) are preserved because git
# reset/clean only touch tracked state.
if [ "${AUTO_UPDATE:-0}" = "1" ]; then
  if [ -d .git ]; then
    TARGET_BRANCH="${BRANCH:-main}"
    if [ -n "${GIT_ADDRESS:-}" ]; then
      CURRENT_URL="$(git config --get remote.origin.url 2>/dev/null || echo '')"
      if [ "${CURRENT_URL}" != "${GIT_ADDRESS}" ]; then
        echo "[update] Updating remote.origin.url -> ${GIT_ADDRESS}"
        git remote set-url origin "${GIT_ADDRESS}" || git remote add origin "${GIT_ADDRESS}"
      fi
    fi
    echo "[update] Fetching latest from origin (branch=${TARGET_BRANCH})..."
    if git fetch --prune origin "${TARGET_BRANCH}"; then
      LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null || echo '')"
      REMOTE_SHA="$(git rev-parse "origin/${TARGET_BRANCH}" 2>/dev/null || echo '')"
      if [ -z "${REMOTE_SHA}" ]; then
        echo "[update] ERROR: could not resolve origin/${TARGET_BRANCH}. Check BRANCH env var."
      elif [ "${LOCAL_SHA}" = "${REMOTE_SHA}" ]; then
        echo "[update] Already up to date at ${LOCAL_SHA}."
      else
        echo "[update] Updating ${LOCAL_SHA} -> ${REMOTE_SHA}"
        git checkout -B "${TARGET_BRANCH}" "origin/${TARGET_BRANCH}" || true
        if ! git reset --hard "origin/${TARGET_BRANCH}"; then
          echo "[update] ERROR: git reset --hard failed."
        else
          find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
          echo "[update] Successfully updated to $(git rev-parse --short HEAD) ($(git log -1 --pretty=%s))."
          # If start.sh was updated upstream, refresh the runtime copy too.
          if [ -f deploy_handlers/start.sh ] && ! cmp -s deploy_handlers/start.sh start.sh 2>/dev/null; then
            echo "[update] Refreshing /home/container/start.sh from deploy_handlers/start.sh"
            cp deploy_handlers/start.sh start.sh && chmod +x start.sh
          fi
        fi
      fi
    else
      echo "[update] ERROR: git fetch failed. Check GIT_ADDRESS, network, and credentials. Keeping current code."
    fi
  else
    echo "[update] WARNING: AUTO_UPDATE=1 but no .git directory found. Re-install the server (or upload via the Git egg) to enable auto-update."
  fi
  rm -f .env config.json
fi
# --------------------------------------------------------------------------

if [ "${SKIP_PIP_ON_START:-0}" != "1" ] && [ -f requirements.txt ]; then
  mkdir -p /home/container/.tmp
  export TMPDIR=/home/container/.tmp
  if [ "${INSTALL_BROWSER_DEPS:-0}" != "1" ]; then
    sed -i -E '/^(nodriver|undetected-chromedriver)([[:space:]=<>!]|$)/Id' requirements.txt 2>/dev/null || true
  fi
  python3 -m pip install --no-cache-dir -r requirements.txt
  rm -rf /home/container/.tmp
fi

exec python3 -u main.py
