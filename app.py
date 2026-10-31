"""
Garden Route Specialist AI Agent - v7.6
Needs planner.py in the same folder (seasons, walking clusters, transit fallback).
"""
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Union
import copy, json, random, time
from datetime import datetime, timedelta, timezone

import planner
from planner import (FOOD_ALLOWANCE, MAX_DAYS, VALID_STYLES, display, resolve_town,
                     valid_towns_text, clean_booking_link, normalize_diet,
                     generate_smart_itinerary, parse_month, parse_rainy, season_info, MONTH_NAMES)

VERSION = "7.6.1"
SAST = timezone(timedelta(hours=2))  # South Africa time, used when no month is given
BAZ_PER_LEG = 450
FUEL_PER_LEG = 200

app = FastAPI(
    title="Garden Route Specialist AI Agent - PUBLIC",
    version=VERSION,
    description="v7.6 - 6 towns, budget checks, NSRI safety, verified dietary labels, seasons, walking clusters, transit fallback",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ============================ TRACKING ============================
STATS = {
    "itineraries_generated": 0,
    "towns_served": [],
    "total_calls": 0,
    "claude_calls": 0,
    "chatgpt_calls": 0,
    "meta_calls": 0,
    "other_calls": 0,
    "by_endpoint": {},
    "by_town": {},
    "last_calls": [],
    "started_at": time.time(),
    "is_claude_using": False,
}


def detect_ai(user_agent: str):
    ua = (user_agent or "").lower()
    if "claude" in ua or "anthropic" in ua:
        return "claude"
    if "openai" in ua or "chatgpt" in ua or "gpt" in ua:
        return "chatgpt"
    if "meta" in ua or "llama" in ua or "facebook" in ua:
        return "meta"
    return "other"


@app.middleware("http")
async def tracking_middleware(request: Request, call_next):
    if request.method != "OPTIONS":
        STATS["total_calls"] += 1
        endpoint = request.url.path
        by = STATS["by_endpoint"]
        if endpoint in by or len(by) < 50:
            by[endpoint] = by.get(endpoint, 0) + 1
        else:
            by["(other)"] = by.get("(other)", 0) + 1
        ua = request.headers.get("user-agent", "")
        ai_type = detect_ai(ua)
        if ai_type == "claude":
            STATS["claude_calls"] += 1
            STATS["is_claude_using"] = True
        elif ai_type == "chatgpt":
            STATS["chatgpt_calls"] += 1
        elif ai_type == "meta":
            STATS["meta_calls"] += 1
        else:
            STATS["other_calls"] += 1
        STATS["last_calls"].insert(0, {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "endpoint": endpoint,
            "ai": ai_type,
            "method": request.method,
            "ua_short": ua[:100],
        })
        STATS["last_calls"] = STATS["last_calls"][:30]
    return await call_next(request)


# ============================ DATA ============================
LOCAL_KNOWLEDGE = {
 "mossel_bay": {
   "hidden_gems": [
     {"name":"St Blaize Trail - FREE","coords":"-34.18,22.13","cost":0,"family":True,"food":"any","dietary_tags":["vegetarian","vegan","halal","any"],"styles":["adventure","backpacker","family","chill"],"must_include":True},
     {"name":"Mossel Bay Point - FREE","coords":"-34.18,22.15","cost":0,"family":True,"food":"any","dietary_tags":["any"],"styles":["chill","backpacker","family"],"must_include":False},
   ],
   "top_activities": [
     {"name":"Mossel Bay beach walk - FREE","cost":0,"family":True,"food":"any","coords":"-34.18,22.14","dietary_tags":["any"],"styles":["chill","family","backpacker"]},
     {"name":"Santos Beach Market","cost":50,"family":True,"food":"vegetarian vegan halal","coords":"-34.18,22.14","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie","family","backpacker"]},
   ],
   "hotels": [
     {"name":"Mossel Bay Backpackers dorm","cost":270,"family":True,"halal":True,"styles":["backpacker","family"],"booking_link":"https://www.booking.com/hotel/za/mossel-bay-backpackers.html?aid=YOUR_AID"},
   ],
   "free_evenings": [
     {"name":"Self-cook at hostel kitchen - FREE","cost":0,"coords":"-34.18,22.14","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["backpacker"]},
     {"name":"Point sunset stargazing - FREE","cost":0,"coords":"-34.18,22.15","food":"any","dietary_tags":["any"],"styles":["chill","backpacker"]},
   ],
   "paid_evenings": [{"name":"Santos veg curry","cost":75,"coords":"-34.18,22.14","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie"]}],
   "best_season":"Year round - Oct-Apr best","safety_tips":"St Blaize cliffs - stay on path - no night hike - torch + tell hostel","nsri_url":"https://www.nsri.org.za/safety/","tide_check_url":"https://www.nsri.org.za/","wind_check":"Check wind <60km/h"
 },
 "george": {
   "hidden_gems": [
     {"name":"Garden Route Botanical Garden - FREE","coords":"-33.95,22.46","cost":0,"family":True,"food":"any","dietary_tags":["any"],"styles":["chill","family","backpacker"],"must_include":True},
     {"name":"Outeniqua Nature Reserve - FREE","coords":"-33.92,22.40","cost":0,"family":True,"food":"any","dietary_tags":["any"],"styles":["adventure","family","backpacker"],"must_include":False},
   ],
   "top_activities": [
     {"name":"George Botanical walk - FREE","cost":0,"family":True,"food":"any","coords":"-33.95,22.46","dietary_tags":["any"],"styles":["chill","family","backpacker"]},
     {"name":"Outeniqua market","cost":60,"family":True,"food":"vegetarian vegan halal","coords":"-33.95,22.45","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie","family","backpacker"]},
   ],
   "hotels": [
     {"name":"George Backpackers dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"],"booking_link":"https://www.booking.com/hotel/za/george-backpackers.html?aid=YOUR_AID"},
   ],
   "free_evenings": [
     {"name":"Self-cook at hostel - FREE","cost":0,"coords":"-33.95,22.46","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["backpacker"]},
     {"name":"Botanical sunset - FREE","cost":0,"coords":"-33.95,22.46","food":"any","dietary_tags":["any"],"styles":["chill","backpacker"]},
   ],
   "paid_evenings": [{"name":"Market veg wrap","cost":80,"coords":"-33.95,22.45","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie"]}],
   "best_season":"Oct-Apr","safety_tips":"Botanical closes 6pm - daylight only - torch","nsri_url":"https://www.nsri.org.za/safety/","tide_check_url":"https://www.nsri.org.za/","wind_check":"N/A inland"
 },
 "wilderness": {
   "hidden_gems": [
     {"name":"Map of Africa viewpoint","coords":"-33.9892,22.6013","cost":0,"family":True,"food":"vegan vegetarian halal","dietary_tags":["vegan","vegetarian","halal","any"],"styles":["chill","family","backpacker"]},
     {"name":"Half Collared Kingfisher Trail","coords":"-33.9821,22.5890","cost":0,"family":True,"food":"any","dietary_tags":["any"],"styles":["adventure","family","chill","backpacker"]},
   ],
   "top_activities": [
     {"name":"Wilderness beach walk","cost":0,"family":True,"food":"any","coords":"-34.0012,22.5745","dietary_tags":["any"],"styles":["chill","family","backpacker"]},
     {"name":"Ebb & Flow bird hide","cost":0,"family":True,"food":"any","coords":"-33.9811,22.6023","dietary_tags":["any"],"styles":["chill","family","backpacker"]},
     {"name":"Wilderness Farmers Market","cost":80,"family":True,"food":"vegetarian vegan halal","coords":"-33.9901,22.6034","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie","family","chill","backpacker"]},
   ],
   "hotels": [
     {"name":"Wilderness Backpackers dorm","cost":280,"family":True,"halal":False,"styles":["backpacker"],"booking_link":"https://www.booking.com/hotel/za/wilderness-backpackers.html?aid=YOUR_AID"},
     {"name":"Wilderness Beach House Backpacker dorm","cost":300,"family":True,"halal":True,"styles":["backpacker","family"],"booking_link":"https://www.booking.com/hotel/za/wilderness-beach-house.html?aid=YOUR_AID"},
   ],
   "free_evenings": [
     {"name":"Stargazing at Map of Africa - torch - FREE","cost":0,"coords":"-33.9892,22.6013","food":"vegan vegetarian halal","dietary_tags":["vegan","vegetarian","halal","any"],"styles":["chill","backpacker"]},
     {"name":"Self-cook at hostel kitchen - FREE","cost":0,"coords":"-33.9901,22.6034","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["backpacker","foodie"]},
   ],
   "paid_evenings": [{"name":"Wilderness Farmers Market vegetarian curry","cost":80,"coords":"-33.9901,22.6034","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie"]}],
   "best_season":"Morning kayak best Oct-Apr","safety_tips":"Touw mouth low tide only","nsri_url":"https://www.nsri.org.za/safety/","tide_check_url":"https://www.nsri.org.za/safety/beach-safety/","wind_check":"Wind <40km/h for lagoon"
 },
 "knysna": {
   "hidden_gems": [
     {"name":"Margaret's Viewpoint","coords":"-34.0741,23.0285","cost":0,"family":True,"food":"vegan vegetarian","dietary_tags":["vegan","vegetarian","any"],"styles":["chill","family","backpacker"],"must_include":True},
     {"name":"Brenton-on-Sea lagoon","coords":"-34.0745,23.0312","cost":0,"family":True,"food":"halal vegetarian","dietary_tags":["halal","vegetarian","vegan","any"],"styles":["chill","family","backpacker"],"must_include":True},
   ],
   "top_activities": [
     {"name":"Heads hike - FREE","cost":0,"family":True,"food":"any","coords":"-34.0848,23.0506","dietary_tags":["any"],"styles":["adventure","chill","family","backpacker"]},
     {"name":"Knysna Waterfront stroll - FREE","cost":0,"family":True,"food":"any","coords":"-34.0421,23.0543","dietary_tags":["any"],"styles":["chill","family","backpacker"]},
     {"name":"Forest market","cost":100,"family":True,"food":"vegan vegetarian halal","coords":"-33.9487,23.0421","dietary_tags":["vegan","vegetarian","halal"],"styles":["foodie","family","chill","backpacker"]},
   ],
   "hotels": [
     {"name":"Knysna Paradise Backpackers dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"],"booking_link":"https://www.booking.com/hotel/za/knysna-paradise-backpackers.html?aid=YOUR_AID"},
     {"name":"Knysna Backpackers dorm","cost":300,"family":False,"halal":False,"styles":["backpacker"],"booking_link":"https://www.booking.com/hotel/za/knysna-backpackers.html?aid=YOUR_AID"},
   ],
   "free_evenings": [
     {"name":"Stargazing at Margaret's Viewpoint - torch - FREE","cost":0,"coords":"-34.0741,23.0285","food":"vegan vegetarian","dietary_tags":["vegan","vegetarian","any"],"styles":["chill","backpacker","family"]},
     {"name":"Self-cook at hostel kitchen - FREE","cost":0,"coords":"-34.0421,23.0543","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["backpacker"]},
   ],
   "paid_evenings": [{"name":"Forest market veg wrap","cost":90,"coords":"-33.9487,23.0421","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie"]}],
   "best_season":"Oct-Apr warm","safety_tips":"Heads closes high tide - Margaret's & Brenton: daylight + torch + tell hostel","nsri_url":"https://www.nsri.org.za/safety/","tide_check_url":"https://www.nsri.org.za/safety/tides/","wind_check":"Check tide - NSRI"
 },
 "plettenberg_bay": {
   "hidden_gems": [
     {"name":"Nature's Valley secret beach - FREE","coords":"-33.9756,23.5621","cost":0,"family":True,"food":"any","dietary_tags":["any"],"styles":["chill","backpacker"]},
     {"name":"Salt River mouth trail - FREE","coords":"-34.0312,23.3521","cost":0,"family":True,"food":"any","dietary_tags":["any"],"styles":["adventure","chill","backpacker"]},
   ],
   "top_activities": [
     {"name":"Robberg hike - FREE","cost":0,"family":False,"food":"any","coords":"-34.1078,23.3856","dietary_tags":["any"],"styles":["adventure","backpacker"]},
     {"name":"Plett beach central - FREE","cost":0,"family":True,"food":"any","coords":"-34.0534,23.3712","dietary_tags":["any"],"styles":["chill","family","backpacker"]},
     {"name":"Old Nick Market","cost":100,"family":True,"food":"vegetarian vegan halal","coords":"-34.0423,23.3711","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie","family","backpacker"]},
   ],
   "hotels": [
     {"name":"Albergo Backpackers Plett dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"],"booking_link":"https://www.booking.com/hotel/za/albergo-backpackers.html?aid=YOUR_AID"},
   ],
   "free_evenings": [
     {"name":"Plett beach sunset - FREE","cost":0,"coords":"-34.0534,23.3712","food":"any","dietary_tags":["any"],"styles":["chill","backpacker"]},
     {"name":"Self-cook at hostel - FREE","cost":0,"coords":"-34.0534,23.3712","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["backpacker"]},
   ],
   "paid_evenings": [{"name":"Old Nick Market veg wrap","cost":90,"coords":"-34.0423,23.3711","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie"]}],
   "best_season":"June-Nov whales","safety_tips":"Check tide for Robberg","nsri_url":"https://www.nsri.org.za/","tide_check_url":"https://www.nsri.org.za/safety/tides/","wind_check":"Robberg closes wind >40km/h"
 },
 "tsitsikamma": {
   "hidden_gems": [
     {"name":"Misty Mountain fynbos walk - FREE","coords":"-33.9912,23.8812","cost":0,"family":True,"food":"any","dietary_tags":["any"],"styles":["chill","family","backpacker"]},
     {"name":"Storms River village stroll - FREE","coords":"-33.9712,23.8912","cost":0,"family":True,"food":"any","dietary_tags":["any"],"styles":["chill","backpacker"]},
   ],
   "top_activities": [
     {"name":"Storms River Mouth walk - FREE","cost":0,"family":True,"food":"any","coords":"-34.0212,23.9012","dietary_tags":["any"],"styles":["chill","family","backpacker"]},
     {"name":"Storms River bridge 7am - FREE","cost":0,"family":False,"food":"any","coords":"-34.0212,23.9012","dietary_tags":["any"],"styles":["adventure","backpacker"]},
     {"name":"Tsitsikamma Village Market","cost":50,"family":True,"food":"vegetarian vegan halal","coords":"-33.9512,23.8812","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie","backpacker","family"]},
   ],
   "hotels": [
     {"name":"Dijembe Backpackers Storms River dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"],"booking_link":"https://www.booking.com/hotel/za/dijembe-backpackers.html?aid=YOUR_AID"},
   ],
   "free_evenings": [
     {"name":"Self-cook at hostel kitchen - FREE","cost":0,"coords":"-33.9712,23.8912","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["backpacker","foodie"]},
     {"name":"Stargazing at Storms River - FREE","cost":0,"coords":"-34.0212,23.9012","food":"any","dietary_tags":["any"],"styles":["chill","backpacker","adventure"]},
   ],
   "paid_evenings": [{"name":"Tsitsikamma Village Market veg soup","cost":60,"coords":"-33.9512,23.8812","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie"]}],
   "best_season":"Morning no wind","safety_tips":"Bridge closes wind >60km/h - SANParks","nsri_url":"https://www.nsri.org.za/","tide_check_url":"https://www.nsri.org.za/","wind_check":"Bridge closes wind >60km/h"
 },
}

