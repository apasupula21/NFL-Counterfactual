from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError, field_validator

# -------------------------
# FastAPI + CORS
# -------------------------
app = FastAPI(title="NFL Counterfactual API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # <-- front-end dev origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Core schemas
# -------------------------
HashT = Literal["LEFT", "MIDDLE", "RIGHT"]
ActionTypeT = Literal["RUN", "PASS", "FIELD_GOAL", "PUNT", "QB_SNEAK", "SPIKE", "KNEEL", "TRICK"]
PassDepthT = Optional[Literal["SCREEN", "SHORT", "INTERMEDIATE", "DEEP"]]
PassAreaT = Optional[Literal["LEFT", "MIDDLE", "RIGHT"]]

class StateSpec(BaseModel):
    offense: str
    defense: str
    quarter: int = Field(ge=1, le=4)
    clock_seconds: int = Field(ge=0, le=900)
    down: int = Field(ge=1, le=4)
    distance: int = Field(ge=1, le=99)
    yardline_100: int = Field(ge=1, le=99)
    off_timeouts: int = Field(ge=0, le=3, default=3)
    def_timeouts: int = Field(ge=0, le=3, default=3)
    score_off: int = Field(ge=0, default=0)
    score_def: int = Field(ge=0, default=0)
    hash: HashT = "MIDDLE"

    @field_validator("offense", "defense")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

class ActionSpec(BaseModel):
    type: ActionTypeT
    pass_depth: PassDepthT = None
    pass_area: PassAreaT = None
    play_action: bool = False
    personnel_offense: Optional[Literal["10", "11", "12", "13", "20", "21", "22"]] = None
    route_concept: Optional[str] = None

class ContextSpec(BaseModel):
    coverage_hint: Optional[str] = None
    weather: Optional[str] = None

class PlaySpec(BaseModel):
    state: StateSpec
    action: ActionSpec
    context: Optional[ContextSpec] = None

# -------------------------
# Deterministic parser
# -------------------------
DOWN_RE = re.compile(r"\b(1st|first|2nd|second|3rd|third|4th|fourth)\b", re.I)
DIST_RE = re.compile(r"&\s*(\d{1,2})\b")
QTR_RE = re.compile(r"\bQ([1-4])\b", re.I)
CLOCK_RE = re.compile(r"\b(\d{1,2}):([0-5]\d)\b")
YARD_BY_TEAM_RE = re.compile(r"\b([A-Z]{2,5})\s*(\d{1,2})\b")
OWN_RE = re.compile(r"\bown\s*(\d{1,2})\b", re.I)
OPP_RE = re.compile(r"\b(opp|opponent)\s*(\d{1,2})\b", re.I)
HASH_RE = re.compile(r"\b(left hash|right hash|middle hash|left|right|middle)\b", re.I)
PERSONNEL_RE = re.compile(r"\b(10|11|12|13|20|21|22)\s*(?:personnel)?\b", re.I)

PASS_HINTS = {
    "screen": "SCREEN",
    "quick": "SHORT",
    "short": "SHORT",
    "slant": "SHORT",
    "intermediate": "INTERMEDIATE",
    "dig": "INTERMEDIATE",
    "deep": "DEEP",
    "shot": "DEEP",
    "go route": "DEEP",
    "post": "DEEP",
}
AREA_HINTS = {"left": "LEFT", "middle": "MIDDLE", "right": "RIGHT"}
ACTION_KEYWORDS: List[Tuple[str, ActionTypeT]] = [
    ("field goal", "FIELD_GOAL"), ("fg", "FIELD_GOAL"),
    ("punt", "PUNT"),
    ("sneak", "QB_SNEAK"), ("spike", "SPIKE"), ("kneel", "KNEEL"), ("trick", "TRICK"),
    ("pass", "PASS"), ("throw", "PASS"),
    ("rush", "RUN"), ("run", "RUN"), ("carry", "RUN"), ("handoff", "RUN"), ("draw", "RUN"),
    ("inside zone", "RUN"), ("outside zone", "RUN"),
]

def _parse_down(text: str) -> int:
    m = DOWN_RE.search(text); 
    if not m: return 1
    return {"1st":1,"first":1,"2nd":2,"second":2,"3rd":3,"third":3,"4th":4,"fourth":4}[m.group(1).lower()]

def _parse_distance(text: str) -> int:
    m = DIST_RE.search(text); return int(m.group(1)) if m else 10

def _parse_quarter(text: str) -> int:
    m = QTR_RE.search(text); return int(m.group(1)) if m else 1

def _parse_clock_seconds(text: str) -> int:
    m = CLOCK_RE.search(text)
    if not m: return 900
    return max(0, min(900, int(m.group(1))*60 + int(m.group(2))))

def _parse_hash(text: str) -> HashT:
    m = HASH_RE.search(text)
    if not m: return "MIDDLE"
    tok = m.group(1).lower()
    return "LEFT" if "left" in tok else "RIGHT" if "right" in tok else "MIDDLE"

def _parse_yardline_100(text: str, offense: str, defense: str) -> int:
    m = OWN_RE.search(text)
    if m: return 100 - int(m.group(1))
    m = OPP_RE.search(text)
    if m: return int(m.group(1))
    m = YARD_BY_TEAM_RE.search(text)
    if m:
        team, yd = m.group(1).upper(), int(m.group(2))
        if team == offense.upper(): return 100 - yd
        if team == defense.upper(): return yd
        return yd
    return 75

def _parse_action(text: str) -> ActionSpec:
    t_lower = text.lower()
    a_type: ActionTypeT = "RUN"
    for kw, t in ACTION_KEYWORDS:
        if kw in t_lower: a_type = t; break
    depth = None; area = None
    if a_type == "PASS":
        for k, v in PASS_HINTS.items():
            if k in t_lower: depth = v
        for k, v in AREA_HINTS.items():
            if re.search(rf"\b{k}\b", t_lower): area = v
    play_action = "play-action" in t_lower or "play action" in t_lower
    m_per = PERSONNEL_RE.search(text)
    personnel = m_per.group(1) if m_per else None
    return ActionSpec(type=a_type, pass_depth=depth, pass_area=area, play_action=play_action, personnel_offense=personnel)

class ParseRequest(BaseModel):
    text: str
    offense: str
    defense: str

class ParseResponse(BaseModel):
    spec: PlaySpec
    warnings: List[str] = []

def validate_and_autofix(spec: PlaySpec) -> Tuple[PlaySpec, List[str]]:
    w: List[str] = []
    s = spec.model_copy(deep=True)
    if s.state.distance > s.state.yardline_100:
        w.append(f"distance {s.state.distance} > yards-to-goal {s.state.yardline_100}; clamped")
        s.state.distance = s.state.yardline_100
    s.state.clock_seconds = max(0, min(900, s.state.clock_seconds))
    if s.action.type == "FIELD_GOAL" and s.state.yardline_100 + 17 > 60:
        w.append(f"Very long FG attempt (~{s.state.yardline_100 + 17} yards).")
    if s.action.type == "PUNT" and s.state.yardline_100 < 60:
        w.append("Punting inside opponent 40 is uncommon.")
    return s, w

def parse_freeform_to_spec(req: ParseRequest) -> Tuple[PlaySpec, List[str]]:
    text = req.text
    offense = req.offense.upper(); defense = req.defense.upper()
    state = StateSpec(
        offense=offense, defense=defense,
        quarter=_parse_quarter(text), clock_seconds=_parse_clock_seconds(text),
        down=_parse_down(text), distance=_parse_distance(text),
        yardline_100=_parse_yardline_100(text, offense, defense),
        hash=_parse_hash(text),
        off_timeouts=3, def_timeouts=3, score_off=0, score_def=0
    )
    action = _parse_action(text)
    spec = PlaySpec(state=state, action=action)
    return validate_and_autofix(spec)

# -------------------------
# Sim helpers
# -------------------------
def playspec_to_state_action(spec: PlaySpec) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    st, ac = spec.state, spec.action
    return (
        {
            "down": st.down, "distance": st.distance, "yardline_100": st.yardline_100,
            "quarter": st.quarter, "clock_seconds": st.clock_seconds,
            "off_timeouts": st.off_timeouts, "def_timeouts": st.def_timeouts, "hash": st.hash,
        },
        {
            "type": ac.type, "pass_depth": ac.pass_depth, "pass_area": ac.pass_area,
            "play_action": ac.play_action, "personnel_offense": ac.personnel_offense,
        },
    )

def _sample_yards(action: Dict[str, Any]) -> int:
    t = action["type"]
    if t == "QB_SNEAK": y = random.gauss(1.0, 0.7)
    elif t == "RUN":     y = random.gauss(4.3, 3.0)
    elif t == "PASS":
        depth = (action.get("pass_depth") or "SHORT").upper()
        mu = {"SCREEN": 1.0, "SHORT": 5.5, "INTERMEDIATE": 9.0, "DEEP": 15.0}.get(depth, 6.0)
        y = random.gauss(mu, 7.0)
    elif t == "SPIKE":   y = 0.0
    elif t == "KNEEL":   y = -1.0
    elif t == "TRICK":   y = random.gauss(8.0, 12.0)
    else:                y = random.gauss(3.0, 5.0)
    return int(round(max(-15.0, min(80.0, y))))

def _field_goal_make_prob(yl100: int) -> float:
    kick = yl100 + 17
    if   kick <= 20: return 0.99
    elif kick <= 30: return 0.97
    elif kick <= 40: return 0.92
    elif kick <= 50: return 0.78
    elif kick <= 60: return 0.55
    else:            return 0.15

# Single-play simulation (kept because your UI calls it)
class SimRequest(BaseModel):
    spec: PlaySpec
    n: int = Field(default=1000, ge=100, le=5000)
    seed: Optional[int] = None

class SimResponse(BaseModel):
    yards_mean: float
    yards_p10: float
    yards_p50: float
    yards_p90: float
    td_rate: float
    fg_rate: float
    turnover_rate: float
    assumptions: List[str]
    seed: int

def simulate_next_play(req: SimRequest) -> SimResponse:
    seed = random.randrange(1_000_000_000) if req.seed is None else int(req.seed)
    rng = random.Random(seed)
    state, action = playspec_to_state_action(req.spec)

    # FG
    if action["type"] == "FIELD_GOAL":
        p = _field_goal_make_prob(state["yardline_100"])
        made = sum(1 for _ in range(req.n) if rng.random() < p)
        miss = req.n - made
        return SimResponse(0.0, 0.0, 0.0, 0.0, 0.0, made/req.n, miss/req.n,
                           [f"FG make prob from {state['yardline_100']+17}y ≈ {p:.2f}"], seed)

    # Punt (return net yards distribution as "yards")
    if action["type"] == "PUNT":
        base = 42 if state["yardline_100"] > 70 else 38
        mu = base - int((100 - state["yardline_100"]) * 0.15)
        samples = [int(round(max(25, min(70, rng.gauss(mu, 6))))) for _ in range(req.n)]
        samples.sort(); n=len(samples)
        return SimResponse(sum(samples)/n, float(samples[int(0.1*(n-1))]),
                           float(samples[int(0.5*(n-1))]), float(samples[int(0.9*(n-1))]),
                           0.0, 0.0, 0.0, ["Net punt yards heuristic"], seed)

    yl = state["yardline_100"]; dist = state["distance"]; down = state["down"]
    yards: List[int] = []; td = 0; tos = 0
    for _ in range(req.n):
        y = _sample_yards(action); yards.append(y)
        if yl - max(0, y) <= 0: td += 1
        if down == 4 and y < dist: tos += 1
    yards.sort(); n=len(yards)
    return SimResponse(sum(yards)/n, float(yards[int(0.1*(n-1))]),
                       float(yards[int(0.5*(n-1))]), float(yards[int(0.9*(n-1))]),
                       td/n, 0.0, tos/n,
                       ["Heuristic outcome distributions by action type; 4th-down turnover on fail"], seed)

# Drive simulation classes
from typing import Literal as _Literal

class DriveRequest(BaseModel):
    spec: PlaySpec
    n: int = Field(default=1, ge=1, le=20)
    seed: Optional[int] = None

class DrivePlay(BaseModel):
    down: int
    distance: int
    yardline_100: int
    call_type: ActionTypeT
    yards: int
    result: _Literal["GAIN","FIRST_DOWN","TOUCHDOWN","TURNOVER_ON_DOWNS","FIELD_GOAL_GOOD","FIELD_GOAL_MISS","PUNT"]

class DriveSummary(BaseModel):
    plays: List[DrivePlay]
    points_for_offense: int
    time_elapsed_seconds: int
    ended: _Literal["TD","FG_GOOD","FG_MISS","PUNT","DOWNS","EXHAUSTED"]

def _clock_tick(rng: random.Random, action_type: str) -> int:
    base = 6 if action_type == "PASS" else 7
    return base + rng.randint(0, 3)

def _attempt_field_goal(rng: random.Random, yl100: int) -> Tuple[bool, DrivePlay]:
    p = _field_goal_make_prob(yl100)
    made = rng.random() < p
    play = DrivePlay(down=4, distance=0, yardline_100=yl100, call_type="FIELD_GOAL", yards=0,
                     result="FIELD_GOAL_GOOD" if made else "FIELD_GOAL_MISS")
    return made, play

def _attempt_punt(rng: random.Random, yl100: int) -> DrivePlay:
    base = 42 if yl100 > 70 else 38
    mu = base - int((100 - yl100) * 0.15)
    net = int(round(max(25, min(70, rng.gauss(mu, 6)))))
    return DrivePlay(down=4, distance=0, yardline_100=yl100, call_type="PUNT", yards=net, result="PUNT")

def simulate_drive_once(spec: PlaySpec, seed: Optional[int] = None) -> DriveSummary:
    st, ac = playspec_to_state_action(spec)
    rng = random.Random(seed if seed is not None else random.randrange(1_000_000_000))

    down = st["down"]
    dist = st["distance"]
    yl = st["yardline_100"]
    clock = st["clock_seconds"]

    plays: List[DrivePlay] = []
    points = 0
    elapsed = 0

    while True:
        # out of time this quarter (v1 stop rule)
        if clock <= 0:
            return DriveSummary(
                plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="EXHAUSTED"
            )

        # 4th-down simple decision policy
        if down == 4:
            # FG if <= 60 yd attempt
            if yl + 17 <= 60:
                made, fg_play = _attempt_field_goal(rng, yl)
                plays.append(fg_play)
                t = _clock_tick(rng, "FIELD_GOAL")
                elapsed += t
                clock -= t
                if made:
                    points += 3
                    return DriveSummary(
                        plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="FG_GOOD"
                    )
                else:
                    return DriveSummary(
                        plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="FG_MISS"
                    )
            # Punt if outside opp 40 (yl >= 60 means ball ≥ own 40)
            if yl >= 60:
                punt_play = _attempt_punt(rng, yl)
                plays.append(punt_play)
                t = _clock_tick(rng, "PUNT")
                elapsed += t
                clock -= t
                return DriveSummary(
                    plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="PUNT"
                )
            # else: go for it (fall through to run a normal play)

        # choose call: first snap = requested action, then simple policy
        if plays:
            if down == 3 and dist >= 6:
                ac_type = "PASS"
                sample_action = {"type": "PASS", "pass_depth": "INTERMEDIATE"}
            else:
                ac_type = "RUN"
                sample_action = {"type": "RUN"}
        else:
            ac_type = ac["type"]
            sample_action = ac

        # record pre-snap state for the row
        pre_down = down
        pre_dist = dist
        pre_yl = yl

        y = _sample_yards(sample_action)  # can be negative
        # touchdown if ball crosses the goal line
        if pre_yl - max(0, y) <= 0:
            plays.append(
                DrivePlay(
                    down=pre_down,
                    distance=pre_dist,
                    yardline_100=pre_yl,
                    call_type=ac_type,  # type: ignore
                    yards=y,
                    result="TOUCHDOWN",
                )
            )
            t = _clock_tick(rng, ac_type)
            elapsed += t
            clock -= t
            points += 6  # (ignore XP/2pt for v1)
            return DriveSummary(
                plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="TD"
            )

        # update ball & line to gain using the ACTUAL yards (negative moves backward)
        yl = int(max(1, min(99, pre_yl - y)))   # if y is negative, yl increases (backward)
        gained = y >= pre_dist
        if gained:
            down = 1
            dist = 10 if yl > 10 else yl
            result = "FIRST_DOWN"
        else:
            down = pre_down + 1
            dist = max(1, pre_dist - y)         # if y is negative, distance increases

            # turnover on downs if we just exceeded 4th
            if down > 4:
                plays.append(
                    DrivePlay(
                        down=4,
                        distance=dist,
                        yardline_100=yl,
                        call_type=ac_type,  # type: ignore
                        yards=y,
                        result="TURNOVER_ON_DOWNS",
                    )
                )
                t = _clock_tick(rng, ac_type)
                elapsed += t
                clock -= t
                return DriveSummary(
                    plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="DOWNS"
                )
            result = "GAIN"

        # append the snap row with the PRE-snap down/dist/yardline (what users expect)
        plays.append(
            DrivePlay(
                down=pre_down,
                distance=pre_dist,
                yardline_100=pre_yl,
                call_type=ac_type,  # type: ignore
                yards=y,
                result=result,
            )
        )

        # tick clock once per snap
        t = _clock_tick(rng, ac_type)
        elapsed += t
        clock -= t
    st, ac = playspec_to_state_action(spec)
    rng = random.Random(seed if seed is not None else random.randrange(1_000_000_000))
    down, dist, yl = st["down"], st["distance"], st["yardline_100"]
    clock = st["clock_seconds"]
    plays: List[DrivePlay] = []; points = 0; elapsed = 0

    while True:
        if clock <= 0:
            return DriveSummary(plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="EXHAUSTED")

        if down == 4:
            if yl + 17 <= 60:
                made, fg_play = _attempt_field_goal(rng, yl)
                plays.append(fg_play); t=_clock_tick(rng,"FIELD_GOAL"); elapsed+=t; clock-=t
                if made:
                    points += 3
                    return DriveSummary(plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="FG_GOOD")
                else:
                    return DriveSummary(plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="FG_MISS")
            if yl >= 60:
                punt_play = _attempt_punt(rng, yl)
                plays.append(punt_play); t=_clock_tick(rng,"PUNT"); elapsed+=t; clock-=t
                return DriveSummary(plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="PUNT")
            # else, go for it

        if plays:
            if down == 3 and dist >= 6:
                ac_type = "PASS"; sample_action = {"type":"PASS","pass_depth":"INTERMEDIATE"}
            else:
                ac_type = "RUN"; sample_action = {"type":"RUN"}
        else:
            ac_type = ac["type"]; sample_action = ac

        y = _sample_yards(sample_action)
        td = (yl - max(0, y) <= 0)
        if td:
            plays.append(DrivePlay(down=down, distance=dist, yardline_100=yl, call_type=ac_type, yards=y, result="TOUCHDOWN"))
            t=_clock_tick(rng, ac_type); elapsed+=t; clock-=t
            points += 6
            return DriveSummary(plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="TD")

        gained = y >= dist
        yl = max(1, yl - max(0, y))
        if gained:
            dist = 10 if yl > 10 else yl
            down = 1
            result = "FIRST_DOWN"
        else:
            dist = max(1, dist - max(0, y))
            down += 1
            result = "GAIN"
            if down > 4:
                plays.append(DrivePlay(down=4, distance=dist, yardline_100=yl, call_type=ac_type, yards=y, result="TURNOVER_ON_DOWNS"))
                t=_clock_tick(rng, ac_type); elapsed+=t; clock-=t
                return DriveSummary(plays=plays, points_for_offense=points, time_elapsed_seconds=elapsed, ended="DOWNS")

        plays.append(DrivePlay(down=down, distance=dist, yardline_100=yl, call_type=ac_type, yards=y, result=result))
        t=_clock_tick(rng, ac_type); elapsed+=t; clock-=t

# -------------------------
# Routes
# -------------------------
@app.get("/health")
def health() -> Dict[str, bool]:
    return {"ok": True}

@app.post("/parse-freeform", response_model=ParseResponse)
def parse_freeform(req: ParseRequest) -> ParseResponse:
    spec, warnings = parse_freeform_to_spec(req)
    return ParseResponse(spec=spec, warnings=warnings)

@app.post("/simulate", response_model=SimResponse)
def simulate(req: SimRequest) -> SimResponse:
    try:
        _ = PlaySpec.model_validate(req.spec.model_dump())
    except ValidationError as e:
        raise e
    return simulate_next_play(req)

@app.post("/simulate-drive", response_model=DriveSummary)
def simulate_drive(req: DriveRequest) -> DriveSummary:
    spec = PlaySpec.model_validate(req.spec.model_dump())
    return simulate_drive_once(spec, seed=req.seed)
