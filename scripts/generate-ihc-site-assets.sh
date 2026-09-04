#!/usr/bin/env bash
# Generate the hero media for the Integrated Health Associates site (site/) via Arcads.
#
#   1. Nano Banana 2 still  -> site/assets/hero-poster.jpg   (16:9 poster + video start frame)
#   2. Kling 3.0 15s video  -> site/assets/hero-loop.mp4     (image-to-video from that poster)
#
# The page in site/index.html already references both files and falls back to an
# animated gradient when they are missing, so this script only has to drop them in.
#
# Usage:   ./scripts/generate-ihc-site-assets.sh [--yes] [--poster-only] [--video-only]
# Needs:   .env with ARCADS_BASIC_AUTH (or ARCADS_API_KEY), curl, jq. ffmpeg optional (JPEG poster).
# Optional: ARCADS_PRODUCT_ID to pin the Arcads product when the workspace has several.
#
# Follows skills/arcads-external-api/SKILL.md: dated folder/project, credit estimate +
# confirmation before firing, polling by asset type, append-only log in logs/arcads-api.jsonl
# (no prompt text, no secrets), and a visual QA reminder for the still.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="$ROOT/site"
ASSETS="$SITE/assets"
LOG="$ROOT/logs/arcads-api.jsonl"
BASE="${ARCADS_BASE_URL:-https://external-api.arcads.ai}"
TODAY="$(date +%Y-%m-%d)"

AUTO_YES=0; DO_POSTER=1; DO_VIDEO=1
for a in "$@"; do
  case "$a" in
    --yes|-y) AUTO_YES=1 ;;
    --poster-only) DO_VIDEO=0 ;;
    --video-only) DO_POSTER=0 ;;
    -h|--help) sed -n 2,16p "$0"; exit 0 ;;
    *) echo "Unknown flag: $a" >&2; exit 2 ;;
  esac
done

for tool in curl jq; do command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 1; }; done

# ── Auth ─────────────────────────────────────────────────────────────────────
if [[ -f "$ROOT/.env" ]]; then set -a; source "$ROOT/.env"; set +a; fi
if [[ -n "${ARCADS_BASIC_AUTH:-}" && "$ARCADS_BASIC_AUTH" != *"your_base64_encoded_credentials_here"* ]]; then
  AUTH="Authorization: $ARCADS_BASIC_AUTH"
elif [[ -n "${ARCADS_API_KEY:-}" && "$ARCADS_API_KEY" != "your_key_here" ]]; then
  AUTH="Authorization: Basic $(printf '%s:' "$ARCADS_API_KEY" | base64 | tr -d '\n')"
else
  echo "No Arcads credentials in .env — run ./scripts/setup.sh first." >&2; exit 1
fi

api() { # api METHOD PATH [JSON]
  local m="$1" p="$2" body="${3:-}"
  if [[ -n "$body" ]]; then
    curl -sS -X "$m" -H "$AUTH" -H "Content-Type: application/json" -d "$body" "$BASE$p"
  else
    curl -sS -X "$m" -H "$AUTH" "$BASE$p"
  fi
}

# ── Product + dated project (so assets are findable in the Arcads dashboard) ─
PRODUCTS="$(api GET /v1/products)"
if [[ -n "${ARCADS_PRODUCT_ID:-}" ]]; then
  PRODUCT_ID="$ARCADS_PRODUCT_ID"
else
  COUNT="$(echo "$PRODUCTS" | jq 'if type=="array" then length else (.data // .items // [] | length) end')"
  LIST="$(echo "$PRODUCTS" | jq -c 'if type=="array" then . else (.data // .items // []) end')"
  if [[ "$COUNT" == "1" ]]; then
    PRODUCT_ID="$(echo "$LIST" | jq -r '.[0].id')"
  else
    echo "Your workspace has $COUNT products. Set ARCADS_PRODUCT_ID in .env to one of:" >&2
    echo "$LIST" | jq -r '.[] | "  \(.id)  \(.name // "")"' >&2
    exit 1
  fi
