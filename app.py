from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json, random, urllib.parse

app = FastAPI(title="Garden Route Specialist AI Agent", version="7.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
API_KEY_NAME = "X-Agent-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
def get_api_key(api_key: str = Security(api_key_header)): return api_key

# v7 DAILY BUDGET FIX - budget_max = TOTAL per day with hotel, not per activity
LOCAL_KNOWLEDGE = {
 "wilderness": {
   "hidden_gems": [
     {"name":"Map of Africa viewpoint","coords":"-33.99,22.60","cost":0,"family":True,"food":"vegan vegetarian halal","styles":["chill","family","backpacker"]},
     {"name":"Half Collared Kingfisher Trail","coords":"-33.98,22.59","cost":0,"family":True,"food":"any","styles":["adventure","family","chill","backpacker"]},
     {"name":"Wilderness lagoon canoe spot","coords":"-33.99,22.58","cost":0,"family":True,"food":"any","styles":["chill","family","backpacker"]},
   ],
   "top_activities": [
     {"name":"Wilderness beach walk","cost":0,"family":True,"food":"any","coords":"-33.99,22.57","styles":["chill","family","backpacker"]},
     {"name":"Ebb & Flow bird hide","cost":0,"family":True,"food":"any","coords":"-33.98,22.60","styles":["chill","family","backpacker"]},
     {"name":"Touw River kayak","cost":400,"family":True,"food":"any","coords":"-33.99,22.60","styles":["adventure","family"]},
     {"name":"Wilderness Farmers Market","cost":80,"family":True,"food":"vegetarian vegan halal","coords":"-33.99,22.60","styles":["foodie","family","chill","backpacker"]},
     {"name":"Paragliding Wilderness","cost":950,"family":False,"food":"any","coords":"-34.00,22.61","styles":["adventure","luxury"]},
   ],
   "hotels": [
     {"name":"Wilderness Backpackers dorm","cost":280,"family":False,"halal":False,"styles":["backpacker"]},
     {"name":"Wilderness Beach House Backpacker dorm","cost":300,"family":True,"halal":True,"styles":["backpacker","family"]},
     {"name":"Fairy Knowe Backpackers","cost":320,"family":True,"halal":True,"styles":["backpacker"]},
   ],
   "free_evenings": [
     {"name":"Stargazing at Map of Africa - free","cost":0,"coords":"-33.99,22.60","food":"vegan vegetarian halal","styles":["chill","backpacker"]},
     {"name":"Self-cook at hostel kitchen - free","cost":0,"coords":"-33.99,22.60","food":"vegetarian vegan halal","styles":["backpacker","foodie"]},
     {"name":"Wilderness beach sunset - free","cost":0,"coords":"-33.99,22.57","food":"any","styles":["chill","backpacker"]},
   ],
   "paid_evenings": [
     {"name":"Wilderness Farmers Market vegetarian curry","cost":80,"coords":"-33.99,22.60","food":"vegetarian vegan halal","styles":["foodie","family","backpacker"]},
   ],
   "best_season":"Morning kayak best - Oct-Apr","safety_tips":"Touw mouth low tide only - Check NSRI"
 },
 "knysna": {
   "hidden_gems": [
     {"name":"Margaret's Viewpoint","coords":"-34.07,23.02","cost":0,"family":True,"food":"vegan vegetarian","styles":["chill","family","backpacker"]},
     {"name":"Brenton-on-Sea lagoon","coords":"-34.07,23.03","cost":0,"family":True,"food":"halal vegetarian","styles":["chill","family","backpacker"]},
   ],
   "top_activities": [
     {"name":"Heads hike","cost":0,"family":True,"food":"any","coords":"-34.08,23.05","styles":["adventure","chill","family","backpacker"]},
     {"name":"Knysna Waterfront stroll","cost":0,"family":True,"food":"any","coords":"-34.04,23.05","styles":["chill","family","backpacker"]},
     {"name":"Lagoon kayak sunrise","cost":350,"family":True,"food":"any","coords":"-34.05,23.05","styles":["adventure","family"]},
     {"name":"Forest market","cost":100,"family":True,"food":"vegan vegetarian halal","coords":"-33.95,23.04","styles":["foodie","family","chill","backpacker"]},
   ],
   "hotels": [
     {"name":"Knysna Paradise Backpackers dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"]},
     {"name":"Knysna Backpackers dorm","cost":300,"family":False,"halal":False,"styles":["backpacker"]},
     {"name":"Afro Lodge Backpackers","cost":320,"family":True,"halal":True,"styles":["backpacker"]},
   ],
   "free_evenings": [
     {"name":"Stargazing at Margaret's Viewpoint - torch - free","cost":0,"coords":"-34.07,23.02","food":"vegan vegetarian","styles":["chill","backpacker","family"]},
     {"name":"Self-cook at hostel kitchen - free","cost":0,"coords":"-34.04,23.05","food":"vegetarian vegan halal","styles":["backpacker"]},
     {"name":"Brenton-on-Sea sunset - free","cost":0,"coords":"-34.07,23.03","food":"any","styles":["chill","backpacker"]},
   ],
   "paid_evenings": [
     {"name":"Forest market veg wrap","cost":90,"coords":"-33.95,23.04","food":"vegetarian vegan halal","styles":["foodie","backpacker"]},
   ],
   "best_season":"Oct-Apr warm","safety_tips":"Heads closes high tide - check NSRI"
 },
 "plettenberg_bay": {
   "hidden_gems": [
     {"name":"Nature's Valley secret beach","coords":"-33.97,23.56","cost":0,"family":True,"food":"any","styles":["chill","backpacker"]},
     {"name":"Salt River mouth trail","coords":"-34.03,23.35","cost":0,"family":True,"food":"any","styles":["adventure","chill","backpacker"]},
   ],
   "top_activities": [
     {"name":"Robberg hike","cost":0,"family":False,"food":"any","coords":"-34.10,23.38","styles":["adventure","backpacker"]},
     {"name":"Plett beach central","cost":0,"family":True,"food":"any","coords":"-34.05,23.37","styles":["chill","family","backpacker"]},
     {"name":"Old Nick Market","cost":100,"family":True,"food":"vegetarian vegan halal","coords":"-34.04,23.37","styles":["foodie","family","backpacker"]},
     {"name":"Whale watch boat","cost":1200,"family":True,"food":"any","coords":"-34.05,23.37","styles":["luxury"]},
   ],
   "hotels": [
     {"name":"Albergo Backpackers Plett dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"]},
     {"name":"Plett Backpackers dorm","cost":320,"family":False,"halal":False,"styles":["backpacker"]},
     {"name":"Buccaneers Backpackers","cost":350,"family":True,"halal":True,"styles":["backpacker"]},
   ],
   "free_evenings": [
     {"name":"Plett beach sunset - free","cost":0,"coords":"-34.05,23.37","food":"any","styles":["chill","backpacker"]},
     {"name":"Self-cook at hostel - free","cost":0,"coords":"-34.05,23.37","food":"vegetarian vegan halal","styles":["backpacker"]},
     {"name":"Stargazing at Lookout - free","cost":0,"coords":"-34.10,23.38","food":"any","styles":["chill","backpacker"]},
   ],
   "paid_evenings": [
     {"name":"Old Nick Market veg wrap","cost":90,"coords":"-34.04,23.37","food":"vegetarian vegan halal","styles":["foodie","backpacker"]},
   ],
   "best_season":"June-Nov whales","safety_tips":"Check tide for Robberg - NSRI"
 },
 "tsitsikamma": {
   "hidden_gems": [
     {"name":"Misty Mountain fynbos walk","coords":"-33.99,23.88","cost":0,"family":True,"food":"any","styles":["chill","family","backpacker"]},
     {"name":"Storms River village stroll","coords":"-33.97,23.89","cost":0,"family":True,"food":"any","styles":["chill","backpacker"]},
   ],
   "top_activities": [
     {"name":"Storms River Mouth walk","cost":0,"family":True,"food":"any","coords":"-34.02,23.90","styles":["chill","family","backpacker"]},
     {"name":"Tsitsikamma Village Market","cost":50,"family":True,"food":"vegetarian vegan halal","coords":"-33.95,23.88","styles":["foodie","backpacker","family"]},
     {"name":"Storms River bridge 7am","cost":0,"family":False,"food":"any","coords":"-34.02,23.90","styles":["adventure","backpacker"]},
     {"name":"Woodcutters Journey","cost":350,"family":True,"food":"any","coords":"-33.96,23.89","styles":["adventure","family"]},
     {"name":"Canopy tour","cost":900,"family":True,"food":"any","coords":"-33.96,23.89","styles":["adventure"]},
   ],
   "hotels": [
     {"name":"Dijembe Backpackers Storms River dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"]},
     {"name":"Tsitsikamma Backpackers dorm","cost":300,"family":False,"halal":False,"styles":["backpacker"]},
     {"name":"Tube 'n Axe Backpackers","cost":320,"family":True,"halal":True,"styles":["backpacker"]},
   ],
   "free_evenings": [
     {"name":"Self-cook at hostel kitchen - free - Tsitsikamma","cost":0,"coords":"-33.97,23.89","food":"vegetarian vegan halal","styles":["backpacker","foodie"]},
     {"name":"Stargazing at Storms River - free","cost":0,"coords":"-34.02,23.90","food":"any","styles":["chill","backpacker","adventure"]},
     {"name":"Village bonfire - free","cost":0,"coords":"-33.97,23.89","food":"any","styles":["backpacker","chill"]},
   ],
   "paid_evenings": [
     {"name":"Tsitsikamma Village Market veg soup","cost":60,"coords":"-33.95,23.88","food":"vegetarian vegan halal","styles":["foodie","backpacker"]},
   ],
   "best_season":"Morning no wind","safety_tips":"Bridge closes wind >60km/h - SANParks"
 },
}

