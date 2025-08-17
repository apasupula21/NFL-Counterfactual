from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import random

print(">>> Loading backend/app/main.py")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

class ParseRequest(BaseModel):
    text: str
    offense: str
    defense: str

class ParseResponse(BaseModel):
    spec: dict
    warnings: Optional[List[str]] = []

@app.post("/parse-freeform", response_model=ParseResponse)
async def parse_freeform(req: ParseRequest):
    spec = {
        "situation": "3rd & 8",
        "yardline": f"{req.offense} 42",
        "quarter": 4,
        "time": "2:05",
        "score_diff": -3,
        "playcall": req.text,
        "offense": req.offense,
        "defense": req.defense
    }
    warnings: List[str] = []
    if "hail mary" in req.text.lower():
        warnings.append("Low-probability play detected.")
    return {"spec": spec, "warnings": warnings}

class SimulateRequest(BaseModel):
    spec: Dict
    n: int = Field(ge = 50, le = 5000, default = 1000)
    
class SimulateRespone(BaseModel):
    yards_mean: float
    yards_p10: float
    yards_p50: float
    yards_p90: float
    td_rate: float
    fg_rate: float
    turnover_rate: float
    
def _toy_yards_for_action(action: Dict) -> int:
    """very rough distribution; replace with your learned models later."""
    a_type = (action.get("type") or "").upper()
    depth = (action.get("pass_depth") or "").upper()

    if a_type == "RUN":
        return int(random.gauss(4, 3))
    if a_type == "PASS":
        base = {"SCREEN": 0, "SHORT": 4, "INTERMEDIATE": 8, "DEEP": 14}.get(depth, 6)
        return int(random.gauss(base, 7))
    if a_type == "QB_SNEAK":
        return int(random.gauss(1, 1))
    return int(random.gauss(3, 5))

@app.post("/simulate", response_model=SimulateResponse)
async def simulate(req: SimulateRequest):
    state = req.spec.get("state", {})
    action = req.spec.get("action", {})

    # simple FG handling based on rough kick distance
    if action.get("type") == "FIELD_GOAL":
        yl = int(state.get("yardline_100", 60))
        kick = yl + 17
        # crude make prob
        p = max(0.05, 0.95 - 0.02 * max(0, kick - 35))
        made = sum(1 for _ in range(req.n) if random.random() < p)
        miss = req.n - made
        # map to response fields
        return {
            "yards_mean": 0.0,
            "yards_p10": 0.0,
            "yards_p50": 0.0,
            "yards_p90": 0.0,
            "td_rate": 0.0,
            "fg_rate": made / req.n,
            "turnover_rate": miss / req.n,  # treat misses as turnover on downs
        }

    # generic run/pass-ish simulation
    samples = []
    tds = 0
    tos = 0
    fgs = 0

    yl = int(state.get("yardline_100", 60))
    dist = int(state.get("distance", 10))
    down = int(state.get("down", 1))

    for _ in range(req.n):
        y = max(-15, min(80, _toy_yards_for_action(action)))
        samples.append(y)
        # touchdown if cross goal line
        if yl - max(0, y) <= 0:
            tds += 1
        # turnover if fail on 4th down
        gained = y >= dist
        if not gained and down == 4:
            tos += 1

    samples.sort()
    n = len(samples)
    def pct(p):  # percentile helper
        i = max(0, min(n - 1, int(p * (n - 1))))
        return float(samples[i])

    return {
        "yards_mean": float(sum(samples) / n),
        "yards_p10": pct(0.10),
        "yards_p50": pct(0.50),
        "yards_p90": pct(0.90),
        "td_rate": tds / n,
        "fg_rate": 0.0,
        "turnover_rate": tos / n,
    }