fi
PRODUCT_NAME="$(echo "$PRODUCTS" | jq -r --arg id "$PRODUCT_ID" '(if type=="array" then . else (.data // .items // []) end) | map(select(.id==$id)) | .[0].name // "unknown"')"

FOLDER_NAME="Arcads API - $TODAY"
FOLDERS="$(api GET "/v1/products/$PRODUCT_ID/folders" || echo '[]')"
FOLDER_ID="$(echo "$FOLDERS" | jq -r --arg n "$FOLDER_NAME" '(if type=="array" then . else (.data // .items // []) end) | map(select(.name==$n)) | .[0].id // empty')"
if [[ -z "$FOLDER_ID" ]]; then
  FOLDER_ID="$(api POST /v1/folders "$(jq -nc --arg p "$PRODUCT_ID" --arg n "$FOLDER_NAME" '{productId:$p,name:$n}')" | jq -r '.id')"
fi
PROJECT_ID="$(api POST /v1/projects "$(jq -nc --arg p "$PRODUCT_ID" --arg f "$FOLDER_ID" --arg n "IHA website hero - $TODAY" '{productId:$p,folderId:$f,name:$n}')" | jq -r '.id')"

# ── Prompts (edit freely; brand = steel blue #1f5872, warm paper #f6f4ef, orange #e27a1b) ─
POSTER_PROMPT='Wide cinematic establishing photograph of a modern community health center lobby at golden hour. Low sun rakes across warm off-white walls and pale steel-blue glass; one nurse in navy scrubs walks away, small and out of focus, in the far background. Style: photoreal editorial architecture photography, calm and hopeful, muted palette of warm paper white, deep steel blue and a single burnt-orange accent in a wayfinding sign. Composition: low horizon, camera at chest height, generous empty wall space on the left third for a text overlay. Lighting: natural window light, gentle haze, soft long shadows. Background: clean architecture, wood and glass, no logos. Avoid: readable text, faces in focus, clutter, people in the foreground, oversaturated colors, watermarks, lens flare artifacts.'
VIDEO_PROMPT='Very slow, steady dolly forward through the same health center lobby, starting exactly from the provided frame. Sunlight drifts a few degrees across the wall, dust motes float in the light shaft, glass reflections shift gently, and the distant nurse walks calmly out of frame. Camera: locked horizon, continuous slow push-in, no cuts, no handheld shake. Mood: calm, confident, hopeful; a quiet steady rhythm. Avoid: fast motion, new people entering, text, flicker, morphing or warping architecture, color shifts.'

# ── Credit estimate (MANDATORY before firing; estimates only) ───────────────
EST_POSTER="0.03"; EST_VIDEO="0.7"
echo "=== Integrated Health Associates — site hero assets ==="
echo "Product: $PRODUCT_NAME ($PRODUCT_ID)   Project: IHA website hero - $TODAY"
echo
echo "Estimated credits (from skills/arcads-external-api/reference.md, 2026-04-09 observations):"
[[ $DO_POSTER == 1 ]] && echo "  Nano Banana 2 still, 16:9        x1 = ~$EST_POSTER"
[[ $DO_VIDEO  == 1 ]] && echo "  Kling 3.0, 15s, startFrame       x1 = ~$EST_VIDEO"
echo "  Estimate only — confirm exact pricing in the Arcads platform."
if [[ $AUTO_YES != 1 ]]; then
  read -r -p "Proceed? [y/N] " ok; [[ "$ok" =~ ^[Yy] ]] || { echo "Cancelled."; exit 0; }
fi
mkdir -p "$ASSETS" "$ROOT/logs"