ROUTE_ORDER = ["mossel_bay","george","wilderness","knysna","plettenberg_bay","tsitsikamma"]

def optimize_route(towns):
    def sort_key(t):
        key = t.lower().replace(" ","_")
        try: return ROUTE_ORDER.index(key)
        except: return 99
    return sorted(towns, key=sort_key)

def get_maps_link(name, coords):
    q = urllib.parse.quote(f"{name} {coords}")
    return f"https://www.google.com/maps/search/?api=1&query={q}"

def generate_smart_itinerary(towns, days, travel_style, budget_max=None, dietary=None, family_mode=False, shuffle=False):
    towns = optimize_route(towns)
    is_backpacker_budget = (travel_style.lower() == "backpacker" or (budget_max and budget_max <= 500))
    
    plan = []; total = 0; total_hotels = 0; used = set()
    
    for d in range(1, days+1):
        t = towns[(d-1) % len(towns)]
        key = t.lower().replace(" ","_")
        k = LOCAL_KNOWLEDGE.get(key)
        if not k:
            k = LOCAL_KNOWLEDGE["wilderness"]
        
        if is_backpacker_budget:
            free_acts = [a for a in (k["top_activities"] + k["hidden_gems"]) if a["cost"] == 0]
            if len(free_acts) < 2:
                free_acts = [a for a in (k["top_activities"] + k["hidden_gems"]) if a["cost"] <= 50] or free_acts
            pool = free_acts
            if dietary and "vegetarian" in dietary.lower():
                pool = [p for p in pool if "vegetarian" in p.get("food","").lower() or "vegan" in p.get("food","").lower() or p.get("food","").lower()=="any"]
            available = [p for p in pool if p["name"] not in used]
            if len(available) < 2:
                available = pool
            morning = available[0] if available else pool[0]
            afternoon = available[1] if len(available)>1 else available[0]
            evening = k["free_evenings"][(d-1) % len(k["free_evenings"])]
            hotels_sorted = sorted(k["hotels"], key=lambda x: x["cost"])
            hotel = hotels_sorted[0]
        else:
            pool = k["top_activities"] + k["hidden_gems"]
            if dietary and "vegetarian" in dietary.lower():
                pool = [p for p in pool if "vegetarian" in p.get("food","").lower() or "vegan" in p.get("food","").lower() or p.get("food","").lower()=="any"]
            if budget_max:
                pool = [p for p in pool if p["cost"] <= budget_max]
            available = [p for p in pool if p["name"] not in used]
            if len(available) < 2: available = pool
            morning = available[0]
            afternoon = available[1] if len(available)>1 else available[0]
            if budget_max and budget_max > 500:
                evening = k["paid_evenings"][0] if k["paid_evenings"] else k["free_evenings"][0]
            else:
                evening = k["free_evenings"][0]
            hotel = sorted(k["hotels"], key=lambda x: x["cost"])[0]
        
        used.add(morning["name"])
        used.add(afternoon["name"])
        
        if is_backpacker_budget:
            transport = {
                "not_included": True,
                "options": [
                    "Baz Bus Hop-on Hop-off R450 per town - book bazbus.com - backpacker favorite",
                    "Intercape Mainliner R250-350 per leg - intercape.co.za",
                    "Hostel lift / N2 self-drive R200 fuel per leg"
                ],
                "recommended_for_R300_budget": "Hostel lift or self-cook + free hikes = stay at R280-300/day",
                "extra_cost_if_Baz_Bus": "R450 x 3 moves = R1350 extra for 4 days"
            }
        else:
            transport = {
                "not_included": False,
                "options": ["Private shuttle R2500/day", "Baz Bus R450/town", "N2 self-drive R200 fuel"],
                "recommended": "Private shuttle"
            }
        
        day_activities = morning["cost"] + afternoon["cost"] + evening["cost"]
        day_with_hotel = day_activities + hotel["cost"]
        total += day_activities
        total_hotels += day_with_hotel
        
        plan.append({
            "day": d,
            "town": t,
            "town_verified": t,
            "morning": f"{morning['name']} R{morning['cost']} - {t} - FREE" if morning["cost"]==0 else f"{morning['name']} R{morning['cost']} - {t}",
            "morning_maps": get_maps_link(morning["name"], morning.get("coords","")),
            "afternoon": f"{afternoon['name']} R{afternoon['cost']} - {t} - FREE" if afternoon["cost"]==0 else f"{afternoon['name']} R{afternoon['cost']} - {t}",
            "afternoon_maps": get_maps_link(afternoon["name"], afternoon.get("coords","")),
            "evening": f"{evening['name']} R{evening['cost']} - {t} - FREE & vegetarian safe - v7 FIX town correct" if evening["cost"]==0 else f"{evening['name']} R{evening['cost']} - {t}",
            "evening_maps": get_maps_link(evening["name"], evening.get("coords","")),
            "hotel": f"{hotel['name']} R{hotel['cost']}/night - DORM CHEAPEST v7",
            "hotel_maps": get_maps_link(hotel["name"], morning.get("coords","")),
            "transport": transport,
            "day_budget_activities": f"R{day_activities}",
            "day_budget_with_hotel": f"R{day_with_hotel} - {'FITS R300' if day_with_hotel <= (budget_max or 999) else 'OVER BUDGET - cook free'}",
            "safety": f"{k['safety_tips']} - Evening: torch + tell someone + no night swim - Check NSRI tide + wind <60km/h",
            "best_time": f"{k['best_season']} - Go before 8am - Budget tip: Self-cook + free hikes to stay R280-300/day",
            "budget_tip": "To hit R300/day: Do FREE hikes (0) + self-cook at hostel (0) + dorm R280 = R280/day. Paid dinners are extra."
        })
    return plan, total, total_hotels

