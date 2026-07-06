from __future__ import annotations
from pathlib import Path
from typing import Iterable
import pandas as pd
from src.common import output_path,project_path
from src.load.build_identity_crosswalk import canonical_team,normalize_player_name
COLS=["player_id","player_name","team","position","current_team","projected_role","injury_status","injury_detail","practice_status","game_status","availability_risk","projection_action","source","updated_at","manual_override","injury_mapping_status","validation_status","notes"]
BLOCKED_INJURY={"out","ir","pup","suspended"};BLOCKED_GAME={"out","inactive"}
def truthy(v):return str(v).strip().lower() in {"1","true","yes","y","approved"}
def read_many(paths:Iterable[Path]):
 frames=[]
 for p in paths:
  try:d=pd.read_csv(p,low_memory=False)
  except pd.errors.EmptyDataError:continue
  if not d.empty:d["_input_file"]=str(p);frames.append(d)
 return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
def discover_real_inputs(d:Path):
 files=list(d.glob("*.csv")) if d.exists() else [];real=[p for p in files if "template" not in p.name.lower()];ov=[p for p in real if "override" in p.name.lower()];return sorted([p for p in real if "override" not in p.name.lower()]),sorted(ov)
def identity_candidates(identity,pid,name):
 if identity.empty:return identity
 if pid:
  x=identity[identity.player_id.fillna("").astype(str).str.strip().eq(pid)]
  if not x.empty:return x
 return identity[identity.normalized_player_name.fillna("").astype(str).eq(name)]
def build_map_from_frames(injuries,overrides,identity,roster,roles):
 if injuries.empty:return pd.DataFrame(columns=COLS)
 d=injuries.copy();base=["player_id","player_name","team","position","injury_status","injury_detail","practice_status","game_status","availability_risk","projection_action","source","source_url","updated_at","manual_override","notes"]
 for c in base:
  if c not in d.columns:d[c]=""
 d["player_id"]=d.player_id.fillna("").astype(str).str.strip();d["player_name"]=d.player_name.fillna("").astype(str).str.strip();d["normalized_player_name"]=d.player_name.map(normalize_player_name);d["team"]=d.team.map(canonical_team)
 ov={}
 if not overrides.empty:
  o=overrides.copy()
  for c in ["player_id","player_name","approved","override_injury_status","override_practice_status","override_game_status","override_availability_risk","override_projection_action"]:
   if c not in o.columns:o[c]=""
  o["player_id"]=o.player_id.fillna("").astype(str).str.strip();o["normalized_player_name"]=o.player_name.map(normalize_player_name)
  for _,r in o.iterrows():ov[r.player_id or "name:"+r.normalized_player_name]=r
 rb={str(r.player_id).strip():r for _,r in roster.iterrows()} if not roster.empty and "player_id" in roster.columns else {};roleb={str(r.player_id).strip():r for _,r in roles.iterrows()} if not roles.empty and "player_id" in roles.columns else {};rows=[]
 for _,r in d.iterrows():
  pid=r.player_id;x=identity_candidates(identity,pid,r.normalized_player_name);id_exact=bool(pid and not x.empty and x.player_id.fillna("").astype(str).str.strip().eq(pid).any());rr=rb.get(pid);role=roleb.get(pid);team=canonical_team(r.team);current=canonical_team(rr.get("current_team","")) if rr is not None else "";roster_ready=bool(rr is not None and str(rr.get("team_mapping_status",""))=="READY");override=ov.get(pid or "name:"+r.normalized_player_name);approved=bool(override is not None and truthy(override.get("approved",False)));v={"injury_status":r.injury_status,"practice_status":r.practice_status,"game_status":r.game_status,"availability_risk":r.availability_risk,"projection_action":r.projection_action}
  if approved:
   for k in v:
    z=override.get("override_"+k,"");v[k]=z if pd.notna(z) and str(z).strip() else v[k]
  norm={k:str(z).strip().lower() for k,z in v.items()};reasons=[]
  if x.empty:status="BLOCKED";validation="UNMATCHED_PLAYER";reasons.append("Injury row cannot be matched to identity crosswalk.")
  elif not pid:status="NEEDS REVIEW";validation="MISSING_PLAYER_ID";reasons.append("Missing player_id; name-only availability requires review.")
  elif not id_exact:status="BLOCKED";validation="IDENTITY_CONFLICT";reasons.append("Injury identity conflicts with player_id.")
  elif rr is not None and (not roster_ready or team!=current):status="BLOCKED";validation="TEAM_MISMATCH";reasons.append("Injury team does not match a READY current roster mapping.")
  elif rr is None:status="NEEDS REVIEW";validation="CURRENT_TEAM_UNVERIFIED";reasons.append("No verified current roster mapping is available.")
  elif norm["injury_status"] in BLOCKED_INJURY or norm["game_status"] in BLOCKED_GAME or norm["projection_action"]=="block" or norm["availability_risk"]=="blocked":status="BLOCKED";validation="PLAYER_UNAVAILABLE";reasons.append("Player status blocks projected availability.")
  elif truthy(r.manual_override) and not approved:status="NEEDS REVIEW";validation="OVERRIDE_NOT_APPROVED";reasons.append("Manual injury override is not approved.")
  elif norm["injury_status"] in {"questionable","doubtful","unknown",""} or norm["practice_status"] in {"limited","dnp","unknown",""} or norm["game_status"] in {"questionable","doubtful","unknown",""} or norm["availability_risk"] in {"medium","high","unknown",""} or norm["projection_action"] in {"review","","unknown"}:status="NEEDS REVIEW";validation="AVAILABILITY_UNCERTAIN";reasons.append("Questionable or uncertain availability requires review.")
  elif norm["projection_action"] in {"allow","reduce"} and norm["availability_risk"] in {"none","low","medium"}:status="READY";validation="PASS";reasons.append("Availability verified." if not approved else "Approved injury override applied.")
  else:status="NEEDS REVIEW";validation="AVAILABILITY_UNCERTAIN";reasons.append("Availability combination requires review.")
  rows.append({"player_id":pid,"player_name":r.player_name,"team":team,"position":r.position,"current_team":current,"projected_role":role.get("projected_role","") if role is not None else "","injury_status":v["injury_status"],"injury_detail":r.injury_detail,"practice_status":v["practice_status"],"game_status":v["game_status"],"availability_risk":v["availability_risk"],"projection_action":v["projection_action"],"source":r.source,"updated_at":r.updated_at,"manual_override":approved,"injury_mapping_status":status,"validation_status":validation,"notes":" ".join(reasons)})
 return pd.DataFrame(rows,columns=COLS)
