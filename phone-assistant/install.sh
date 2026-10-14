#!/usr/bin/env bash
# Installerar skillen phone-assistant i ~/.claude/skills/phone-assistant
# och lägger till en Claude Code-regel som alltid kräver ditt klick innan ett samtal startas.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${HOME}/.claude/skills/phone-assistant"

mkdir -p "$DEST"
install -m 0644 "$SRC/SKILL.md" "$DEST/SKILL.md"
install -m 0755 "$SRC/phone_assistant.py" "$DEST/phone_assistant.py"
echo "Skill installerad: $DEST"

# Extra spärr utöver --confirm: Claude Code frågar dig varje gång test/ask ska köras.
SETTINGS="${HOME}/.claude/settings.json"
python3 - "$SETTINGS" <<'PY'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
data = json.loads(p.read_text()) if p.exists() and p.read_text().strip() else {}
ask = data.setdefault("permissions", {}).setdefault("ask", [])
rules = [
    "Bash(python3 ~/.claude/skills/phone-assistant/phone_assistant.py ask:*)",
    "Bash(python3 ~/.claude/skills/phone-assistant/phone_assistant.py test:*)",
    "Bash(python3 ~/.claude/skills/phone-assistant/phone_assistant.py set-limit:*)",
    "Bash(python3 ~/.claude/skills/phone-assistant/phone_assistant.py set-number:*)",
]
added = [r for r in rules if r not in ask]
ask.extend(added)
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"Godkännanderegler i {p}: {len(added)} nya")
PY

cat <<EOF

Nästa steg:
  1. python3 $DEST/phone_assistant.py setup-key      # dold inmatning av BLAND_API_KEY
  2. python3 $DEST/phone_assistant.py set-number +467XXXXXXXX
  3. python3 $DEST/phone_assistant.py check          # ringer inte
  4. Be Claude: "ring mig för ett testsamtal"
EOF