# ── Logging helpers (append on fire, update the same line after polling) ────
log_fire() { # log_fire endpoint model assetId requestJson
  jq -nc --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg ep "$1" --arg model "$2" --arg id "$3" \
         --arg pid "$PRODUCT_ID" --arg prj "$PROJECT_ID" --arg folder "$FOLDER_NAME" --argjson req "$4" \
    '{timestamp:$ts,endpoint:$ep,model:$model,assetId:$id,productId:$pid,projectId:$prj,request:$req,
      response:{status:"pending",creditsCharged:null,generationTimeSec:null,videoUrl:null,thumbnailUrl:null,error:null},
      session:{folderName:$folder,notes:"IHA website hero asset (scripts/generate-ihc-site-assets.sh)"}}' >> "$LOG"
}
log_done() { # log_done assetId status credits seconds url thumb error
  python3 - "$LOG" "$@" <<'PY'
import json,sys
path,aid,status,credits,secs,url,thumb,err=sys.argv[1:9]
lines=open(path).read().splitlines()
for i,l in enumerate(lines):
    if not l.strip(): continue
    try: e=json.loads(l)
    except Exception: continue
    if e.get("assetId")==aid:
        e["response"]={"status":status,"creditsCharged":(float(credits) if credits not in ("","null") else None),
                       "generationTimeSec":int(secs),"videoUrl":url or None,"thumbnailUrl":thumb or None,"error":err or None}
        lines[i]=json.dumps(e)
open(path,"w").write("\n".join(lines)+"\n")
PY
}

wc_of() { echo "$1" | wc -w | tr -d ' '; }

# poll_asset ID -> prints final JSON; tries /v1/assets then /v1/videos (Kling jobs live under videos)
poll_asset() {
  local id="$1" started=$SECONDS r status
  while :; do
    r="$(api GET "/v1/assets/$id" 2>/dev/null || true)"
    status="$(echo "$r" | jq -r '.status // empty' 2>/dev/null || true)"
    if [[ -z "$status" ]]; then
      r="$(api GET "/v1/videos/$id" 2>/dev/null || true)"
      status="$(echo "$r" | jq -r '.videoStatus // .status // empty' 2>/dev/null || true)"
    fi
    case "$status" in
      generated|completed|done|ready|uploaded) echo "$r"; return 0 ;;
      failed|error) echo "$r"; return 1 ;;
    esac
    (( SECONDS - started > 900 )) && { echo "$r"; return 1; }
    printf '  … %s (%ss)\r' "${status:-waiting}" "$((SECONDS-started))" >&2
    sleep 5
  done
}

TOTAL_CREDITS=0
add_credits() { TOTAL_CREDITS="$(jq -n --arg a "$TOTAL_CREDITS" --arg b "${1:-0}" '($a|tonumber)+(($b|tonumber)? // 0)')"; }

# ── 1. Poster still (Nano Banana 2) ─────────────────────────────────────────
POSTER_PNG="$ASSETS/hero-poster.png"
if [[ $DO_POSTER == 1 ]]; then
  echo; echo "→ Generating poster still (Nano Banana 2, 16:9)…"
  BODY="$(jq -nc --arg p "$PRODUCT_ID" --arg prj "$PROJECT_ID" --arg pr "$POSTER_PROMPT" '{productId:$p,projectId:$prj,prompt:$pr,model:"nano-banana-2",aspectRatio:"16:9"}')"
  RES="$(api POST /v2/images/generate "$BODY")"
  AID="$(echo "$RES" | jq -r '.id // empty')"
  [[ -n "$AID" ]] || { echo "Image create failed: $RES" >&2; exit 1; }
  log_fire "POST /v2/images/generate" "nano-banana-2" "$AID" "$(jq -nc --arg w "$(wc_of "$POSTER_PROMPT")" '{aspectRatio:"16:9",referenceImagesCount:0,promptWordCount:($w|tonumber),purpose:"site hero poster"}')"
  T0=$SECONDS
  if FINAL="$(poll_asset "$AID")"; then
    URL="$(echo "$FINAL" | jq -r '.url // .imageUrl // empty')"
    CR="$(echo "$FINAL" | jq -r '.data.creditsCharged // .creditsCharged // empty')"
    log_done "$AID" generated "$CR" "$((SECONDS-T0))" "$URL" "" ""
    add_credits "$CR"
    curl -sS -L -o "$POSTER_PNG" "$URL"
    if command -v ffmpeg >/dev/null; then ffmpeg -loglevel error -y -i "$POSTER_PNG" -q:v 3 "$ASSETS/hero-poster.jpg"
    elif python3 -c "import PIL" 2>/dev/null; then python3 -c "from PIL import Image; Image.open('$POSTER_PNG').convert('RGB').save('$ASSETS/hero-poster.jpg',quality=88)"
    else cp "$POSTER_PNG" "$ASSETS/hero-poster.jpg"; fi
    echo "  ✓ poster saved → site/assets/hero-poster.jpg  (asset $AID, ~${CR:-?} credits)"
    echo "  QA: open the poster and check for warped architecture, stray limbs, or readable text before deploying."
  else
    log_done "$AID" failed "" "$((SECONDS-T0))" "" "" "$(echo "$FINAL" | jq -r '.data.error.message // .error // "failed"')"
    echo "Poster generation failed: $FINAL" >&2; exit 1
  fi
