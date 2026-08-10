#!/usr/bin/env bash
# Render the Devpost brand images from the site favicon.
#
# Both outputs are drawn from the same mark as app/static/changesafe-logo.svg,
# so the submission page stays consistent with the deployed UI.
#
#   docs/brand/logo-1024.png            square logo / project thumbnail
#   docs/brand/logo-card-1200x800.png   3:2 gallery cover
#
# Requires headless Chromium and Pillow. Pass the Chromium binary as $CHROME
# when it is not on PATH.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="$repo_root/docs/brand"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

chrome="${CHROME:-$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)}"
if [ -z "$chrome" ]; then
  echo "No Chromium binary found. Set CHROME=/path/to/chrome and retry." >&2
  exit 1
fi

mark_svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img">
  <defs>
    <filter id="g" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="1.1" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="32" height="32" rx="9" fill="#000000"/>
  <path d="M12 8H9.5A2.5 2.5 0 0 0 7 10.5v11A2.5 2.5 0 0 0 9.5 24H12M20 8h2.5a2.5 2.5 0 0 1 2.5 2.5v11a2.5 2.5 0 0 1-2.5 2.5H20" fill="none" stroke="#a8c7eb" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="16" cy="16" r="3" fill="#ffffff" filter="url(#g)"/>
</svg>'

# The mark is rendered oversized and cropped to its alpha bounds, because the
# headless viewport is shorter than the requested window height and would
# otherwise clip the rounded bottom corners.
cat > "$work_dir/mark.html" <<EOF
<style>
  html,body{margin:0;padding:0;background:transparent;overflow:hidden}
  body{width:1200px;height:1200px;display:flex;align-items:center;justify-content:center}
  svg{display:block;width:960px;height:960px}
</style>
$mark_svg
EOF

cat > "$work_dir/card.html" <<EOF
<style>
  html,body{margin:0;padding:0;overflow:hidden}
  body{width:1200px;height:800px;background:#000;display:flex;align-items:center;
       justify-content:center;font-family:"Liberation Sans",Arial,sans-serif;
       color:#fff;text-align:center}
  .wrap{display:flex;flex-direction:column;align-items:center}
  svg{display:block;width:190px;height:190px}
  .name{margin-top:44px;font-size:88px;font-weight:700;letter-spacing:-.035em;line-height:1}
  .by{margin-top:16px;font-size:27px;color:#a8c7eb;letter-spacing:.02em}
  .rule{margin-top:40px;width:96px;height:2px;background:rgba(168,199,235,.38)}
  .tag{margin-top:38px;font-size:31px;color:#9fb3c8;letter-spacing:-.01em;line-height:1.35}
</style>
<div class="wrap">
  $mark_svg
  <div class="name">ChangeSafe</div>
  <div class="by">by Luca</div>
  <div class="rule"></div>
  <div class="tag">See who a data change affects<br>before it breaks them.</div>
</div>
EOF

mkdir -p "$out_dir"

"$chrome" --headless --no-sandbox --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 --default-background-color=00000000 \
  --screenshot="$work_dir/mark-raw.png" --window-size=1200,1400 \
  "file://$work_dir/mark.html" 2>/dev/null

"$chrome" --headless --no-sandbox --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 \
  --screenshot="$out_dir/logo-card-1200x800.png" --window-size=1200,800 \
  "file://$work_dir/card.html" 2>/dev/null

python3 - "$work_dir/mark-raw.png" "$out_dir/logo-1024.png" <<'PY'
import sys
from PIL import Image

source, target = sys.argv[1], sys.argv[2]
image = Image.open(source).convert("RGBA")
bounds = image.split()[3].getbbox()
image.crop(bounds).resize((1024, 1024), Image.LANCZOS).save(target)
print(f"wrote {target} from alpha bounds {bounds}")
PY

echo "wrote $out_dir/logo-card-1200x800.png"
