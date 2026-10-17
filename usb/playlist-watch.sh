#!/bin/sh
# Started by mixxx.service (ExecStartPost). When import_playlists.py left songs
# waiting for Mixxx's startup scan, restart Mixxx once after the scan so the
# importer runs again and adds them to their playlists.
PENDING=$HOME/.cache/mixxx-playlists-pending
[ -f "$PENDING" ] || exit 0
timeout 1800 tail -n 0 -F "$HOME/.mixxx/mixxx.log" 2>/dev/null | grep -q -m1 "Scan finished cleanly" || exit 0
[ -f "$PENDING" ] || exit 0
mv "$PENDING" "$PENDING.done"
sudo -n /usr/bin/systemctl restart mixxx.service
