from __future__ import annotations
from pathlib import Path
from typing import Iterable
import pandas as pd
from src.common import output_path,project_path
from src.load.build_identity_crosswalk import canonical_team,normalize_player_name
MAP_COLUMNS=["player_id","player_name","team","position","current_team","projected_role","starter_status","depth_chart_rank","projected_snap_share","projected_route_share","projected_carry_share","projected_target_share","role_confidence","source","updated_at","manual_override","role_mapping_status","validation_status","notes"]
def truthy(v):return str(v).strip().lower() in {"1","true","yes","y","approved"}
def read_many(paths:Iterable[Path]):
 frames=[]
 for p in paths:
  try:d=pd.read_csv(p,low_memory=False)
  except pd.errors.EmptyDataError:continue
  if not d.empty:d["_input_file"]=str(p);frames.append(d)
 return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
def discover_real_inputs(role_dir:Path):
 files=list(role_dir.glob("*.csv")) if role_dir.exists() else [];real=[p for p in files if "template" not in p.name.lower()];overrides=[p for p in real if "override" in p.name.lower()];return sorted([p for p in real if "override" not in p.name.lower()]),sorted(overrides)
def candidates(identity,pid,name):
 if identity.empty:return identity
 if pid:
  x=identity[identity.player_id.fillna("").astype(str).str.strip().eq(pid)]
  if not x.empty:return x
 return identity[identity.normalized_player_name.fillna("").astype(str).eq(name)]
def latest(x):
 if x.empty:return None
 q=x.copy();q["_season"]=pd.to_numeric(q.get("season_max"),errors="coerce").fillna(-1);return q.sort_values(["_season","team"],ascending=[False,True]).iloc[0]
def build_map_from_frames(roles,overrides,identity,roster):
 if roles.empty:return pd.DataFrame(columns=MAP_COLUMNS)
 d=roles.copy();base=["player_id","player_name","team","position","projected_role","starter_status","depth_chart_rank","projected_snap_share","projected_route_share","projected_carry_share","projected_target_share","role_confidence","source","source_url","updated_at","manual_override","notes"]
 for c in base:
  if c not in d.columns:d[c]=""
 d["player_id"]=d.player_id.fillna("").astype(str).str.strip();d["player_name"]=d.player_name.fillna("").astype(str).str.strip();d["normalized_player_name"]=d.player_name.map(normalize_player_name);d["team"]=d.team.map(canonical_team)
 ov={}
 if not overrides.empty:
  o=overrides.copy()
  for c in ["player_id","player_name","approved"]+[f"override_{x}" for x in ["projected_role","starter_status","depth_chart_rank","snap_share","route_share","carry_share","target_share"]]:
   if c not in o.columns:o[c]=""
  o["player_id"]=o.player_id.fillna("").astype(str).str.strip();o["normalized_player_name"]=o.player_name.map(normalize_player_name)
  for _,r in o.iterrows():ov[r.player_id or "name:"+r.normalized_player_name]=r
 roster_by_id={}
 if not roster.empty and "player_id" in roster.columns:
  for _,r in roster.iterrows():roster_by_id[str(r.player_id).strip()]=r
 rows=[]
 for _,r in d.iterrows():
  pid=r.player_id;name=r.normalized_player_name;x=candidates(identity,pid,name);ident=latest(x);id_exact=bool(pid and not x.empty and x.player_id.fillna("").astype(str).str.strip().eq(pid).any());override=ov.get(pid or "name:"+name);approved=bool(override is not None and truthy(override.get("approved",False)))
  values={"projected_role":r.projected_role,"starter_status":r.starter_status,"depth_chart_rank":r.depth_chart_rank,"projected_snap_share":r.projected_snap_share,"projected_route_share":r.projected_route_share,"projected_carry_share":r.projected_carry_share,"projected_target_share":r.projected_target_share}
  if approved:
   for target,source in [("projected_role","override_projected_role"),("starter_status","override_starter_status"),("depth_chart_rank","override_depth_chart_rank"),("projected_snap_share","override_snap_share"),("projected_route_share","override_route_share"),("projected_carry_share","override_carry_share"),("projected_target_share","override_target_share")]:
    v=override.get(source,"");values[target]=v if pd.notna(v) and str(v).strip() else values[target]
  team=canonical_team(r.team);rr=roster_by_id.get(pid);current_team=canonical_team(rr.get("current_team","")) if rr is not None else "";roster_ready=bool(rr is not None and str(rr.get("team_mapping_status",""))=="READY");confidence=str(r.role_confidence).strip().lower();starter=str(values["starter_status"]).strip().lower();reasons=[]
  if x.empty:status="BLOCKED";validation="UNMATCHED_PLAYER";reasons.append("Role row cannot be matched to identity crosswalk.")
  elif not pid:status="NEEDS REVIEW";validation="MISSING_PLAYER_ID";reasons.append("Missing player_id; name-only role requires review.")
  elif not id_exact:status="BLOCKED";validation="IDENTITY_CONFLICT";reasons.append("Role identity conflicts with player_id.")
  elif rr is not None and (not roster_ready or team!=current_team):status="BLOCKED";validation="TEAM_MISMATCH";reasons.append("Role team does not match a READY current roster mapping.")
  elif rr is None:status="NEEDS REVIEW";validation="CURRENT_TEAM_UNVERIFIED";reasons.append("No verified current roster mapping is available for this player.")
  elif truthy(r.manual_override) and not approved:status="NEEDS REVIEW";validation="OVERRIDE_NOT_APPROVED";reasons.append("Manual role override is not approved.")
  elif not approved and (confidence not in {"high","medium"} or starter in {"","unknown"} or str(values["projected_role"]).strip().lower() in {"","unknown"}):status="NEEDS REVIEW";validation="ROLE_UNCERTAIN";reasons.append("Role confidence or starter status is not sufficiently verified.")
  else:status="READY";validation="PASS";reasons.append("Verified role and current-team match." if not approved else "Approved role override applied.")
  rows.append({"player_id":pid,"player_name":r.player_name,"team":team,"position":r.position or (ident.get("position","") if ident is not None else ""),"current_team":current_team,**values,"role_confidence":"high" if approved else confidence,"source":r.source,"updated_at":r.updated_at,"manual_override":approved,"role_mapping_status":status,"validation_status":validation,"notes":" ".join(reasons)})
 return pd.DataFrame(rows,columns=MAP_COLUMNS)
