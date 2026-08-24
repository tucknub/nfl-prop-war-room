from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import championship


PUBLIC_APP_REPO = "tucknub/nfl-prop-war-room"
DEFAULT_BRANCH = "main"
DEFAULT_STATE_PATH = "margin/live_state_2026.json"
OWNER_EMAIL_SECRET = "PROPWAR_OWNER_EMAIL"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def commit_pick_state(state: dict[str, Any], audit: dict[str, Any], team: str, *, now_iso: str | None = None) -> dict[str, Any]:
    """Return a new state with the current week's selected team committed.

    This records the user's internal Margin War Room selection. It does not submit
    anything to an external contest website.
    """
    updated = deepcopy(state)
    week = int(updated["current_week"])
    if int(updated.get("completed_week", 0)) >= week:
        raise ValueError(f"Week {week} is already completed")

    team = championship.canon_team(team)
    if team not in championship.VALID_TEAMS:
        raise ValueError(f"invalid NFL team: {team}")
    if team in set(str(x) for x in updated.get("used_teams", [])):
        raise ValueError(f"{team} is already used")

    if int(audit.get("season", 0)) != int(updated.get("season", 0)) or int(audit.get("week", 0)) != week:
        raise ValueError("audit snapshot does not match current state week")

    board = {str(row["team"]): row for row in audit.get("board", [])}
    if team not in board:
        raise ValueError(f"{team} is not eligible on the current board")
    row = board[team]

    decision = dict(updated.get("current_decision") or {})
    decision.update({
        "status": "COMMITTED",
        "committed_pick": team,
        "committed_at_utc": now_iso or _now_iso(),
        "provisional_pick": str(audit.get("policy", {}).get("expected_points_pick") or audit.get("pick", {}).get("team")),
        "anchor": str(audit.get("policy", {}).get("anchor") or audit.get("anchor", {}).get("team")),
        "market_snapshot_utc": str(audit.get("snapshot_utc")),
        "current_spread": float(row["current_spread"]),
        "calibrated_expected_margin": float(row["calibrated_margin"]),
        "p_loss": float(row["p_loss"]),
        "p_win20": float(row["p_win20"]),
        "expected_points_pick": str(audit.get("policy", {}).get("expected_points_pick")),
        "championship_override_applied": bool(audit.get("policy", {}).get("championship_override_applied", False)),
        "reason": "User committed this team in Margin War Room.",
    })
    updated["current_decision"] = decision
    return updated


def complete_week_state(state: dict[str, Any], actual_margin: float, *, now_iso: str | None = None) -> dict[str, Any]:
    """Return a new state with the committed current week finalized."""
    updated = deepcopy(state)
    week = int(updated["current_week"])
    completed = int(updated.get("completed_week", 0))
    if completed >= week:
        raise ValueError(f"Week {week} is already completed")

    decision = dict(updated.get("current_decision") or {})
    team = decision.get("committed_pick")
    if not team or str(decision.get("status")) != "COMMITTED":
        raise ValueError("A team must be committed before the week can be completed")
    team = championship.canon_team(team)

    margin = float(actual_margin)
    used = [championship.canon_team(x) for x in updated.get("used_teams", [])]
    if team in used:
        raise ValueError(f"{team} is already in used_teams")
    if any(int(r.get("week", -1)) == week for r in updated.get("weekly_results", [])):
        raise ValueError(f"Week {week} already exists in weekly_results")

    used.append(team)
    results = list(updated.get("weekly_results", []))
    results.append({
        "week": week,
        "team": team,
        "actual_margin": margin,
        "completed_at_utc": now_iso or _now_iso(),
    })

    updated["used_teams"] = used
    updated["weekly_results"] = results
    updated["completed_week"] = week
    updated["cumulative_score"] = float(sum(float(r["actual_margin"]) for r in results))
    updated["season_complete"] = bool(week >= 18)
    if week < 18:
        updated["current_week"] = week + 1

    updated["current_decision"] = {
        "status": "SEASON_COMPLETE" if week >= 18 else "NEEDS_REFRESH",
        "provisional_pick": None,
        "committed_pick": None,
        "anchor": None,
        "market_snapshot_utc": None,
        "current_spread": None,
        "calibrated_expected_margin": None,
        "p_loss": None,
        "p_win20": None,
        "reason": "Previous week completed; refresh live markets for the next recommendation." if week < 18 else "2026 regular season completed.",
    }
    return updated


