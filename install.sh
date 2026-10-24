#!/usr/bin/env bash
# 开发用：把插件复制到用户扩展目录并重启 nautilus。
# 正式安装请用 pacman 包（见 README）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="$HOME/.local/share/nautilus-python/extensions"

mkdir -p "$DIR"
install -m 644 "$ROOT/nautilus-folder-yaml.py" "$DIR/nautilus-folder-yaml.py"
# 旧名字的副本会让菜单出现两份（docs/pitfalls.md #4）
[ -e "$DIR/nautilus-meta.py" ] && mv "$DIR/nautilus-meta.py" "$DIR/nautilus-meta.py.disabled"

nautilus -q 2>/dev/null || true
echo "已安装到 $DIR/nautilus-folder-yaml.py，nautilus 已重启。"