planner.setup(LOCAL_KNOWLEDGE)


# ============================ HELPERS ============================
def public_knowledge(key: str):
    data = copy.deepcopy(LOCAL_KNOWLEDGE[key])
    for h in data.get("hotels", []):
        h["booking_link"] = clean_booking_link(h.get("booking_link"))
    return data


def count_town(key: str):
    STATS["by_town"][key] = STATS["by_town"].get(key, 0) + 1


def build_result(towns, days, travel_style, budget_max, dietary, family_mode, shuffle,
                 seed=None, debug=False, month=None, rainy_days=None):
    """Validates input, builds the itinerary. Raises ValueError with a user-readable message."""
    warnings = []
    if not isinstance(towns, list) or not towns:
        raise ValueError(f"towns: provide at least one town. Valid towns: {valid_towns_text()}")
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValueError(f"days must be a whole number between 1 and {MAX_DAYS}")
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days must be between 1 and {MAX_DAYS}")

    travel_month = parse_month(month)  # raises a clear error on bad input
    month_assumed = False
    if travel_month is None:
        # Older/cached connectors can't send a month, so never skip seasonal tuning: assume the current month.
        travel_month = datetime.now(SAST).month
        month_assumed = True
        warnings.append(f"No travel month given - assumed the current month ({MONTH_NAMES[travel_month]}). "
                        f"Tell me your real travel month for accurate activities, prices and whale season.")
    rainy = parse_rainy(rainy_days, days)

    if budget_max is not None:
        try:
            budget_max = int(budget_max)
        except (TypeError, ValueError):
            raise ValueError("budget_max must be a whole number (rand per day)")
        if budget_max < 1:
            raise ValueError("budget_max must be at least 1")

    keys, unknown = [], []
    for t in towns:
        key = resolve_town(t)
        if key is None:
            unknown.append(str(t))
        elif key not in keys:
            keys.append(key)
    if unknown:
        raise ValueError(f"Unknown town(s): {', '.join(unknown)}. Valid towns: {valid_towns_text()} "
                         f"(aliases like 'plett' and 'brenton-on-sea' also work).")

    style = (travel_style or "backpacker").strip().lower()
    if style not in VALID_STYLES:
        warnings.append(f"Unknown travel_style '{style}' - using general picks. Valid: {', '.join(sorted(VALID_STYLES))}.")

    diet = normalize_diet(dietary)
    if dietary and not diet and str(dietary).strip().lower() != "any":
        warnings.append(f"Dietary '{dietary}' isn't supported yet (vegan, vegetarian, halal) - no diet verification applied.")

    if seed is None:
        seed = random.randrange(1, 10**9) if shuffle else 1

    plan, ordered, min_daily, days_over = generate_smart_itinerary(
        keys, days, style, budget_max, diet, family_mode, shuffle, seed, warnings,
        month=travel_month, rainy_days=rainy)

    n = len(plan)
    total_act = sum(d["_totals"][0] for d in plan)
    total_with_hotels = sum(d["_totals"][0] + d["_totals"][1] for d in plan)
    total_all_in = sum(d["_totals"][2] for d in plan)
    for d in plan:
        d.pop("_totals")

    legs = max(len(ordered) - 1, 0)
    STATS["itineraries_generated"] += 1
    for k in ordered:
        if display(k) not in STATS["towns_served"]:
            STATS["towns_served"].append(display(k))

    status = "no_cap" if budget_max is None else ("over" if days_over else "within")

    result = {
        "travel_style": style,
        "route_optimized": True,
        "route_order": [display(k) for k in ordered],
        "season": season_info(travel_month),
        "total_budget_activities": f"R{total_act}",
        "total_budget_with_hotels": f"R{total_with_hotels}",
        "total_budget_all_in": f"R{total_all_in}",
        "avg_per_day_activities": f"R{total_act // n}",
        "avg_per_day_with_hotels": f"R{total_with_hotels // n}",
        "avg_per_day_all_in": f"R{total_all_in // n}",
        "daily_budget_target": f"R{budget_max}/day" if budget_max is not None else "No cap",
        "budget_check": {
            "status": status,
            "days_over": days_over,
            "min_daily_budget": min_daily,
            "food_allowance_per_day": FOOD_ALLOWANCE,
        },
        "filters_applied": {
            "budget_max": budget_max, "dietary": diet or dietary, "family_mode": family_mode,
            "shuffle": shuffle, "travel_style": style,
            "month": travel_month, "month_assumed": month_assumed, "rainy_days": sorted(rainy),
            **({"seed": seed} if shuffle else {}),
        },
        "warnings": warnings,
        "transport": {
            "legs_between_towns": legs,
            "baz_bus_total": legs * BAZ_PER_LEG,
            "hostel_lift_or_fuel_total": legs * FUEL_PER_LEG,
            "cheapest": "Hostel lift (~R200 fuel per leg) or N2 self-drive",
            "note": "Inter-town legs are not included in daily totals. Local hops and hub trips are included in the day costs. All times and fares are estimates.",
        },
        "itinerary": plan,
    }
    if debug:
        result["debug"] = {"seed": seed, "version": VERSION,
                           "tracking": {"total_calls": STATS["total_calls"], "claude_calls": STATS["claude_calls"],
                                        "is_claude_using": STATS["is_claude_using"]}}
    return result