fi

# ── 2. Hero loop (Kling 3.0, image-to-video from the poster) ────────────────
if [[ $DO_VIDEO == 1 ]]; then
  [[ -f "$POSTER_PNG" || -f "$ASSETS/hero-poster.jpg" ]] || { echo "No poster to animate — run without --video-only first." >&2; exit 1; }
  SRC="$POSTER_PNG"; TYPE="image/png"; [[ -f "$SRC" ]] || { SRC="$ASSETS/hero-poster.jpg"; TYPE="image/jpeg"; }
  echo; echo "→ Uploading poster as start frame…"
  PRE="$(api POST /v1/file-upload/get-presigned-url "$(jq -nc --arg t "$TYPE" '{fileType:$t}')")"
  PUT_URL="$(echo "$PRE" | jq -r '.presignedUrl')"; FILE_PATH="$(echo "$PRE" | jq -r '.filePath')"
  curl -sS -o /dev/null -X PUT -H "Content-Type: $TYPE" --data-binary @"$SRC" "$PUT_URL"
  echo "→ Generating hero loop (Kling 3.0, 15s, startFrame)…"
  BODY="$(jq -nc --arg p "$PRODUCT_ID" --arg prj "$PROJECT_ID" --arg pr "$VIDEO_PROMPT" --arg sf "$FILE_PATH" '{model:"kling-3.0",productId:$p,projectId:$prj,prompt:$pr,duration:15,startFrame:$sf}')"
  RES="$(api POST /v2/videos/generate "$BODY")"
  VID="$(echo "$RES" | jq -r '.id // empty')"
  [[ -n "$VID" ]] || { echo "Video create failed: $RES" >&2; exit 1; }
  log_fire "POST /v2/videos/generate" "kling-3.0" "$VID" "$(jq -nc --arg w "$(wc_of "$VIDEO_PROMPT")" '{duration:15,startFrame:true,referenceImagesCount:0,promptWordCount:($w|tonumber),purpose:"site hero loop"}')"
  T0=$SECONDS
  if FINAL="$(poll_asset "$VID")"; then
    URL="$(echo "$FINAL" | jq -r '.videoUrl // .url // empty')"
    THUMB="$(echo "$FINAL" | jq -r '.thumbnailUrl // empty')"
    CR="$(echo "$FINAL" | jq -r '.data.creditsCharged // .creditsCharged // empty')"
    log_done "$VID" generated "$CR" "$((SECONDS-T0))" "$URL" "$THUMB" ""
    add_credits "$CR"
    curl -sS -L -o "$ASSETS/hero-loop.mp4" "$URL"
    echo "  ✓ video saved → site/assets/hero-loop.mp4  (asset $VID, ~${CR:-?} credits)"
  else
    log_done "$VID" failed "" "$((SECONDS-T0))" "" "" "$(echo "$FINAL" | jq -r '.data.error.message // .error // "failed"')"
    echo "Video generation failed: $FINAL" >&2; exit 1
  fi
fi

echo
echo "Done. Credits charged this run (from API responses): ~$TOTAL_CREDITS — confirm in the Arcads platform."
echo "Preview: open site/index.html, then redeploy the site/ folder to Netlify."
( open "$ASSETS" 2>/dev/null || xdg-open "$ASSETS" 2>/dev/null || explorer "$ASSETS" 2>/dev/null ) || true