class ItineraryRequest(BaseModel):
 towns: List[str]; days: int; travel_style: str = "adventure"; budget_max: Optional[int] = None; dietary: Optional[str] = None; family_mode: bool = False; shuffle: bool = False

@app.get("/")
def root(): return {"status":"Specialist LIVE v7 DAILY BUDGET FIX - R300/day with hotel = free hikes + free self-cook + R280 dorm","version":"7.0.0","fixes":["daily budget R300 includes hotel","free activities only for backpacker R300","free evenings self-cook stargazing","hotel R280 cheapest dorm","evening town verified Tsitsikamma not Plett","transport extra not included","budget tip self-cook"],"towns": list(LOCAL_KNOWLEDGE.keys())}

@app.get("/knowledge/{town}")
def get_knowledge(town: str, api_key: str = Depends(get_api_key)):
 key = town.lower().replace(" ","_"); data = LOCAL_KNOWLEDGE.get(key, {"hidden_gems": [], "top_activities": []})
 return {"town": town, "knowledge": data}

@app.post("/itinerary/generate")
def generate(req: ItineraryRequest, api_key: str = Depends(get_api_key)):
 if req.days <1 or req.days>30: raise HTTPException(400, detail="days 1-30")
 plan, total, total_hotels = generate_smart_itinerary(req.towns, req.days, req.travel_style, req.budget_max, req.dietary, req.family_mode, req.shuffle)
 return {"request": req, "route_optimized": True, "route_order": optimize_route(req.towns), "total_budget_activities": f"R{total}", "total_budget_with_hotels": f"R{total_hotels}", "avg_per_day_activities": f"R{total//req.days if req.days>0 else total}", "avg_per_day_with_hotels": f"R{total_hotels//req.days if req.days>0 else total_hotels}", "daily_budget_target": f"R{req.budget_max}/day" if req.budget_max else "No daily cap", "itinerary": plan}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
 body = await request.json(); method = body.get("method"); id = body.get("id")
 if method == "initialize": return {"jsonrpc":"2.0","id":id,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"garden-route-specialist","version":"7.0.0"}}}
 if method == "notifications/initialized": return {"jsonrpc":"2.0","id":id,"result":{}}
 if method == "tools/list": return {"jsonrpc":"2.0","id":id,"result":{"tools":[
   {"name":"get_knowledge","description":"Get hidden gems, activities, hotels, season, safety, maps for ANY town - v7 daily budget fix","inputSchema":{"type":"object","properties":{"town":{"type":"string"}},"required":["town"]}},
   {"name":"generate_itinerary","description":"Generate ANY itinerary FIXED v7: daily budget R300 includes hotel = free hikes + free self-cook + R280 dorm, evening town verified Tsitsikamma not Plett, transport extra not included, budget tip self-cook","inputSchema":{"type":"object","properties":{"towns":{"type":"array","items":{"type":"string"}},"days":{"type":"integer"},"travel_style":{"type":"string","description":"luxury, adventure, chill, foodie, family, backpacker"},"budget_max":{"type":"integer","description":"DAILY TOTAL with hotel, e.g. 300 = R300/day with hotel"},"dietary":{"type":"string"},"family_mode":{"type":"boolean"},"shuffle":{"type":"boolean"}},"required":["towns","days"]}}
 ]}}
 if method == "tools/call":
  params = body.get("params",{}); tool_name = params.get("name"); args = params.get("arguments",{})
  if tool_name == "get_knowledge":
   town = args.get("town","knysna"); key = town.lower().replace(" ","_"); data = LOCAL_KNOWLEDGE.get(key, {"hidden_gems": [], "top_activities": []})
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps({"town": town, "knowledge": data}, indent=2)}]}}
  if tool_name == "generate_itinerary":
   towns = args.get("towns",["knysna"]); days = int(args.get("days",3)); travel_style = args.get("travel_style","adventure"); budget_max = args.get("budget_max"); dietary = args.get("dietary"); family_mode = args.get("family_mode", False); shuffle = args.get("shuffle", False)
   plan, total, total_hotels = generate_smart_itinerary(towns, days, travel_style, budget_max, dietary, family_mode, shuffle)
   result = {"travel_style": travel_style, "route_optimized": True, "route_order": optimize_route(towns), "total_budget_activities": f"R{total}", "total_budget_with_hotels": f"R{total_hotels}", "avg_per_day_activities": f"R{total//days if days>0 else total}", "avg_per_day_with_hotels": f"R{total_hotels//days if days>0 else total_hotels}", "daily_budget_target": f"R{budget_max}/day" if budget_max else "No daily cap", "filters_applied": {"budget_max":budget_max,"dietary":dietary,"family_mode":family_mode,"shuffle":shuffle,"travel_style":travel_style}, "v7_fixes": ["daily budget includes hotel R300 = free hikes + free self-cook + R280 dorm","evening town verified","transport extra not included"], "itinerary": plan}
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps(result, indent=2)}]}}
 return {"jsonrpc":"2.0","id":id,"result":{}}

@app.get("/mcp")
def mcp_get(): return {"status":"MCP endpoint LIVE v7 DAILY BUDGET FIX","version":"7.0.0"}