def write_config_from_secrets(secrets: Mapping[str, Any]) -> dict[str, str] | None:
    """Return private GitHub state configuration without making an auth decision."""
    token = str(secrets.get("MARGIN_GITHUB_TOKEN", "")).strip()
    repo = str(secrets.get("MARGIN_GITHUB_REPO", "")).strip()
    if not token or not repo:
        return None
    return {
        "token": token,
        "repo": repo,
        "branch": str(secrets.get("MARGIN_GITHUB_BRANCH", DEFAULT_BRANCH)).strip() or DEFAULT_BRANCH,
        "path": str(secrets.get("MARGIN_STATE_PATH", DEFAULT_STATE_PATH)).strip() or DEFAULT_STATE_PATH,
    }


def _oidc_configured(secrets: Mapping[str, Any]) -> bool:
    auth = secrets.get("auth")
    if not isinstance(auth, Mapping):
        return False
    owner_email = str(secrets.get(OWNER_EMAIL_SECRET, "")).strip()
    required = ["redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url"]
    return bool(owner_email and all(str(auth.get(key, "")).strip() for key in required))


def config_from_secrets(secrets: Mapping[str, Any]) -> dict[str, str] | None:
    """Return private state config only when owner OIDC is fully configured."""
    config = write_config_from_secrets(secrets)
    if config is None or not _oidc_configured(secrets):
        return None
    return {
        **config,
        "auth_mode": "OIDC_OWNER",
        "owner_email": str(secrets.get(OWNER_EMAIL_SECRET, "")).strip().casefold(),
    }


def _current_streamlit_user() -> dict[str, Any]:
    try:
        import streamlit as st

        if hasattr(st.user, "to_dict"):
            return dict(st.user.to_dict())
        return dict(st.user)
    except Exception:
        return {}


def owner_write_authorized(config: Mapping[str, str]) -> bool:
    """Authorize Margin writes only for the authenticated configured OIDC owner."""
    if str(config.get("auth_mode")) != "OIDC_OWNER":
        return False
    user = _current_streamlit_user()
    if not bool(user.get("is_logged_in", False)):
        return False
    actual = str(user.get("email", "")).strip().casefold()
    expected = str(config.get("owner_email", "")).strip().casefold()
    if not actual or actual != expected:
        return False
    return user.get("email_verified") is not False


def _github_json(config: Mapping[str, str], method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {config['token']}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PropWar-Margin-War-Room",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub state request failed ({exc.code}): {body[:300]}") from exc


def assert_private_repository(config: Mapping[str, str]) -> None:
    """Fail closed unless the configured Margin state repository is private."""
    repo = str(config.get("repo", "")).strip()
    if not repo or repo.casefold() == PUBLIC_APP_REPO.casefold():
        raise RuntimeError("Margin state repository must be a separate private GitHub repository.")
    metadata = _github_json(config, "GET", f"https://api.github.com/repos/{repo}")
    is_private = bool(metadata.get("private")) or str(metadata.get("visibility", "")).casefold() == "private"
    if not is_private:
        raise RuntimeError("Configured Margin state repository is not private; refusing to load or write personal pool data.")


def fetch_remote_state(config: Mapping[str, str]) -> tuple[dict[str, Any], str]:
    assert_private_repository(config)
    repo = config["repo"]
    path = config["path"]
    branch = config["branch"]
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    payload = _github_json(config, "GET", url)
    raw = base64.b64decode(payload["content"]).decode("utf-8")
    state = json.loads(raw)
    if not isinstance(state, dict):
        raise RuntimeError("Private Margin state file must contain one JSON object.")
    return state, str(payload["sha"])


def write_remote_state(config: Mapping[str, str], state: dict[str, Any], *, expected_sha: str, message: str) -> str:
    assert_private_repository(config)
    repo = config["repo"]
    path = config["path"]
    branch = config["branch"]
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    encoded = base64.b64encode((json.dumps(state, indent=2) + "\n").encode("utf-8")).decode("ascii")
    payload = _github_json(config, "PUT", url, {
        "message": message,
        "content": encoded,
        "sha": expected_sha,
        "branch": branch,
    })
    return str(payload.get("commit", {}).get("sha", ""))
