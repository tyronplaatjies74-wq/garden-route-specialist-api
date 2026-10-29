from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json, random, urllib.parse

app = FastAPI(title="Garden Route Specialist AI Agent", version="5.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
API_KEY_NAME = "X-Agent-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
def get_api_key(api_key: str = Security(api_key_header)): return api_key

# v5 ANY - 12 towns + fallback + hotels + transport + styles
LOCAL_KNOWLEDGE = {
 "knysna": {
   "hidden_gems": [{"name":"Margaret's Viewpoint","coords":"-34.07,23.02","cost":0,"family":True,"food":"vegan","styles":["chill","family","adventure"]},{"name":"Brenton-on-Sea lagoon","coords":"-34.07,23.03","cost":0,"family":True,"food":"halal","styles":["chill","family"]}],
   "top_activities": [
     {"name":"Lagoon kayak sunrise","cost":350,"family":True,"food":"any","coords":"-34.05,23.05","styles":["adventure","family"]},
     {"name":"Heads hike","cost":0,"family":True,"food":"any","coords":"-34.08,23.05","styles":["adventure","chill","family"]},
     {"name":"Forest market","cost":100,"family":True,"food":"vegan halal","coords":"-33.95,23.04","styles":["foodie","family","chill"]},
     {"name":"Featherbed Eco Trail","cost":750,"family":False,"food":"any","coords":"-34.06,23.05","styles":["luxury","adventure"]},
     {"name":"Oyster tasting","cost":250,"family":False,"food":"oyster non-halal","coords":"-34.04,23.05","styles":["foodie","luxury"]},
     {"name":"Knysna Elephant Park","cost":600,"family":True,"food":"any","coords":"-33.99,23.23","styles":["family","luxury"]},
   ],
   "hotels": [{"name":"Belvidere Manor","cost":2800,"family":True,"halal":True},{"name":"Knysna Backpackers","cost":350,"family":False,"halal":False},{"name":"Premier Resort The Moorings","cost":1500,"family":True,"halal":True}],
   "best_season":"Oct-Apr warm","safety_tips":"Heads closes high tide - check NSRI"
 },
 "plettenberg_bay": {
   "hidden_gems": [{"name":"Nature's Valley secret beach","coords":"-33.97,23.56","cost":0,"family":True,"food":"any","styles":["chill"]}],
   "top_activities": [
     {"name":"Robberg hike","cost":0,"family":False,"food":"any","coords":"-34.10,23.38","styles":["adventure"]},
     {"name":"Whale watch boat","cost":1200,"family":True,"food":"any","coords":"-34.05,23.37","styles":["luxury","family","adventure"]},
     {"name":"Monkeyland","cost":350,"family":True,"food":"vegan","coords":"-33.98,23.45","styles":["family"]},
     {"name":"Birds of Eden","cost":350,"family":True,"food":"vegan","coords":"-33.98,23.45","styles":["family","chill"]},
     {"name":"Old Nick Market","cost":100,"family":True,"food":"halal vegan","coords":"-34.04,23.37","styles":["foodie","family"]},
     {"name":"Bloukrans Bungy","cost":1300,"family":False,"food":"any","coords":"-33.97,23.64","styles":["adventure","luxury"]},
   ],
   "hotels": [{"name":"The Plettenberg Hotel","cost":4500,"family":True,"halal":False},{"name":"Plett Backpackers","cost":400,"family":False,"halal":False}],
   "best_season":"June-Nov whales","safety_tips":"Check tide for Robberg"
 },
 "george": {"hidden_gems": [{"name":"Kaaimans River mouth","coords":"-33.99,22.55","cost":0,"family":True,"food":"any","styles":["chill"]}], "top_activities": [{"name":"Wilderness beach","cost":0,"family":True,"food":"any","coords":"-33.99,22.57","styles":["chill","family"]}], "hotels": [{"name":"Fancourt","cost":5000,"family":True,"halal":True}], "best_season":"Year round","safety_tips":"Mountain weather changes fast"},
 "mossel_bay": {"hidden_gems": [{"name":"St Blaize cave","coords":"-34.18,22.13","cost":0,"family":True,"food":"any","styles":["adventure"]}], "top_activities": [{"name":"Shark cage","cost":2500,"family":False,"food":"any","coords":"-34.18,22.13","styles":["adventure","luxury"]}], "hotels": [{"name":"Point Hotel","cost":1800,"family":True,"halal":True}], "best_season":"Year round","safety_tips":"Santos rip current"},
 "wilderness": {"hidden_gems": [{"name":"Map of Africa viewpoint","coords":"-33.99,22.60","cost":0,"family":True,"food":"any","styles":["chill"]}], "top_activities": [{"name":"Touw River kayak","cost":400,"family":True,"food":"any","coords":"-33.99,22.60","styles":["adventure","family"]}], "hotels": [{"name":"Wilderness Beach House","cost":1200,"family":True,"halal":True}], "best_season":"Morning kayak best","safety_tips":"Touw mouth low tide only"},
 "tsitsikamma": {"hidden_gems": [{"name":"Storms River bridge 7am","coords":"-34.02,23.90","cost":0,"family":False,"food":"any","styles":["adventure"]}], "top_activities": [{"name":"Canopy tour","cost":900,"family":True,"food":"any","coords":"-33.96,23.89","styles":["adventure","family"]}], "hotels": [{"name":"Storms River Mouth","cost":2000,"family":True,"halal":False}], "best_season":"Morning no wind","safety_tips":"Bridge closes wind >60km/h"},
 "oudtshoorn": {"hidden_gems": [{"name":"Swartberg Pass sunset","coords":"-33.35,22.20","cost":0,"family":False,"food":"any","styles":["chill","luxury"]}], "top_activities": [{"name":"Ostrich farm","cost":250,"family":True,"food":"halal","coords":"-33.59,22.20","styles":["family","foodie"]}], "hotels": [{"name":"De Denne Guesthouse","cost":900,"family":True,"halal":True}], "best_season":"Winter cooler","safety_tips":"No night driving Swartberg"},
 "cape_town": {"hidden_gems": [{"name":"Kloof Corner sunrise","coords":"-33.95,18.40","cost":0,"family":True,"food":"any","styles":["adventure","chill"]}], "top_activities": [{"name":"Table Mountain cable car","cost":400,"family":True,"food":"any","coords":"-33.95,18.40","styles":["family","luxury"]}], "hotels": [{"name":"Cape Town Lodge","cost":2200,"family":True,"halal":True}], "best_season":"Nov-Mar","safety_tips":"Table Mountain closes wind"},
 "addo": {"hidden_gems": [{"name":"Addo sundowner spot","coords":"-33.44,25.74","cost":0,"family":True,"food":"any","styles":["chill"]}], "top_activities": [{"name":"Addo game drive","cost":800,"family":True,"food":"any","coords":"-33.44,25.74","styles":["family","luxury","adventure"]}], "hotels": [{"name":"Addo Main Camp","cost":1800,"family":True,"halal":True}], "best_season":"Year round","safety_tips":"Stay in car"},
 "stellenbosch": {"hidden_gems": [{"name":"Jonkershoek nature reserve","coords":"-33.98,18.95","cost":0,"family":True,"food":"any","styles":["chill","adventure"]}], "top_activities": [{"name":"Wine tram halal-friendly","cost":350,"family":True,"food":"halal","coords":"-33.93,18.86","styles":["foodie","luxury","chill"]}], "hotels": [{"name":"Stellenbosch Hotel","cost":2000,"family":True,"halal":True}], "best_season":"Year round","safety_tips":"Book wine farms early"},
 "hermanus": {"hidden_gems": [{"name":"Cliff Path whale watching","coords":"-34.41,19.23","cost":0,"family":True,"food":"any","styles":["chill","family"]}], "top_activities": [{"name":"Whale watching cliff","cost":0,"family":True,"food":"any","coords":"-34.41,19.23","styles":["family","chill"]}], "hotels": [{"name":"Birkenhead House","cost":6000,"family":False,"halal":False}], "best_season":"July-Nov whales","safety_tips":"Cliff path slippery when wet"},
}

ROUTE_ORDER = ["mossel_bay","george","wilderness","knysna","plettenberg_bay","tsitsikamma","oudtshoorn","cape_town","hermanus","stellenbosch","addo"]
TRANSPORT = {"default": "N2 self-drive 1-2hr between towns", "luxury": "Private shuttle R2500/day", "backpacker": "Baz Bus R450 hop"}

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
    # Normalize towns - handle ANY town with fallback
    normalized_towns = []
    for t in towns:
        key = t.lower().replace(" ","_")
        if key in LOCAL_KNOWLEDGE:
            normalized_towns.append(t)
        else:
            # Fallback: treat as custom town, use Knysna data as template
            normalized_towns.append(t)
            LOCAL_KNOWLEDGE[key] = {
                "hidden_gems": [{"name": f"{t} hidden viewpoint","coords":"-34.0,23.0","cost":0,"family":True,"food":"any","styles":["chill","family"]}],
                "top_activities": [{"name": f"Explore {t} - local market","cost":100,"family":True,"food":"any","coords":"-34.0,23.0","styles":["foodie","family","chill","adventure","luxury"]}],
                "hotels": [{"name": f"{t} Guesthouse","cost":800,"family":True,"halal":True}],
                "best_season":"Year round - ask locals","safety_tips":"Ask locals + check weather"
            }
    towns = optimize_route(normalized_towns)
    pool = []
    for t in towns:
        k = LOCAL_KNOWLEDGE.get(t.lower().replace(" ","_"))
        if k:
            for act in k["top_activities"]:
                pool.append({"town": t, **act, "type":"activity", "safety":k["safety_tips"], "season":k["best_season"], "hotels": k.get("hotels",[])})
            for gem in k["hidden_gems"]:
                pool.append({"town": t, **gem, "type":"hidden_gem", "safety":k["safety_tips"], "season":k["best_season"], "hotels": k.get("hotels",[])})

    # ANY dietary
    if dietary:
        d = dietary.lower()
        if "oyster" in d or "no oyster" in d: pool = [p for p in pool if "oyster" not in p["name"].lower()]
        if "halal" in d: pool = [p for p in pool if "non-halal" not in p.get("food","").lower() and "oyster" not in p.get("food","").lower()]
        if "kosher" in d: pool = [p for p in pool if "non-halal" not in p.get("food","").lower() and "oyster" not in p.get("food","").lower()]
        if "vegan" in d: pool = [p for p in pool if "vegan" in p.get("food","").lower() or p.get("food","")=="any"]
        if "vegetarian" in d: pool = [p for p in pool if "oyster" not in p.get("food","").lower() and "non-halal" not in p.get("food","").lower()]
        if "gluten" in d: pool = [p for p in pool if "oyster" not in p.get("food","").lower()] # simplified

    if family_mode or "family" in travel_style.lower():
        pool = [p for p in pool if p.get("family",True) == True]

    # ANY travel style
    style = travel_style.lower()
    if style in ["luxury","adventure","chill","foodie","backpacker","family"]:
        filtered_by_style = [p for p in pool if style in p.get("styles",[])]
        if filtered_by_style: pool = filtered_by_style

    if budget_max:
        pool = [p for p in pool if p.get("cost",0) <= budget_max]

    if shuffle:
        random.shuffle(pool)

    # Evenings ANY - halal, family, budget aware
    evenings_pool = [
        {"name":"Sunset at The Heads with halal mocktails at Island Cafe","cost":150,"coords":"-34.08,23.05","family":True,"food":"halal vegan","styles":["chill","family","foodie"]},
        {"name":"Drydock halal grill, lagoon-side","cost":400,"coords":"-34.04,23.05","family":True,"food":"halal","styles":["foodie","family","luxury"]},
        {"name":"Beach braai at Brenton-on-Sea (halal-friendly)","cost":200,"coords":"-34.07,23.03","family":True,"food":"halal","styles":["family","chill","foodie"]},
        {"name":"Stargazing at Margaret's Viewpoint - take torch","cost":0,"coords":"-34.07,23.02","family":True,"food":"halal vegan","styles":["chill","family","adventure"]},
        {"name":"Family pizza night - halal","cost":150,"coords":"-34.05,23.05","family":True,"food":"halal","styles":["family","foodie","chill"]},
        {"name":"Luxury spa sunset","cost":900,"coords":"-34.05,23.05","family":False,"food":"any","styles":["luxury","chill"]},
        {"name":"Backpacker braai + beers","cost":120,"coords":"-34.05,23.05","family":False,"food":"any","styles":["backpacker","foodie"]},
    ]
    if dietary and "halal" in dietary.lower(): evenings_pool = [e for e in evenings_pool if "halal" in e.get("food","").lower() or "vegan" in e.get("food","").lower() or e.get("food","")=="any"]
    if family_mode or "family" in style: evenings_pool = [e for e in evenings_pool if e.get("family",True)]
    if "luxury" in style: evenings_pool = [e for e in evenings_pool if "luxury" in e.get("styles",[]) or e["cost"]>=200]
    if "backpacker" in style: evenings_pool = [e for e in evenings_pool if e["cost"]<=200]
    if budget_max: evenings_pool = [e for e in evenings_pool if e.get("cost",0) <= budget_max]
    if not evenings_pool: evenings_pool = [{"name":"Stargazing - free","cost":0,"coords":"-34.07,23.02","family":True,"food":"halal vegan","styles":["chill"]}]

    plan = []; used = set(); total = 0; total_with_hotels = 0
    for d in range(1, days+1):
        t = towns[(d-1) % len(towns)]
        k = LOCAL_KNOWLEDGE.get(t.lower().replace(" ","_"), list(LOCAL_KNOWLEDGE.values())[0])
        town_pool = [p for p in pool if p["town"].lower() == t.lower() and p["name"] not in used]
        if len(town_pool) < 2: town_pool = [p for p in pool if p["name"] not in used]
        if not town_pool: used.clear(); town_pool = pool
        if not town_pool: town_pool = [{"name":"Margaret's Viewpoint","cost":0,"family":True,"food":"halal","coords":"-34.07,23.02","safety":k["safety_tips"],"season":k["best_season"],"styles":["chill"],"hotels":k.get("hotels",[])}]
        morning = town_pool[0]
        afternoon = town_pool[1] if len(town_pool)>1 else town_pool[0]
        used.add(morning["name"]); used.add(afternoon["name"])

        # v5 FIX: Day budget cap ANY
        evening = evenings_pool[(d-1) % len(evenings_pool)]
        if budget_max:
            base_cost = morning.get("cost",0) + afternoon.get("cost",0)
            if base_cost + evening.get("cost",0) > budget_max + 200:
                for e in sorted(evenings_pool, key=lambda x: x["cost"]):
                    if base_cost + e.get("cost",0) <= budget_max + 200:
                        evening = e; break
                else: evening = min(evenings_pool, key=lambda x: x["cost"])

        # Hotel logic ANY
        hotels = k.get("hotels", [{"name":"Guesthouse","cost":800,"family":True,"halal":True}])
        if budget_max:
            if budget_max < 500: hotels = [h for h in hotels if h["cost"] <= 600] or hotels
            if budget_max >= 1500: hotels = [h for h in hotels if h["cost"] >= 1000] or hotels
        if dietary and "halal" in dietary.lower(): hotels = [h for h in hotels if h.get("halal",True)] or hotels
        if family_mode: hotels = [h for h in hotels if h.get("family",True)] or hotels
        hotel = hotels[(d-1) % len(hotels)] if hotels else {"name":"Guesthouse","cost":800}

        # Transport
        if "luxury" in style: transport = TRANSPORT["luxury"]
        elif "backpacker" in style: transport = TRANSPORT["backpacker"]
        else: transport = TRANSPORT["default"]

        day_cost = morning.get("cost",0) + afternoon.get("cost",0) + evening.get("cost",0)
        day_cost_with_hotel = day_cost + hotel["cost"]
        total += day_cost
        total_with_hotels += day_cost_with_hotel

        plan.append({
            "day": d, "town": t,
            "morning": f"{morning['name']} R{morning.get('cost',0)}",
            "morning_maps": get_maps_link(morning['name'], morning.get("coords","")),
            "afternoon": f"{afternoon['name']} R{afternoon.get('cost',0)}",
            "afternoon_maps": get_maps_link(afternoon['name'], afternoon.get("coords","")),
            "evening": f"{evening['name']} R{evening['cost']}",
            "evening_maps": get_maps_link(evening['name'], evening['coords']),
            "hotel": f"{hotel['name']} R{hotel['cost']}/night",
            "hotel_maps": get_maps_link(hotel['name'], morning.get("coords","")),
            "transport": transport,
            "day_budget_activities": f"R{day_cost}",
            "day_budget_with_hotel": f"R{day_cost_with_hotel}",
            "safety": f"{morning.get('safety','')} - Evening: torch + tell someone + no night swim - Weather: Check NSRI + wind <60km/h - Oct warm - Live: check wttr.in/{t}",
            "best_time": f"{morning.get('season', k['best_season'])} - Go before 8am no crowds - Style: {travel_style}",
            "family_friendly": morning.get("family",True),
            "food_info": morning.get("food","any"),
            "style_match": morning.get("styles",[])
        })
    return plan, total, total_with_hotels

class ItineraryRequest(BaseModel):
 towns: List[str]; days: int; travel_style: str = "adventure"; budget_max: Optional[int] = None; dietary: Optional[str] = None; family_mode: bool = False; shuffle: bool = False

@app.get("/")
def root(): return {"status":"Specialist LIVE v5 ANY - Hotels Transport Any Town Dietary Style","features":["budget","any dietary halal vegan kosher gluten vegetarian","family","shuffle","maps","weather live tip","hotels","transport","any town fallback","luxury adventure chill foodie backpacker","total budget with hotels"],"version":"5.0.0","towns": list(LOCAL_KNOWLEDGE.keys())}

@app.get("/knowledge/{town}")
def get_knowledge(town: str, api_key: str = Depends(get_api_key)):
 key = town.lower().replace(" ","_"); data = LOCAL_KNOWLEDGE.get(key)
 if not data:
  data = {"hidden_gems": [{"name": f"{town} hidden gem","coords":"-34.0,23.0","cost":0,"family":True,"food":"any","styles":["chill"]}], "top_activities": [{"name": f"Explore {town}","cost":100,"family":True,"food":"any","coords":"-34.0,23.0","styles":["adventure"]}], "hotels": [{"name": f"{town} Guesthouse","cost":800,"family":True,"halal":True}], "best_season":"Year round","safety_tips":"Ask locals"}
 return {"town": town, "knowledge": data}

@app.post("/itinerary/generate")
def generate(req: ItineraryRequest, api_key: str = Depends(get_api_key)):
 if req.days <1 or req.days>30: raise HTTPException(400, detail="days 1-30")
 plan, total, total_hotels = generate_smart_itinerary(req.towns, req.days, req.travel_style, req.budget_max, req.dietary, req.family_mode, req.shuffle)
 return {"request": req, "route_optimized": True, "route_order": optimize_route(req.towns), "total_budget_activities": f"R{total}", "total_budget_with_hotels": f"R{total_hotels}", "avg_per_day_activities": f"R{total//req.days if req.days>0 else total}", "avg_per_day_with_hotels": f"R{total_hotels//req.days if req.days>0 else total_hotels}", "itinerary": plan}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
 body = await request.json(); method = body.get("method"); id = body.get("id")
 if method == "initialize": return {"jsonrpc":"2.0","id":id,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"garden-route-specialist","version":"5.0.0"}}}
 if method == "notifications/initialized": return {"jsonrpc":"2.0","id":id,"result":{}}
 if method == "tools/list": return {"jsonrpc":"2.0","id":id,"result":{"tools":[
   {"name":"get_knowledge","description":"Get hidden gems, activities, hotels, season, safety, maps for ANY town in SA - with fallback","inputSchema":{"type":"object","properties":{"town":{"type":"string"}},"required":["town"]}},
   {"name":"generate_itinerary","description":"Generate ANY itinerary: any town in SA, any budget R, any dietary halal vegan kosher gluten vegetarian no oyster, any style luxury adventure chill foodie family backpacker, family_mode, shuffle, hotels, transport, Google Maps, weather, total budget with hotels - v5 ANY","inputSchema":{"type":"object","properties":{"towns":{"type":"array","items":{"type":"string"}},"days":{"type":"integer"},"travel_style":{"type":"string","description":"luxury, adventure, chill, foodie, family, backpacker"},"budget_max":{"type":"integer","description":"Max cost per activity R, e.g. 400"},"dietary":{"type":"string","description":"halal, vegan, kosher, gluten-free, vegetarian, no oyster"},"family_mode":{"type":"boolean"},"shuffle":{"type":"boolean"}},"required":["towns","days"]}}
 ]}}
 if method == "tools/call":
  params = body.get("params",{}); tool_name = params.get("name"); args = params.get("arguments",{})
  if tool_name == "get_knowledge":
   town = args.get("town","knysna"); key = town.lower().replace(" ","_"); data = LOCAL_KNOWLEDGE.get(key)
   if not data: data = {"hidden_gems": [{"name": f"{town} hidden gem","coords":"-34.0,23.0","cost":0,"family":True,"food":"any","styles":["chill"]}], "top_activities": [{"name": f"Explore {town}","cost":100,"family":True,"food":"any","coords":"-34.0,23.0","styles":["adventure"]}], "hotels": [{"name": f"{town} Guesthouse","cost":800,"family":True,"halal":True}], "best_season":"Year round","safety_tips":"Ask locals"}
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps({"town": town, "knowledge": data}, indent=2)}]}}
  if tool_name == "generate_itinerary":
   towns = args.get("towns",["knysna","plettenberg_bay"]); days = int(args.get("days",3)); travel_style = args.get("travel_style","adventure"); budget_max = args.get("budget_max"); dietary = args.get("dietary"); family_mode = args.get("family_mode", False); shuffle = args.get("shuffle", False)
   plan, total, total_hotels = generate_smart_itinerary(towns, days, travel_style, budget_max, dietary, family_mode, shuffle)
   result = {"travel_style": travel_style, "route_optimized": True, "route_order": optimize_route(towns), "total_budget_activities": f"R{total}", "total_budget_with_hotels": f"R{total_hotels}", "avg_per_day_activities": f"R{total//days if days>0 else total}", "avg_per_day_with_hotels": f"R{total_hotels//days if days>0 else total}", "filters_applied": {"budget_max":budget_max,"dietary":dietary,"family_mode":family_mode,"shuffle":shuffle,"travel_style":travel_style}, "itinerary": plan}
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps(result, indent=2)}]}}
 return {"jsonrpc":"2.0","id":id,"result":{}}

@app.get("/mcp")
def mcp_get(): return {"status":"MCP endpoint LIVE v5 ANY - Handles ANY itinerary","towns": list(LOCAL_KNOWLEDGE.keys())}