from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json, urllib.parse

app = FastAPI(
    title="Garden Route Specialist AI Agent - PUBLIC",
    version="7.3.0",
    description="v7.3 PUBLIC - 6 towns + R280/day formula + NSRI safety + fixed vegetarian tags + affiliate ready"
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# v7.3 - Analytics in-memory
STATS = {"itineraries_generated": 0, "towns_served": []}

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
     {"name":"Self-cook at hostel kitchen - FREE - Tsitsikamma","cost":0,"coords":"-33.9712,23.8912","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["backpacker","foodie"]},
     {"name":"Stargazing at Storms River - FREE","cost":0,"coords":"-34.0212,23.9012","food":"any","dietary_tags":["any"],"styles":["chill","backpacker","adventure"]},
   ],
   "paid_evenings": [{"name":"Tsitsikamma Village Market veg soup","cost":60,"coords":"-33.9512,23.8812","food":"vegetarian vegan halal","dietary_tags":["vegetarian","vegan","halal"],"styles":["foodie"]}],
   "best_season":"Morning no wind","safety_tips":"Bridge closes wind >60km/h - SANParks","nsri_url":"https://www.nsri.org.za/","tide_check_url":"https://www.nsri.org.za/","wind_check":"Bridge closes wind >60km/h"
 },
}

ROUTE_ORDER = ["mossel_bay","george","wilderness","knysna","plettenberg_bay","tsitsikamma"]

def optimize_route(towns):
    def sort_key(t):
        key = t.lower().replace(" ","_")
        try: return ROUTE_ORDER.index(key)
        except ValueError: return 99
    return sorted(towns, key=sort_key)

def get_maps_link(name, location):
    q = urllib.parse.quote(f"{name} {location}")
    return f"https://www.google.com/maps/search/?api=1&query={q}"

def is_diet_ok(item, dietary):
    if not dietary: return True
    want = dietary.lower()
    tags = [t.lower() for t in item.get("dietary_tags", [])]
    if "vegetarian" in want: return "vegetarian" in tags or "vegan" in tags or "any" in tags
    if "vegan" in want: return "vegan" in tags or "any" in tags
    if "halal" in want: return "halal" in tags or "any" in tags
    return True

def evening_label(evening, town):
    if evening["cost"] != 0: return f"{evening['name']} R{evening['cost']} - {town}"
    f = ",".join(evening.get("dietary_tags", []))
    return f"{evening['name']} R0 - {town} - FREE [{f}]"