def build_current_injury_map(injury_dir=None,identity_path=None,roster_path=None,role_path=None):
 injury_dir=injury_dir or project_path("data","gates","injuries");identity_path=identity_path or output_path("identity/player_identity_crosswalk.csv");roster_path=roster_path or output_path("roster/current_roster_map.csv");role_path=role_path or output_path("roles/current_role_map.csv");ip,op=discover_real_inputs(injury_dir);inj=read_many(ip);ov=read_many(op);identity=pd.read_csv(identity_path,low_memory=False) if identity_path.exists() else pd.DataFrame();roster=pd.read_csv(roster_path,low_memory=False) if roster_path.exists() else pd.DataFrame();roles=pd.read_csv(role_path,low_memory=False) if role_path.exists() else pd.DataFrame();m=build_map_from_frames(inj,ov,identity,roster,roles);review=m[m.injury_mapping_status.ne("READY")].copy() if not m.empty else m.copy();c=m.injury_mapping_status.value_counts() if not m.empty else pd.Series(dtype=int);overall="NEEDS DATA" if not ip or m.empty else ("BLOCKED" if c.get("BLOCKED",0) else ("NEEDS REVIEW" if c.get("NEEDS REVIEW",0) or c.get("NEEDS DATA",0) else "READY"));q=int(((m.injury_status.astype(str).str.lower().eq("questionable"))|(m.practice_status.astype(str).str.lower().eq("limited"))).sum()) if not m.empty else 0;b=int((m.injury_status.astype(str).str.lower().isin(BLOCKED_INJURY)|m.game_status.astype(str).str.lower().isin(BLOCKED_GAME)).sum()) if not m.empty else 0;s=pd.DataFrame([{"status":overall,"real_injury_files":len(ip),"override_files":len(op),"injury_rows_loaded":len(m),"ready_rows":int(c.get("READY",0)),"needs_review_rows":int(c.get("NEEDS REVIEW",0)),"needs_data_rows":int(c.get("NEEDS DATA",0)),"blocked_rows":int(c.get("BLOCKED",0)),"questionable_limited_rows":q,"out_ir_inactive_rows":b,"manual_overrides":int(m.manual_override.map(truthy).sum()) if not m.empty else 0,"templates_ignored":True,"notes":"No real current injury input found; template files do not count as data." if overall=="NEEDS DATA" else "Current injury map built from non-template inputs."}]);m.to_csv(output_path("injuries/current_injury_map.csv"),index=False);s.to_csv(output_path("injuries/current_injury_map_status.csv"),index=False);review.to_csv(output_path("injuries/current_injury_needs_review.csv"),index=False);return m,s,review
def main():
 m,s,r=build_current_injury_map();print(f"current_injury_map: {len(m):,} rows");print(f"current_injury_needs_review: {len(r):,} rows");print(f"current_injury_map_status: {s.status.iloc[0]}");print("template_files_count_as_data: False")
if __name__=="__main__":main()