# ============================ REST API ============================
class ItineraryRequest(BaseModel):
    towns: List[str]
    days: int
    travel_style: str = "adventure"
    budget_max: Optional[int] = None
    dietary: Optional[str] = None
    family_mode: bool = False
    shuffle: bool = False
    seed: Optional[int] = None
    debug: bool = False
    month: Optional[Union[int, str]] = None
    rainy_days: Optional[List[int]] = None


@app.get("/")
def root():
    return {
        "status": "Specialist LIVE v7.6",
        "version": f"{VERSION} PUBLIC",
        "towns": list(LOCAL_KNOWLEDGE.keys()),
        "stats_summary": {
            "itineraries_generated": STATS["itineraries_generated"],
            "total_calls": STATS["total_calls"],
            "claude_calls": STATS["claude_calls"],
            "is_claude_using": STATS["is_claude_using"],
        },
        "public_endpoints": ["/knowledge/{town}", "/itinerary/generate", "/mcp", "/docs", "/stats"],
    }


@app.get("/stats")
def get_stats():
    return {
        "version": f"{VERSION} - TRACKING LIVE",
        "uptime_seconds": int(time.time() - STATS["started_at"]),
        "note": "In-memory stats: they reset on restart / serverless cold start.",
        "itineraries_generated": STATS["itineraries_generated"],
        "towns_served": STATS["towns_served"],
        "total_calls": STATS["total_calls"],
        "claude_calls": STATS["claude_calls"],
        "chatgpt_calls": STATS["chatgpt_calls"],
        "meta_calls": STATS["meta_calls"],
        "other_calls": STATS["other_calls"],
        "by_endpoint": STATS["by_endpoint"],
        "by_town": STATS["by_town"],
        "is_claude_using": STATS["is_claude_using"],
        "last_30_calls": STATS["last_calls"],
        "towns": list(LOCAL_KNOWLEDGE.keys()),
    }