def build_current_role_map(role_dir=None,identity_path=None,roster_path=None):
 role_dir=role_dir or project_path("data","gates","roles");identity_path=identity_path or output_path("identity/player_identity_crosswalk.csv");roster_path=roster_path or output_path("roster/current_roster_map.csv");rp,op=discover_real_inputs(role_dir);roles=read_many(rp);overrides=read_many(op);identity=pd.read_csv(identity_path,low_memory=False) if identity_path.exists() else pd.DataFrame();roster=pd.read_csv(roster_path,low_memory=False) if roster_path.exists() else pd.DataFrame();mapped=build_map_from_frames(roles,overrides,identity,roster);review=mapped[mapped.role_mapping_status.ne("READY")].copy() if not mapped.empty else mapped.copy();counts=mapped.role_mapping_status.value_counts() if not mapped.empty else pd.Series(dtype=int);overall="NEEDS DATA" if not rp or mapped.empty else ("BLOCKED" if counts.get("BLOCKED",0) else ("NEEDS REVIEW" if counts.get("NEEDS REVIEW",0) or counts.get("NEEDS DATA",0) else "READY"));status=pd.DataFrame([{"status":overall,"real_role_files":len(rp),"override_files":len(op),"role_rows_loaded":len(mapped),"ready_rows":int(counts.get("READY",0)),"needs_review_rows":int(counts.get("NEEDS REVIEW",0)),"needs_data_rows":int(counts.get("NEEDS DATA",0)),"blocked_rows":int(counts.get("BLOCKED",0)),"manual_overrides":int(mapped.manual_override.map(truthy).sum()) if not mapped.empty else 0,"low_confidence_roles":int(mapped.role_confidence.astype(str).str.lower().isin({"low","unknown",""}).sum()) if not mapped.empty else 0,"templates_ignored":True,"notes":"No real current role input found; template files do not count as data." if overall=="NEEDS DATA" else "Current role map built from non-template inputs."}]);mapped.to_csv(output_path("roles/current_role_map.csv"),index=False);status.to_csv(output_path("roles/current_role_map_status.csv"),index=False);review.to_csv(output_path("roles/current_role_needs_review.csv"),index=False);return mapped,status,review
def main():
 m,s,r=build_current_role_map();print(f"current_role_map: {len(m):,} rows");print(f"current_role_needs_review: {len(r):,} rows");print(f"current_role_map_status: {s.status.iloc[0]}");print("template_files_count_as_data: False")
if __name__=="__main__":main()
