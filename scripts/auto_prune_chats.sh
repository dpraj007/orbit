#!/usr/bin/env bash
set -euo pipefail

# Prune specified chats down to KEEP messages by deleting the oldest first.
# Designed for the Series hackathon API with broken pagination.

BASE_URL="${SERIES_BASE_URL:?set SERIES_BASE_URL}"
API_KEY="${SERIES_API_KEY:?set SERIES_API_KEY}"

# Chats to prune (space-separated). Defaults: Leon/Dhairyasheel threads.
if [[ -n "${CHAT_IDS:-}" ]]; then
  read -r -a CHATS <<<"${CHAT_IDS}"
else
  CHATS=("1701689" "1701997")
fi

# Tunables
KEEP="${KEEP:-15}"           # target max messages per chat
SLEEP_SECONDS="${SLEEP_SECONDS:-5}"  # delay between prune passes when looping
MAX_DELETE="${MAX_DELETE:-200}"      # safety cap per run
RUN_ONCE="${RUN_ONCE:-0}"    # set to 1 to prune once and exit

prune_chat() {
  local chat_id="$1"
  local deleted=0
  while true; do
    resp=$(curl -sS "$BASE_URL/api/chats/$chat_id/chat_messages?page=1&per_page=25" \
      -H "Authorization: Bearer $API_KEY" \
      -H "Content-Type: application/json")
    count=$(printf '%s' "$resp" | jq -r '.meta.total_count // 0')
    oldest_id=$(printf '%s' "$resp" | jq -r '.data | sort_by(.sent_at) | .[0].id // empty')
    newest_id=$(printf '%s' "$resp" | jq -r '.data | sort_by(.sent_at) | .[-1].id // empty')
    echo "chat $chat_id: total=$count keep<=$KEEP oldest=$oldest_id newest=$newest_id"

    if [[ -z "$oldest_id" || "$count" -le "$KEEP" || "$deleted" -ge "$MAX_DELETE" ]]; then
      break
    fi

    curl -sS -X DELETE "$BASE_URL/api/chats/$chat_id/chat_messages/$oldest_id" \
      -H "Authorization: Bearer $API_KEY" \
      -H "Content-Type: application/json" >/dev/null || true
    deleted=$((deleted+1))
    sleep 0.05
  done
}

while true; do
  for chat in "${CHATS[@]}"; do
    prune_chat "$chat"
  done
  [[ "$RUN_ONCE" == "1" ]] && break
  sleep "$SLEEP_SECONDS"
done