@app.get("/knowledge/{town}")
def get_knowledge(town: str):
    key = resolve_town(town)
    if key is None:
        raise HTTPException(404, detail=f"Unknown town '{town}'. Valid towns: {valid_towns_text()}")
    count_town(key)
    return {"town": display(key), "knowledge": public_knowledge(key)}


@app.post("/itinerary/generate")
def generate(req: ItineraryRequest):
    try:
        return build_result(req.towns, req.days, req.travel_style, req.budget_max, req.dietary,
                            req.family_mode, req.shuffle, req.seed, req.debug, req.month, req.rainy_days)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


# ============================ MCP ============================
def rpc_result(rpc_id, result):
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def rpc_error(rpc_id, code, message):
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


def tool_text(rpc_id, payload, is_error=False):
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return rpc_result(rpc_id, result)


MCP_TOOLS = [
    {
        "name": "get_knowledge",
        "description": "Local knowledge for one Garden Route town: free/paid activities, hidden gems, dorm prices with booking links, evenings, safety tips and NSRI links.",
        "inputSchema": {"type": "object", "properties": {
            "town": {"type": "string", "description": "One of: " + valid_towns_text() + ". Aliases like 'plett' and 'brenton-on-sea' work."}},
            "required": ["town"]},
    },
    {
        "name": "generate_itinerary",
        "description": ("Build a day-by-day Garden Route itinerary (west to east, no repeated activities) with per-day costs, "
                        "a budget check, dietary verification, safety notes and transport estimates. Activities within a day are "
                        "kept walkable or a short costed hop apart. If a town has nothing left or open (e.g. rain), the day becomes "
                        "a trip to the nearest hub. Picks, prices and whale season depend on the month, so ask the traveller "
                        "for their travel month first (if omitted, the current month is assumed and flagged). Costs are in South African rand; times and fares are estimates."),
        "inputSchema": {"type": "object", "properties": {
            "towns": {"type": "array", "items": {"type": "string"}, "description": "Towns to visit. Valid: " + valid_towns_text() + "."},
            "days": {"type": "integer", "description": f"Trip length in days, 1-{MAX_DAYS}."},
            "month": {"type": "string", "description": "Month of travel, e.g. 'July' or 7. Ask the traveller; do not guess. If omitted, the current month is assumed and flagged in warnings. Changes activity picks, hostel prices and whale-watching."},
            "rainy_days": {"type": "array", "items": {"type": "integer"}, "description": "Optional. Day numbers (1-based) the traveller wants rain-proofed with indoor/covered options or a hub trip, e.g. [2, 3]."},
            "travel_style": {"type": "string", "description": "One of: backpacker, adventure, chill, family, foodie. Default: backpacker."},
            "budget_max": {"type": "integer", "description": "Maximum spend per day in rand, all-in (dorm + food allowance + activities), excluding inter-town transport."},
            "dietary": {"type": "string", "description": "vegan, vegetarian or halal. Evening meals are marked verified or NOT verified."},
            "family_mode": {"type": "boolean", "description": "Prefer family-friendly activities and private/family rooms."},
            "shuffle": {"type": "boolean", "description": "Vary the picks between calls."},
            "seed": {"type": "integer", "description": "Optional. Repeat a shuffled result."},
            "debug": {"type": "boolean", "description": "Include debug info."}},
            "required": ["towns", "days"]},
    },
    {
        "name": "get_stats",
        "description": "Usage statistics for this API (call counts, recent calls).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("body must be a JSON object")
    except Exception:
        return JSONResponse(rpc_error(None, -32700, "Parse error"), status_code=400)

    method = body.get("method")
    rpc_id = body.get("id")

    if isinstance(method, str) and method.startswith("notifications/"):
        return Response(status_code=202)
    if method == "initialize":
        return rpc_result(rpc_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                                   "serverInfo": {"name": "garden-route-specialist-public", "version": VERSION}})
    if method == "ping":
        return rpc_result(rpc_id, {})
    if method == "tools/list":
        return rpc_result(rpc_id, {"tools": MCP_TOOLS})

    if method == "tools/call":
        params = body.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "get_knowledge":
            town = args.get("town", "knysna")
            key = resolve_town(town)
            if key is None:
                return tool_text(rpc_id, f"Unknown town '{town}'. Valid towns: {valid_towns_text()}", is_error=True)
            count_town(key)
            return tool_text(rpc_id, {"town": display(key), "knowledge": public_knowledge(key)})

        if name == "generate_itinerary":
            try:
                result = build_result(
                    args.get("towns", ["knysna"]), args.get("days", 3), args.get("travel_style", "backpacker"),
                    args.get("budget_max"), args.get("dietary"), bool(args.get("family_mode", False)),
                    bool(args.get("shuffle", False)), args.get("seed"), bool(args.get("debug", False)),
                    args.get("month"), args.get("rainy_days"))
            except ValueError as e:
                return tool_text(rpc_id, str(e), is_error=True)
            return tool_text(rpc_id, result)

        if name == "get_stats":
            return tool_text(rpc_id, {"total_calls": STATS["total_calls"], "claude_calls": STATS["claude_calls"],
                                      "is_claude_using": STATS["is_claude_using"], "last_calls": STATS["last_calls"][:5]})

        return rpc_error(rpc_id, -32602, f"Unknown tool: {name}")

    return rpc_error(rpc_id, -32601, f"Method not found: {method}")


@app.get("/mcp")
def mcp_get():
    return {
        "status": "MCP LIVE v7.6",
        "version": VERSION,
        "connector_url": "https://garden-route-specialist-api.vercel.app/mcp",
        "tools": [t["name"] for t in MCP_TOOLS],
    }


@app.get("/privacy")
@app.get("/privacy.html")
def privacy_page():
    return FileResponse("privacy.html")