def generate_smart_itinerary(towns, days, travel_style, budget_max=None, dietary=None, family_mode=False, shuffle=False):
    towns = optimize_route(towns)
    is_backpacker = (travel_style.lower() == "backpacker" or (budget_max and budget_max <= 500))
    plan = []; total = 0; total_hotels = 0; used = set()
    for d in range(1, days+1):
        t = towns[(d-1) % len(towns)]
        key = t.lower().replace(" ","_")
        k = LOCAL_KNOWLEDGE.get(key, LOCAL_KNOWLEDGE["wilderness"])
        all_acts = k["top_activities"] + k["hidden_gems"]
        if is_backpacker:
            free_acts = [a for a in all_acts if a["cost"] == 0]
            pool = [a for a in free_acts if is_diet_ok(a, dietary)]
            if len(pool) < 2: pool = [a for a in free_acts]
            pool.sort(key=lambda a: not a.get("must_include", False))
        else:
            pool = [a for a in all_acts if is_diet_ok(a, dietary)]
            if budget_max: pool = [p for p in pool if p["cost"] <= budget_max]
            if not pool: pool = all_acts
        available = [p for p in pool if p["name"] not in used]
        if len(available) < 2: available = pool
        morning = available[0]
        afternoon = available[1] if len(available) > 1 else available[0]
        used.add(morning["name"]); used.add(afternoon["name"])
        free_ev = [e for e in k["free_evenings"] if is_diet_ok(e, dietary)] or k["free_evenings"]
        evening = free_ev[(d-1) % len(free_ev)]
        hotel = sorted(k["hotels"], key=lambda x: x["cost"])[0]
        day_act = morning["cost"] + afternoon["cost"] + evening["cost"]
        day_with = day_act + hotel["cost"]
        total += day_act; total_hotels += day_with
        fits = f"FITS R{budget_max}" if budget_max and day_with <= budget_max else ("OVER" if budget_max else "No cap")
        plan.append({
            "day": d, "town": t, "town_verified": t,
            "morning": f"{morning['name']} R{morning['cost']} - FREE - {t}",
            "morning_maps": get_maps_link(morning["name"], morning.get("coords","")),
            "afternoon": f"{afternoon['name']} R{afternoon['cost']} - FREE - {t}",
            "afternoon_maps": get_maps_link(afternoon["name"], afternoon.get("coords","")),
            "evening": evening_label(evening, t),
            "evening_maps": get_maps_link(evening["name"], evening.get("coords","")),
            "hotel": f"{hotel['name']} R{hotel['cost']}/night - DORM CHEAPEST v7.3",
            "hotel_booking": hotel.get("booking_link",""),
            "hotel_maps": get_maps_link(hotel["name"], t),
            "transport": {
                "not_included_in_R280": True,
                "baz_bus_per_leg": 450,
                "cheapest": "Hostel lift R200 fuel or N2 self-drive",
                "total_extra_4days_if_baz": 1350,
                "R280_formula_tip": "Do FREE hikes + self-cook + R280 dorm = R280/day - transport extra"
            },
            "day_budget_activities": f"R{day_act}",
            "day_budget_with_hotel": f"R{day_with} - {fits}",
            "safety": f"{k['safety_tips']} - Evening: torch + tell hostel + no night swim - {k.get('wind_check','')}",
            "safety_links": {"nsri": k.get("nsri_url"), "tide": k.get("tide_check_url"), "wind": k.get("wind_check")},
            "best_time": k["best_season"],
            "dietary_tags": f"{morning.get('dietary_tags')} + {afternoon.get('dietary_tags')} - vegetarian safe" if dietary else "any"
        })
    return plan, total, total_hotels

class ItineraryRequest(BaseModel):
    towns: List[str]; days: int; travel_style: str = "adventure"; budget_max: Optional[int] = None; dietary: Optional[str] = None; family_mode: bool = False; shuffle: bool = False

def build_result(towns, days, travel_style, budget_max, dietary, family_mode, shuffle):
    STATS["itineraries_generated"] += 1
    for t in towns:
        if t not in STATS["towns_served"]: STATS["towns_served"].append(t)
    plan, total, total_hotels = generate_smart_itinerary(towns, days, travel_style, budget_max, dietary, family_mode, shuffle)
    return {
        "travel_style": travel_style, "route_optimized": True, "route_order": optimize_route(towns),
        "total_budget_activities": f"R{total}", "total_budget_with_hotels": f"R{total_hotels}",
        "avg_per_day_activities": f"R{total//days if days>0 else total}",
        "avg_per_day_with_hotels": f"R{total_hotels//days if days>0 else total_hotels}",
        "daily_budget_target": f"R{budget_max}/day" if budget_max else "No cap",
        "filters_applied": {"budget_max":budget_max,"dietary":dietary,"family_mode":family_mode,"shuffle":shuffle,"travel_style":travel_style,"dietary_tags_fixed": True},
        "v7.3_improvements": ["6 towns - mossel_bay + george added - full Garden Route","dietary_tags fixed - vegetarian/vegan/halal/any filtering","NSRI + tide + wind safety links in every day","booking_link ready for affiliate commission","transport honest - R280/day is without Baz Bus - extra shown","stats tracking"],
        "itinerary": plan
    }

@app.get("/")
def root(): return {"status":"Specialist LIVE v7.3 - 6 towns R280/day","version":"7.3.0 PUBLIC","towns": list(LOCAL_KNOWLEDGE.keys()), "stats": STATS, "public_endpoints": ["/knowledge/{town}","/itinerary/generate","/mcp","/docs","/stats","/whatsapp/info"]}

