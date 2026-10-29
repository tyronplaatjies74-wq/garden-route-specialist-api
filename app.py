"""
Garden Route Specialist AI Agent - v7.5 (fixed)

What changed vs v7.4
 1. Unknown towns now return a clear error (was: silently used Wilderness data)
 2. Town aliases: "plett", "brenton-on-sea", "storms river", "mossel bay" ...
 3. No zig-zag routes: towns sorted west->east, days allocated in blocks
 4. Activities never repeat; when a town runs out you get a "Free time" slot + warning
 5. Budget is honest: R100/day food allowance (env FOOD_ALLOWANCE) is added, over-budget
    plans are flagged with a warning + minimum workable budget
 6. Diet labels are real: verified / NOT verified (no more blanket "vegetarian safe").
    "any" no longer counts as vegetarian/vegan/halal for meals
 7. shuffle really shuffles (seedable); travel_style (foodie/family/adventure/chill/backpacker)
    and family_mode change the picks; halal prefers halal-friendly hostels
 8. Cost labels fixed ("R50", never "R50 - FREE")
 9. Self-cook map links point at the hostel; maps use coords when available
10. Booking links: "YOUR_AID" placeholder stripped; set env BOOKING_AID to add your affiliate id
11. Transport computed from real number of legs, returned once per trip (not repeated per day)
12. Dev/marketing fields removed from itinerary output (add "debug": true to see them)
13. MCP: clean tool descriptions, proper JSON-RPC errors, 202 for notifications,
    tool errors returned as isError instead of crashing
14. Stats: by_endpoint capped, by_town now also counts MCP get_knowledge calls

Env vars (all optional): FOOD_ALLOWANCE (default 100), BOOKING_AID
"""
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import copy, json, os, random, re, time, urllib.parse

VERSION = "7.5.0"

