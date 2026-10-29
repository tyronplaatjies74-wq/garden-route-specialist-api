from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json, random, urllib.parse

app = FastAPI(title="Garden Route Specialist AI Agent", version="4.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
API_KEY_NAME = "X-Agent-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
def get_api_key(api_key: str = Security(api_key_header)): return api_key

LOCAL_KNOWLEDGE = {
 "knysna": {"hidden_gems": [{"name":"Margaret's Viewpoint","coords":"-34.07,23.02","cost":0,"family":True,"food":"vegan"},{"name":"Brenton-on-Sea lagoon","coords":"-34.07,23.03","cost":0,"family":True,"food":"halal"}],"top_activities": [{"name":"Lagoon kayak sunrise","cost":350,"family":True,"food":"any","coords":"-34.05,23.05"},{"name":"Heads hike","cost":0,"family":True,"food":"any","coords":"-34.08,23.05"},{"name":"Forest market","cost":100,"family":True,"food":"vegan halal","coords":"-33.95,23.04"},{"name":"Featherbed Eco Trail","cost":750,"family":False,"food":"any","coords":"-34.06,23.05"},{"name":"Oyster tasting","cost":250,"family":False,"food":"oyster non-halal","coords":"-34.04,23.05"}],"best_season":"Oct-Apr warm","safety_tips":"Heads closes high tide - check NSRI"},
 "plettenberg_bay": {"hidden_gems": [{"name":"Nature's Valley secret beach","coords":"-33.97,23.56","cost":0,"family":True,"food":"any"}], "top_activities": [{"name":"Robberg hike","cost":0,"family":False,"food":"any","coords":"-34.10,23.38"},{"name":"Whale watch boat","cost":1200,"family":True,"food":"any","coords":"-34.05,23.37"},{"name":"Monkeyland","cost":350,"family":True,"food":"vegan","coords":"-33.98,23.45"},{"name":"Birds of Eden","cost":350,"family":True,"food":"vegan","coords":"-33.98,23.45"},{"name":"Old Nick Market","cost":100,"family":True,"food":"halal vegan","coords":"-34.04,23.37"}],"best_season":"June-Nov whales","safety_tips":"Check tide for Robberg"},
 "george": {"hidden_gems": [{"name":"Kaaimans River mouth","coords":"-33.99,22.55","cost":0,"family":True,"food":"any"}], "top_activities": [{"name":"Wilderness beach","cost":0,"family":True,"food":"any","coords":"-33.99,22.57"}], "best_season":"Year round","safety_tips":"Mountain weather changes fast"},
 "mossel_bay": {"hidden_gems": [{"name":"St Blaize cave","coords":"-34.18,22.13","cost":0,"family":True,"food":"any"}], "top_activities": [{"name":"Shark cage","cost":2500,"family":False,"food":"any","coords":"-34.18,22.13"}], "best_season":"Year round","safety_tips":"Santos rip current"},
 "wilderness": {"hidden_gems": [{"name":"Map of Africa viewpoint","coords":"-33.99,22.60","cost":0,"family":True,"food":"any"}], "top_activities": [{"name":"Touw River kayak","cost":400,"family":True,"food":"any","coords":"-33.99,22.60"}], "best_season":"Morning kayak best","safety_tips":"Touw mouth low tide only"},
 "tsitsikamma": {"hidden_gems": [{"name":"Storms River bridge 7am","coords":"-34.02,23.90","cost":0,"family":False,"food":"any"}], "top_activities": [{"name":"Canopy tour","cost":900,"family":True,"food":"any","coords":"-33.96,23.89"}], "best_season":"Morning no wind","safety_tips":"Bridge closes wind >60km/h"},
 "oudtshoorn": {"hidden_gems": [{"name":"Swartberg Pass sunset","coords":"-33.35,22.20","cost":0,"family":False,"food":"any"}], "top_activities": [{"name":"Ostrich farm","cost":250,"family":True,"food":"halal","coords":"-33.59,22.20"}], "best_season":"Winter cooler","safety_tips":"No night driving Swartberg"}
}
ROUTE_ORDER = ["mossel_bay","george","wilderness","knysna","plettenberg_bay","tsitsikamma","oudtshoorn"]
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
    pool = []
    for t in towns:
        k = LOCAL_KNOWLEDGE.get(t.lower().replace(" ","_"))
        if k:
            for act in k["top_activities"]:
                pool.append({"town": t, **act, "type":"activity", "safety":k["safety_tips"], "season":k["best_season"]})
            for gem in k["hidden_gems"]:
                pool.append({"town": t, **gem, "type":"hidden_gem", "safety":k["safety_tips"], "season":k["best_season"]})
    
    # --- FIXED FILTERS v4.1 ---
    if dietary:
        d = dietary.lower()
        if "no oyster" in d or "halal" in d:
            pool = [p for p in pool if "oyster" not in p["name"].lower() and "oyster" not in p.get("food","").lower() and "non-halal" not in p.get("food","").lower()]
        if "halal" in d:
            pool = [p for p in pool if "non-halal" not in p.get("food","")]
        if "vegan" in d:
            pool = [p for p in pool if "vegan" in p.get("food","") or p.get("food")=="any" or "halal" in p.get("food","")]
    if family_mode:
        pool = [p for p in pool if p.get("family",True) == True]
    if budget_max:
        pool = [p for p in pool if p.get("cost",0) <= budget_max]
    if shuffle:
        random.shuffle(pool)

    # --- FIXED EVENINGS v4.1 - HALAL + FAMILY + BUDGET ---
    evenings_pool = [
        {"name":"Sunset at The Heads + mocktails at Island Cafe (halal)","cost":150,"coords":"-34.08,23.05","family":True,"food":"halal vegan"},
        {"name":"Lagoon-side dinner at Drydock - halal grill","cost":400,"coords":"-34.04,23.05","family":True,"food":"halal"},
        {"name":"Beach braai at Brenton-on-Sea (halal-friendly)","cost":200,"coords":"-34.07,23.03","family":True,"food":"halal"},
        {"name":"Stargazing at Margaret's Viewpoint - take torch","cost":0,"coords":"-34.07,23.02","family":True,"food":"halal vegan"},
        {"name":"Family pizza night - halal","cost":150,"coords":"-34.05,23.05","family":True,"food":"halal"}
    ]
    # Filter evenings same logic
    if dietary and "halal" in dietary.lower():
        evenings_pool = [e for e in evenings_pool if "halal" in e.get("food","").lower() or "vegan" in e.get("food","").lower()]
    if family_mode:
        evenings_pool = [e for e in evenings_pool if e.get("family",True)]
    if budget_max:
        evenings_pool = [e for e in evenings_pool if e.get("cost",0) <= budget_max]
    if not evenings_pool:
        evenings_pool = [{"name":"Stargazing at Margaret's Viewpoint - take torch","cost":0,"coords":"-34.07,23.02","family":True,"food":"halal vegan"}]

    plan = []; used = set(); total = 0
    for d in range(1, days+1):
        t = towns[(d-1) % len(towns)]
        k = LOCAL_KNOWLEDGE.get(t.lower().replace(" ","_"), list(LOCAL_KNOWLEDGE.values())[0])
        town_pool = [p for p in pool if p["town"].lower() == t.lower() and p["name"] not in used]
        if len(town_pool) < 2:
            town_pool = [p for p in pool if p["name"] not in used]
        if not town_pool:
            used.clear()
            town_pool = pool
        if not town_pool:
            town_pool = [{"name":"Margaret's Viewpoint","cost":0,"family":True,"food":"halal","coords":"-34.07,23.02","safety":k["safety_tips"],"season":k["best_season"]}]
        morning = town_pool[0]
        afternoon = town_pool[1] if len(town_pool)>1 else town_pool[0]
        used.add(morning["name"])
        used.add(afternoon["name"])
        evening = evenings_pool[(d-1) % len(evenings_pool)]
        day_cost = morning.get("cost",0) + afternoon.get("cost",0) + evening.get("cost",0)
        total += day_cost
        plan.append({
            "day": d, "town": t,
            "morning": f"{morning['name']} R{morning.get('cost',0)}",
            "morning_maps": get_maps_link(morning['name'], morning.get("coords","")),
            "afternoon": f"{afternoon['name']} R{afternoon.get('cost',0)}",
            "afternoon_maps": get_maps_link(afternoon['name'], afternoon.get("coords","")),
            "evening": f"{evening['name']} R{evening['cost']}",
            "evening_maps": get_maps_link(evening['name'], evening['coords']),
            "day_budget": f"R{day_cost}",
            "safety": f"{morning.get('safety','')} - Evening: torch + tell someone + no night swim - Weather: Check NSRI + wind <60km/h - Late Oct warm",
            "best_time": f"{morning.get('season', k['best_season'])} - Go before 8am no crowds",
            "family_friendly": morning.get("family",True),
            "food_info": morning.get("food","any")
        })
    return plan, total

class ItineraryRequest(BaseModel):
 towns: List[str]; days: int; travel_style: str = "adventure"; budget_max: Optional[int] = None; dietary: Optional[str] = None; family_mode: bool = False; shuffle: bool = False

@app.get("/")
def root(): return {"status":"Specialist LIVE v4.1 - FIXED HALAL FAMILY BUDGET MAPS","features":["budget","food filter halal vegan no oyster","family filter","shuffle","maps","weather","halal evenings"],"version":"4.1.0"}

@app.get("/knowledge/{town}")
def get_knowledge(town: str, api_key: str = Depends(get_api_key)):
 key = town.lower().replace(" ","_"); data = LOCAL_KNOWLEDGE.get(key)
 if not data:
  for k in LOCAL_KNOWLEDGE:
   if k in key or key in k: data = LOCAL_KNOWLEDGE[k]; break
 if not data: raise HTTPException(404, detail=f"No data for {town}")
 return {"town": town, "knowledge": data}

@app.post("/itinerary/generate")
def generate(req: ItineraryRequest, api_key: str = Depends(get_api_key)):
 if req.days <1 or req.days>14: raise HTTPException(400, detail="days 1-14")
 plan, total = generate_smart_itinerary(req.towns, req.days, req.travel_style, req.budget_max, req.dietary, req.family_mode, req.shuffle)
 return {"request": req, "route_optimized": True, "route_order": optimize_route(req.towns), "total_budget": f"R{total}", "avg_per_day": f"R{total//req.days if req.days>0 else total}", "itinerary": plan}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
 body = await request.json(); method = body.get("method"); id = body.get("id")
 if method == "initialize": return {"jsonrpc":"2.0","id":id,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"garden-route-specialist","version":"4.1.0"}}}
 if method == "notifications/initialized": return {"jsonrpc":"2.0","id":id,"result":{}}
 if method == "tools/list": return {"jsonrpc":"2.0","id":id,"result":{"tools":[
   {"name":"get_knowledge","description":"Get hidden gems, activities, season and safety with maps and cost","inputSchema":{"type":"object","properties":{"town":{"type":"string"}},"required":["town"]}},
   {"name":"generate_itinerary","description":"Generate itinerary with budget_max (int R), dietary (halal/vegan/no oyster), family_mode (bool), shuffle (bool), Google Maps links, weather safety, total budget","inputSchema":{"type":"object","properties":{"towns":{"type":"array","items":{"type":"string"}},"days":{"type":"integer"},"travel_style":{"type":"string"},"budget_max":{"type":"integer","description":"Max cost per activity in Rand, e.g. 400"},"dietary":{"type":"string","description":"halal, vegan, no oyster, or combo like 'halal vegan'"},"family_mode":{"type":"boolean","description":"True = only kid-friendly"},"shuffle":{"type":"boolean","description":"True = shuffle pool for unique itinerary each time"}},"required":["towns","days"]}}
 ]}}
 if method == "tools/call":
  params = body.get("params",{}); tool_name = params.get("name"); args = params.get("arguments",{})
  if tool_name == "get_knowledge":
   town = args.get("town","knysna"); key = town.lower().replace(" ","_"); data = LOCAL_KNOWLEDGE.get(key)
   if not data:
    for k in LOCAL_KNOWLEDGE:
     if k in key or key in k: data = LOCAL_KNOWLEDGE[k]; break
   if not data: data = LOCAL_KNOWLEDGE["knysna"]
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps({"town": town, "knowledge": data}, indent=2)}]}}
  if tool_name == "generate_itinerary":
   towns = args.get("towns",["knysna","plettenberg_bay"]); days = int(args.get("days",3)); travel_style = args.get("travel_style","adventure"); budget_max = args.get("budget_max"); dietary = args.get("dietary"); family_mode = args.get("family_mode", False); shuffle = args.get("shuffle", False)
   plan, total = generate_smart_itinerary(towns, days, travel_style, budget_max, dietary, family_mode, shuffle)
   result = {"travel_style": travel_style, "route_optimized": True, "route_order": optimize_route(towns), "total_budget": f"R{total}", "avg_per_day": f"R{total//days if days>0 else total}", "filters_applied": {"budget_max":budget_max,"dietary":dietary,"family_mode":family_mode,"shuffle":shuffle}, "itinerary": plan}
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps(result, indent=2)}]}}
 return {"jsonrpc":"2.0","id":id,"result":{}}

@app.get("/mcp")
def mcp_get(): return {"status":"MCP endpoint LIVE v4.1 - FIXED HALAL FAMILY BUDGET MAPS"}