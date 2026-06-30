#!/bin/bash
# Pull-and-relaunch deploy for the My Kitchen website.
# Mirrors the personal-site pattern: run from cron every few minutes; it only
# does work when there's a new commit on the tracked branch.
set -e
cd /home/pi/projects/my-kitchen-website

BEFORE=$(git rev-parse HEAD)
git pull --quiet
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
  exit 0
fi

# Reinstall deps only if requirements.txt changed in the pull.
if git diff --name-only "$BEFORE" "$AFTER" | grep -q '^requirements\.txt$'; then
  echo "[$(date '+%F %T')] requirements.txt changed; reinstalling deps"
  ./venv/bin/pip install -q -r requirements.txt
fi

/usr/bin/sudo /bin/systemctl restart mykitchen_web
echo "[$(date '+%F %T')] deployed $AFTER"
