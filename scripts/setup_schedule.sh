#!/bin/bash
# ============================================================
# AI News Aggregator — macOS LaunchAgent 安装脚本
# 安装后每天 09:00 (系统本地时间) 自动运行一次简报生成
#
# 用法:
#   bash scripts/setup_schedule.sh          # 安装/更新定时任务
#   bash scripts/setup_schedule.sh --remove # 卸载定时任务
# ============================================================

set -e

LABEL="com.ainewsaggregator.daily"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.ainewsaggregator.daily.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

# ---------- Remove mode ----------
if [[ "$1" == "--remove" ]]; then
    echo "Unloading LaunchAgent..."
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST_DEST"
    echo "Done. LaunchAgent removed."
    exit 0
fi

# ---------- Detect Python ----------
PYTHON=$(which python3)
if [[ -z "$PYTHON" ]]; then
    echo "ERROR: python3 not found in PATH"
    exit 1
fi
echo "Using Python: $PYTHON"

# ---------- Ensure log dir exists ----------
mkdir -p "$LOG_DIR"

# ---------- Write final plist ----------
cat > "$PLIST_DEST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${PROJECT_DIR}/main.py</string>
        <string>--mode</string>
        <string>once</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/launchd_stderr.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

echo "Plist written to: $PLIST_DEST"

# ---------- Reload LaunchAgent ----------
# Unload if already loaded (ignore errors)
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

# Load the new plist
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"

echo ""
echo "✓ LaunchAgent installed successfully!"
echo "  Schedule: every day at 09:00 (system local time)"
echo "  Project:  $PROJECT_DIR"
echo "  Logs:     $LOG_DIR/launchd_stdout.log"
echo ""
echo "Useful commands:"
echo "  Check status:  launchctl list | grep ainewsaggregator"
echo "  Run now:       launchctl kickstart -k gui/\$(id -u)/${LABEL}"
echo "  Remove:        bash scripts/setup_schedule.sh --remove"
