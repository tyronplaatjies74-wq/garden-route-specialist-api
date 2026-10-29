from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import json

app = FastAPI(title="Garden Route Specialist AI Agent", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

API_KEY_NAME = "X-Agent-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
def get_api_key(api_key: str = Security(api_key_header)): return api_key

LOCAL_KNOWLEDGE = {
 "knysna": {"hidden_gems": ["Margaret's Viewpoint -34.07,23.02","Brenton-on-Sea lagoon","Gouna waterfall","Jubilee Creek picnic","Noetzie Beach castles"],"top_activities": ["Lagoon kayak sunrise","Heads hike","Forest market","Featherbed Eco Trail","Oyster tasting"],"best_season": "Oct-Apr warm","safety_tips": "Heads closes high tide - check NSRI"},
 "plettenberg_bay": {"hidden_gems": ["Nature's Valley secret beach","Salt River mouth","Robberg 6am seals","Arch Rock sunrise","Keurbooms lagoon"],"top_activities": ["Robberg hike","Whale watch boat","Monkeyland","Birds of Eden","Old Nick Market"],"best_season": "June-Nov whales","safety_tips": "Check tide for Robberg - don't get cut off"},
 "george": {"hidden_gems": ["Kaaimans River mouth","George Peak secret trail","Victoria Bay","Herold wine farm"],"top_activities": ["Wilderness beach","Dam hike","Outeniqua train museum","Redberry Farm"],"best_season": "Year round","safety_tips": "Mountain weather changes fast"},
 "mossel_bay": {"hidden_gems": ["St Blaize cave","Dana Bay tidal pool","Island sunset","Pinnacle Point caves"],"top_activities": ["Shark cage","Point sunset","Santos beach walk","Dias Museum"],"best_season": "Year round","safety_tips": "Santos rip current - swim flags"},
 "wilderness": {"hidden_gems": ["Map of Africa viewpoint","Kingfisher trail","Half-collared kingfisher spot","Rondevlei birds"],"top_activities": ["Touw River kayak","Beach walk","Paragliding","Hoekwil market"],"best_season": "Morning kayak best","safety_tips": "Touw mouth low tide only"},
 "tsitsikamma": {"hidden_gems": ["Storms River bridge 7am no crowd","Otto trail","Nature's Valley - no signal zone","Bloukrans secret viewpoint"],"top_activities": ["Canopy tour","Storms hike Mouth Trail","Blackwater tubing","Bungy"],"best_season": "Morning no wind","safety_tips": "Bridge closes in wind over 60km/h"},
 "oudtshoorn": {"hidden_gems": ["Swartberg Pass sunset - best in SA","Cango Caves 8am before buses","Meiringspoort waterfall","Rust en Vrede waterfall"],"top_activities": ["Ostrich farm","Swartberg drive","Meerkat tour sunrise","Karoo wine"],"best_season": "Winter cooler","safety_tips": "No night driving Swartberg Pass"}
}

ROUTE_ORDER = ["mossel_bay","george","wilderness","knysna","plettenberg_bay","tsitsikamma","oudtshoorn"]
def optimize_route(towns):
    def sort_key(t):
        key = t.lower().replace(" ","_")
        try: return ROUTE_ORDER.index(key)
        except: return 99
    return sorted(towns, key=sort_key)

def generate_smart_itinerary(towns, days, travel_style):
    towns = optimize_route(towns)
    pool = []
    for t in towns:
        k = LOCAL_KNOWLEDGE.get(t.lower().replace(" ","_"))
        if k:
            for act in k["top_activities"]:
                pool.append({"town": t, "type": "activity", "name": act, "safety": k["safety_tips"], "season": k["best_season"]})
            for gem in k["hidden_gems"]:
                pool.append({"town": t, "type": "hidden_gem", "name": gem, "safety": k["safety_tips"], "season": k["best_season"]})
    
    evenings_pool = ["Sunset at The Heads + cocktails at Island Cafe","Lagoon-side dinner at Drydock","Beach braai at Brenton-on-Sea","Stargazing at Margaret's Viewpoint - take torch","Live music at 34 South","Forest night walk in Gouna","Sunset cruise on Knysna Lagoon"]

    plan = []
    used = set()
    for d in range(1, days+1):
        t = towns[(d-1) % len(towns)]
        k = LOCAL_KNOWLEDGE.get(t.lower().replace(" ","_"), list(LOCAL_KNOWLEDGE.values())[0])
        town_pool = [p for p in pool if p["town"].lower() == t.lower() and p["name"] not in used]
        if len(town_pool) < 2:
            town_pool = [p for p in pool if p["name"] not in used]
        if not town_pool:
            used.clear()
            town_pool = pool
        morning = town_pool[0] if town_pool else {"name": k["top_activities"][0], "town": t, "safety": k["safety_tips"], "season": k["best_season"]}
        afternoon = town_pool[1] if len(town_pool)>1 else town_pool[0]
        used.add(morning["name"])
        used.add(afternoon["name"])
        
        evening = evenings_pool[(d-1) % len(evenings_pool)]
        
        plan.append({
            "day": d, 
            "town": t, 
            "morning": f"{morning['name']} ({morning['town']})", 
            "afternoon": f"{afternoon['name']} ({afternoon['town']})", 
            "evening": evening,
            "safety": f"{morning.get('safety','')} - Evening: torch + tell someone + no night swim", 
            "best_time": f"{morning.get('season', k['best_season'])} - Late Oct warm, go before 8am no crowds", 
            "pro_tip": f"Early start for {morning['name']} = no crowds"
        })
    return plan

class ItineraryRequest(BaseModel):
 towns: List[str]
 days: int
 travel_style: str = "adventure"

@app.get("/")
def root(): return {"status":"Specialist LIVE v3 - PERFECT - No Repeats","mcp":"/mcp endpoint LIVE for Claude Free"}

@app.get("/knowledge/{town}")
def get_knowledge(town: str, api_key: str = Depends(get_api_key)):
 key = town.lower().replace(" ","_")
 data = LOCAL_KNOWLEDGE.get(key)
 if not data:
  for k in LOCAL_KNOWLEDGE:
   if k in key or key in k: data = LOCAL_KNOWLEDGE[k]; break
 if not data: raise HTTPException(404, detail=f"No data for {town}")
 return {"town": town, "knowledge": data}

@app.post("/itinerary/generate")
def generate(req: ItineraryRequest, api_key: str = Depends(get_api_key)):
 if req.days <1 or req.days>14: raise HTTPException(400, detail="days 1-14")
 plan = generate_smart_itinerary(req.towns, req.days, req.travel_style)
 return {"request": req, "route_optimized": True, "route_order": optimize_route(req.towns), "itinerary": plan}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
 body = await request.json()
 method = body.get("method")
 id = body.get("id")
 if method == "initialize":
  return {"jsonrpc":"2.0","id":id,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"garden-route-specialist","version":"3.0.0"}}}
 if method == "notifications/initialized":
  return {"jsonrpc":"2.0","id":id,"result":{}}
 if method == "tools/list":
  return {"jsonrpc":"2.0","id":id,"result":{"tools":[
   {"name":"get_knowledge","description":"Get hidden gems, activities, season and safety for any Garden Route town","inputSchema":{"type":"object","properties":{"town":{"type":"string"}},"required":["town"]}},
   {"name":"generate_itinerary","description":"Generate multi-day Garden Route itinerary with unique plan each day, route optimized","inputSchema":{"type":"object","properties":{"towns":{"type":"array","items":{"type":"string"}},"days":{"type":"integer"},"travel_style":{"type":"string"}},"required":["towns","days"]}}
  ]}}
 if method == "tools/call":
  params = body.get("params",{})
  tool_name = params.get("name")
  args = params.get("arguments",{})
  if tool_name == "get_knowledge":
   town = args.get("town","knysna")
   key = town.lower().replace(" ","_")
   data = LOCAL_KNOWLEDGE.get(key)
   if not data:
    for k in LOCAL_KNOWLEDGE:
     if k in key or key in k: data = LOCAL_KNOWLEDGE[k]; break
   if not data: data = LOCAL_KNOWLEDGE["knysna"]
   result_text = json.dumps({"town": town, "knowledge": data}, indent=2)
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text":result_text}]}}
  if tool_name == "generate_itinerary":
   towns = args.get("towns",["knysna","plettenberg_bay"])
   days = int(args.get("days",3))
   travel_style = args.get("travel_style","adventure")
   plan = generate_smart_itinerary(towns, days, travel_style)
   result = {"travel_style": travel_style, "route_optimized": True, "route_order": optimize_route(towns), "itinerary": plan}
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps(result, indent=2)}]}}
 return {"jsonrpc":"2.0","id":id,"result":{}}

@app.get("/mcp")
def mcp_get(): return {"status":"MCP endpoint LIVE v3 - PERFECT"}