app = FastAPI(
    title="Garden Route Specialist AI Agent - PUBLIC",
    version=VERSION,
    description="v7.5 PUBLIC - 6 towns + budget checks + NSRI safety + verified dietary labels + affiliate ready + usage tracking",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ============================ CONFIG ============================
FOOD_ALLOWANCE = int(os.getenv("FOOD_ALLOWANCE", "100"))  # R/day groceries (assumption - tune it). 0 = old behaviour
BOOKING_AID = os.getenv("BOOKING_AID")                    # your booking.com affiliate id
BAZ_PER_LEG = 450
FUEL_PER_LEG = 200
MAX_DAYS = 30
VALID_STYLES = {"adventure", "backpacker", "family", "chill", "foodie"}
DIET_OK = {"vegan": {"vegan"}, "vegetarian": {"vegetarian", "vegan"}, "halal": {"halal"}}
REST_NAME = "Free time - rest or explore on your own"

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
        if endpoint in by or len(by) < 50:  # cap so random URLs can't grow memory forever
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

ROUTE_ORDER = ["mossel_bay", "george", "wilderness", "knysna", "plettenberg_bay", "tsitsikamma"]  # west -> east

TOWN_ALIASES = {
    "mossel": "mossel_bay",
    "plett": "plettenberg_bay",
    "plettenberg": "plettenberg_bay",
    "brenton": "knysna",
    "brenton_on_sea": "knysna",
    "storms_river": "tsitsikamma",
    "stormsriver": "tsitsikamma",
}


# ============================ HELPERS ============================
def display(key: str) -> str:
    return key.replace("_", " ")


def resolve_town(name: str):
    """'Plett', 'brenton-on-sea', 'Mossel Bay' -> internal key, or None if unknown."""
    key = re.sub(r"[\s\-]+", "_", str(name).strip().lower())
    key = TOWN_ALIASES.get(key, key)
    return key if key in LOCAL_KNOWLEDGE else None


def valid_towns_text() -> str:
    return ", ".join(display(k) for k in ROUTE_ORDER)


def optimize_route(keys):
    return sorted(keys, key=lambda k: ROUTE_ORDER.index(k) if k in ROUTE_ORDER else 99)


def allocate_days(n_towns: int, days: int):
    base, extra = divmod(days, n_towns)
    return [base + (1 if i < extra else 0) for i in range(n_towns)]


def fmt_cost(c) -> str:
    return f"R{c}" if c and c > 0 else "FREE"


def clean_name(name: str) -> str:
    name = re.sub(r"\s*-\s*FREE\b", "", name, flags=re.I)
    name = re.sub(r"\s*-\s*torch\b", " (bring a torch)", name, flags=re.I)
    return name.strip()


def is_self_cook(item) -> bool:
    return "self-cook" in item["name"].lower()


def maps_link(query: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(query, safe=",-.")


def clean_booking_link(url):
    """Strip the YOUR_AID placeholder; add the real affiliate id if BOOKING_AID is set."""
    if not url:
        return None
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "aid"]
    if BOOKING_AID:
        query.append(("aid", BOOKING_AID))
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def public_knowledge(key: str):
    data = copy.deepcopy(LOCAL_KNOWLEDGE[key])
    for h in data.get("hotels", []):
        h["booking_link"] = clean_booking_link(h.get("booking_link"))
    return data


def normalize_diet(d):
    if not d:
        return None
    d = str(d).strip().lower()
    for key in ("vegan", "vegetarian", "halal"):
        if key in d:
            return key
    return None


def diet_status(item, diet, is_meal):
    """verified = tagged for this diet. 'any' does NOT count as verified."""
    tags = {t.lower() for t in item.get("dietary_tags", [])}
    if DIET_OK[diet] & tags:
        return "verified"
    return "unverified" if is_meal else "no_meal"


def score(item, ctx, used, is_meal):
    s = 0.0
    if ctx["style"] in item.get("styles", []):
        s += 3
    if item.get("must_include") and not ctx["shuffle"]:
        s += 4
    if ctx["style"] == "foodie" and item.get("food", "any") != "any":
        s += 3
    if ctx["frugal"] and item.get("cost", 0) > 0:
        s -= 2
    if ctx["diet"] and is_meal and diet_status(item, ctx["diet"], True) == "verified":
        s += 6
    if item["name"] in used:
        s -= 2
    s += ctx["rng"].random() * (5 if ctx["shuffle"] else 0.01)
    return s


def pick(pool, used, remaining, ctx, is_meal=False, repeatable=lambda i: False):
    limit = max(remaining, 0)
    cands = [
        i for i in pool
        if (repeatable(i) or i["name"] not in used)
        and i.get("cost", 0) <= limit
        and (not ctx["family"] or i.get("family", True))
    ]
    if not cands:
        return None
    return max(cands, key=lambda i: score(i, ctx, used, is_meal))


def pick_hotel(hotels, ctx, budget, town, warn):
    pool = [h for h in hotels if ctx["style"] in h.get("styles", [])] or list(hotels)
    if ctx["family"]:
        pool = [h for h in pool if h.get("family")] or pool
        private = [h for h in pool if "dorm" not in h["name"].lower()]
        if private:
            pool = private
        else:
            warn(f"{town}: family mode - only dorm beds in the data. Confirm a private/family room with the hostel.")
    pool = sorted(pool, key=lambda h: h["cost"])
    fits = [h for h in pool if h["cost"] + FOOD_ALLOWANCE <= budget]
    chosen = None
    if ctx["diet"] == "halal":
        chosen = next((h for h in fits if h.get("halal")), None)
    if chosen is None and fits:
        chosen = fits[0]
    if chosen is None:
        chosen = pool[0]
    if ctx["diet"] == "halal" and not chosen.get("halal"):
        warn(f"{chosen['name']} isn't marked halal-friendly - confirm food options with the hostel.")
    return chosen


def make_slot(item, hotel, town, diet, is_meal):
    if item is None:
        return {"name": REST_NAME, "cost": 0, "maps": None, "diet": None, "text": REST_NAME}
    name = clean_name(item["name"])
    if is_self_cook(item):
        q = f"{hotel['name']} {town}"
    else:
        q = item.get("coords") or f"{name} {town}"
    return {
        "name": name,
        "cost": item.get("cost", 0),
        "maps": maps_link(q),
        "diet": diet_status(item, diet, is_meal) if diet else None,
        "text": f"{name} - {fmt_cost(item.get('cost', 0))}",
    }


# ============================ CORE ============================
def generate_smart_itinerary(keys, days, style, budget_max, diet, family_mode, shuffle, seed, warnings):
    def warn(msg):
        if msg not in warnings:
            warnings.append(msg)

    budget = float(budget_max) if budget_max is not None else float("inf")
    ctx = {
        "style": style,
        "diet": diet,
        "family": bool(family_mode) or style == "family",
        "shuffle": bool(shuffle),
        "frugal": style == "backpacker" or (budget_max is not None and budget_max <= 500),
        "rng": random.Random(seed),
    }

    towns = optimize_route(keys)
    if len(towns) > days:
        dropped = ", ".join(display(t) for t in towns[days:])
        warn(f"{len(towns)} towns but only {days} day(s): skipping {dropped}. Add days to include them.")
        towns = towns[:days]
    blocks = allocate_days(len(towns), days)

    used, plan, base_costs, unverified_days = set(), [], [], []
    day_no = 1
    for key, n_days in zip(towns, blocks):
        k = LOCAL_KNOWLEDGE[key]
        town = display(key)
        day_pool = k["hidden_gems"] + k["top_activities"]
        eve_pool = k["free_evenings"] + k["paid_evenings"]
        block_start, ran_out = day_no, False

        for _ in range(n_days):
            hotel = pick_hotel(k["hotels"], ctx, budget, town, warn)
            remaining = budget - hotel["cost"] - FOOD_ALLOWANCE

            chosen = []
            for _slot in range(2):  # morning, afternoon
                it = pick(day_pool, used, remaining, ctx)
                if it:
                    used.add(it["name"])
                    remaining -= it.get("cost", 0)
                else:
                    ran_out = True
                chosen.append(it)
            eve = pick(eve_pool, used, remaining, ctx, is_meal=True, repeatable=is_self_cook)
            if eve:
                used.add(eve["name"])

            morning = make_slot(chosen[0], hotel, town, diet, False)
            afternoon = make_slot(chosen[1], hotel, town, diet, False)
            evening = make_slot(eve, hotel, town, diet, True)

            act = morning["cost"] + afternoon["cost"] + evening["cost"]
            all_in = hotel["cost"] + FOOD_ALLOWANCE + act
            base_costs.append(hotel["cost"] + FOOD_ALLOWANCE)

            if budget_max is None:
                status = "No cap"
            elif all_in <= budget_max:
                status = f"FITS R{budget_max}"
            else:
                status = f"OVER R{budget_max} by R{all_in - budget_max}"

            if diet is None:
                diet_text = "any"
            elif eve is None:
                diet_text = f"no evening meal planned - self-cater {diet}"
            elif evening["diet"] == "verified":
                diet_text = f"evening meal verified {diet}"
            else:
                diet_text = f"evening NOT verified {diet} - self-cater or ask first"
                unverified_days.append(day_no)

            if day_no == block_start:
                safety = f"{k['safety_tips']} - Evening: torch + tell hostel + no night swim - {k.get('wind_check', '')}"
            else:
                safety = f"Same as Day {block_start} ({town})"

            plan.append({
                "day": day_no, "town": town, "town_verified": town,
                "morning": morning["text"], "morning_maps": morning["maps"],
                "afternoon": afternoon["text"], "afternoon_maps": afternoon["maps"],
                "evening": evening["text"], "evening_maps": evening["maps"],
                "hotel": f"{hotel['name']} R{hotel['cost']}/night",
                "hotel_booking": clean_booking_link(hotel.get("booking_link")),
                "hotel_maps": maps_link(f"{hotel['name']} {town}"),
                "day_budget_activities": f"R{act}",
                "day_budget_with_hotel": f"R{hotel['cost'] + act}",
                "day_food_estimate": f"R{FOOD_ALLOWANCE}",
                "day_budget_all_in": f"R{all_in} - {status}",
                "safety": safety,
                "safety_links": {"nsri": k.get("nsri_url"), "tide": k.get("tide_check_url"), "wind": k.get("wind_check")},
                "best_time": k["best_season"],
                "dietary_tags": diet_text,
                "dietary_check": {"morning": morning["diet"], "afternoon": afternoon["diet"], "evening": evening["diet"]} if diet else None,
                "_totals": (act, hotel["cost"], all_in),
            })
            day_no += 1

        if ran_out:
            warn(f"{town}: not enough unique activities for {n_days} day(s). Showing free time instead of repeating - "
                 f"consider fewer days here or add more activities to the data.")

    if diet and unverified_days:
        d = ", ".join(str(x) for x in unverified_days)
        warn(f"Day(s) {d}: evening isn't verified {diet}. Self-cater or check with the venue.")

    min_daily = max(base_costs)
    if budget_max is not None and min_daily > budget_max:
        warn(f"Budget R{budget_max}/day is below the cheapest workable plan (about R{min_daily}/day: "
             f"dorm + R{FOOD_ALLOWANCE} groceries). Raise the budget to R{min_daily}+, shorten the trip, or look for cheaper beds.")

    days_over = sum(1 for d in plan if budget_max is not None and d["_totals"][2] > budget_max)
    return plan, towns, min_daily, days_over


def build_result(towns, days, travel_style, budget_max, dietary, family_mode, shuffle, seed=None, debug=False):
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
        keys, days, style, budget_max, diet, family_mode, shuffle, seed, warnings)

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

    if budget_max is None:
        status = "no_cap"
    else:
        status = "over" if days_over else "within"

    result = {
        "travel_style": style,
        "route_optimized": True,
        "route_order": [display(k) for k in ordered],
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
            "shuffle": shuffle, "travel_style": style, **({"seed": seed} if shuffle else {}),
        },
        "warnings": warnings,
        "transport": {
            "legs_between_towns": legs,
            "baz_bus_total": legs * BAZ_PER_LEG,
            "hostel_lift_or_fuel_total": legs * FUEL_PER_LEG,
            "cheapest": "Hostel lift (~R200 fuel per leg) or N2 self-drive",
            "note": "Not included in daily totals. Add getting to the first town and home from the last.",
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


@app.get("/")
def root():
    return {
        "status": "Specialist LIVE v7.5 - 6 towns + budget checks + usage tracking",
        "version": f"{VERSION} PUBLIC",
        "towns": list(LOCAL_KNOWLEDGE.keys()),
        "stats_summary": {
            "itineraries_generated": STATS["itineraries_generated"],
            "total_calls": STATS["total_calls"],
            "claude_calls": STATS["claude_calls"],
            "is_claude_using": STATS["is_claude_using"],
        },
        "public_endpoints": ["/knowledge/{town}", "/itinerary/generate", "/mcp", "/docs", "/stats", "/whatsapp/info"],
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
        "R280_formula": "FREE hikes + self-cook + R280 dorm (+ food allowance, see budget_check)",
        "affiliate_status": "READY - waiting for EUR IBAN - v8.0 MONEY MAKER",
        "towns": list(LOCAL_KNOWLEDGE.keys()),
    }


@app.get("/whatsapp/info")
def whatsapp_info():
    return {"status": "WhatsApp bot coming - v8", "how_it_works": "Same API - POST /itinerary/generate", "contact": "Add your number to hostels"}


def count_town(key: str):
    STATS["by_town"][key] = STATS["by_town"].get(key, 0) + 1


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
                            req.family_mode, req.shuffle, req.seed, req.debug)
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


STYLE_HELP = "One of: backpacker, adventure, chill, family, foodie."

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
        "description": "Build a day-by-day Garden Route itinerary (west to east, no repeated activities) with per-day costs, a budget check with warnings, dietary verification, safety notes and transport estimates. Costs are in South African rand.",
        "inputSchema": {"type": "object", "properties": {
            "towns": {"type": "array", "items": {"type": "string"}, "description": "Towns to visit. Valid: " + valid_towns_text() + "."},
            "days": {"type": "integer", "description": f"Trip length in days, 1-{MAX_DAYS}."},
            "travel_style": {"type": "string", "description": STYLE_HELP + " Default: backpacker."},
            "budget_max": {"type": "integer", "description": "Maximum spend per day in rand, all-in (dorm + food allowance + activities), excluding transport."},
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
        return Response(status_code=202)  # notifications get no JSON body
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
                    bool(args.get("shuffle", False)), args.get("seed"), bool(args.get("debug", False)))
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
        "status": "MCP LIVE v7.5 - Ready for Claude + 1000 backpackers",
        "version": VERSION,
        "connector_url": "https://garden-route-specialist-api.vercel.app/mcp",
        "tracking": True,
        "tools": [t["name"] for t in MCP_TOOLS],
    }
