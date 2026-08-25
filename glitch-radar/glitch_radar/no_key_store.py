import json
from pathlib import Path
from datetime import datetime, timezone

SNAPSHOT_PATH = Path("no_key_snapshot.json")
HISTORY_PATH = Path("no_key_history.jsonl")

def save_no_key_snapshot(data, path=SNAPSHOT_PATH, history_path=HISTORY_PATH):
    now = datetime.now(timezone.utc).isoformat()
    row = {"timestamp": now, **data}
    Path(path).write_text(json.dumps(row, indent=2, default=str), encoding="utf-8")
    with Path(history_path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
    return row

def load_no_key_snapshot(path=SNAPSHOT_PATH):
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def load_no_key_history(limit=100, path=HISTORY_PATH):
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return list(reversed(rows))