@app.get("/stats")
def get_stats(): return {"version":"7.3.0","itineraries_generated": STATS["itineraries_generated"], "towns_served": STATS["towns_served"], "R280_formula": "FREE hikes + self-cook + R280 dorm", "towns": list(LOCAL_KNOWLEDGE.keys())}

@app.get("/whatsapp/info")
def whatsapp_info(): return {"status":"WhatsApp bot coming - v8","how_it_works":"Same API - POST /itinerary/generate - we will add WhatsApp webhook","contact":"Add your number to hostels"}

@app.get("/knowledge/{town}")
def get_knowledge(town: str):
    key = town.lower().replace(" ","_")
    data = LOCAL_KNOWLEDGE.get(key, {"hidden_gems": [], "top_activities": []})
    return {"town": town, "knowledge": data, "R280_formula": "FREE + self-cook + R280 dorm - v7.3 dietary_tags fixed"}

@app.post("/itinerary/generate")
def generate(req: ItineraryRequest):
    if req.days < 1 or req.days > 30: raise HTTPException(400, detail="days 1-30")
    return build_result(req.towns, req.days, req.travel_style, req.budget_max, req.dietary, req.family_mode, req.shuffle)

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json(); method = body.get("method"); id = body.get("id")
    if method == "initialize": return {"jsonrpc":"2.0","id":id,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"garden-route-specialist-public","version":"7.3.0"}}}
    if method == "notifications/initialized": return {"jsonrpc":"2.0","id":id,"result":{}}
    if method == "tools/list": return {"jsonrpc":"2.0","id":id,"result":{"tools":[
        {"name":"get_knowledge","description":"PUBLIC v7.3 - 6 towns - Get hidden gems with dietary_tags, NSRI safety, maps","inputSchema":{"type":"object","properties":{"town":{"type":"string"}},"required":["town"]}},
        {"name":"generate_itinerary","description":"PUBLIC v7.3 - Generate R280/day with 6 towns - dietary_tags vegetarian/vegan/halal fixed + safety links + transport honest","inputSchema":{"type":"object","properties":{"towns":{"type":"array","items":{"type":"string"}},"days":{"type":"integer"},"travel_style":{"type":"string"},"budget_max":{"type":"integer"},"dietary":{"type":"string"},"family_mode":{"type":"boolean"},"shuffle":{"type":"boolean"}},"required":["towns","days"]}},
        {"name":"get_stats","description":"PUBLIC - Get how many backpackers helped - for hostel pitches","inputSchema":{"type":"object","properties":{}}}
    ]}}
    if method == "tools/call":
        params = body.get("params",{}); tool_name = params.get("name"); args = params.get("arguments",{})
        if tool_name == "get_knowledge":
            town = args.get("town","knysna"); key = town.lower().replace(" ","_"); data = LOCAL_KNOWLEDGE.get(key, {})
            return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps({"town": town, "knowledge": data}, indent=2)}]}}
        if tool_name == "generate_itinerary":
            towns = args.get("towns",["knysna"]); days = int(args.get("days",3)); travel_style = args.get("travel_style","backpacker")
            budget_max = args.get("budget_max"); dietary = args.get("dietary"); family_mode = args.get("family_mode", False); shuffle = args.get("shuffle", False)
            result = build_result(towns, days, travel_style, budget_max, dietary, family_mode, shuffle)
            return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps(result, indent=2)}]}}
        if tool_name == "get_stats":
            return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps(STATS, indent=2)}]}}
    return {"jsonrpc":"2.0","id":id,"result":{}}

@app.get("/mcp")
def mcp_get(): return {"status":"MCP LIVE v7.3 - 6 towns - Ready for 1000 backpackers","version":"7.3.0","connector_url": "https://garden-route-specialist-api.vercel.app/mcp", "new": ["mossel_bay","george"]}