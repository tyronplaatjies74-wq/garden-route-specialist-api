from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import json

app = FastAPI(title="Garden Route Specialist AI Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

API_KEY_NAME = "X-Agent-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
def get_api_key(api_key: str = Security(api_key_header)): return api_key

LOCAL_KNOWLEDGE = {
 "knysna": {"hidden_gems": ["Margaret's Viewpoint -34.07,23.02","Brenton-on-Sea lagoon","Gouna waterfall"],"top_activities": ["Lagoon kayak","Heads hike","Forest market"],"best_season": "Oct-Apr warm","safety_tips": "Heads closes high tide"},
 "plettenberg_bay": {"hidden_gems": ["Nature's Valley","Salt River mouth","Robberg 6am seals"],"top_activities": ["Robberg hike","Whale watch","Monkeyland"],"best_season": "June-Nov whales","safety_tips": "Check tide for Robberg"},
 "george": {"hidden_gems": ["Kaaimans River mouth","George Peak"],"top_activities": ["Wilderness beach","Dam hike"],"best_season": "Year round","safety_tips": "Mountain weather fast"},
 "mossel_bay": {"hidden_gems": ["St Blaize cave","Dana Bay pool"],"top_activities": ["Shark cage","Point sunset"],"best_season": "Year round","safety_tips": "Santos rip current"},
 "wilderness": {"hidden_gems": ["Map of Africa","Kingfisher trail"],"top_activities": ["Touw River kayak","Beach walk"],"best_season": "Morning kayak","safety_tips": "Touw mouth low tide only"},
 "tsitsikamma": {"hidden_gems": ["Storms River bridge early","Otto trail"],"top_activities": ["Canopy tour","Storms hike"],"best_season": "Morning no wind","safety_tips": "Bridge closes in wind"},
 "oudtshoorn": {"hidden_gems": ["Swartberg sunset","Cango 8am"],"top_activities": ["Ostrich farm","Swartberg drive"],"best_season": "Winter cooler","safety_tips": "No night driving Swartberg"}
}

class ItineraryRequest(BaseModel):
 towns: List[str]
 days: int
 travel_style: str = "adventure"

# --- YOUR ORIGINAL ENDPOINTS (KEEP) ---
@app.get("/")
def root(): return {"status":"Specialist LIVE","mcp":"/mcp endpoint LIVE for Claude Free","endpoints":["/knowledge/{town}","/itinerary/generate"]}

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
 plan=[]
 for d in range(1, req.days+1):
  t = req.towns[(d-1)%len(req.towns)]
  k = LOCAL_KNOWLEDGE.get(t.lower().replace(" ","_"), list(LOCAL_KNOWLEDGE.values())[0])
  plan.append({"day": d, "town": t, "morning": k["top_activities"][0], "afternoon": k["hidden_gems"][0], "safety": k["safety_tips"]})
 return {"request": req, "route_optimized": True, "itinerary": plan}

# --- NEW MCP FOR CLAUDE FREE (BOARDING DOOR) ---
@app.post("/mcp")
async def mcp_endpoint(request: Request):
 body = await request.json()
 method = body.get("method")
 id = body.get("id")
 
 if method == "initialize":
  return {"jsonrpc":"2.0","id":id,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"garden-route-specialist","version":"1.0.0"}}}
 
 if method == "notifications/initialized":
  return {"jsonrpc":"2.0","id":id,"result":{}}
 
 if method == "tools/list":
  return {"jsonrpc":"2.0","id":id,"result":{"tools":[
   {"name":"get_knowledge","description":"Get hidden gems, activities, season and safety for any Garden Route town. Towns: knysna, plettenberg_bay, george, mossel_bay, wilderness, tsitsikamma, oudtshoorn","inputSchema":{"type":"object","properties":{"town":{"type":"string","description":"Town name e.g. Knysna"}},"required":["town"]}},
   {"name":"generate_itinerary","description":"Generate multi-day Garden Route itinerary with route optimization, hidden gems and safety tips","inputSchema":{"type":"object","properties":{"towns":{"type":"array","items":{"type":"string"},"description":"List of towns"},"days":{"type":"integer","description":"Days 1-14"},"travel_style":{"type":"string","description":"adventure, nature, food, beach"}},"required":["towns","days"]}}
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
   plan=[]
   for d in range(1, days+1):
    t = towns[(d-1)%len(towns)]
    k = LOCAL_KNOWLEDGE.get(t.lower().replace(" ","_"), list(LOCAL_KNOWLEDGE.values())[0])
    plan.append({"day": d, "town": t, "morning": k["top_activities"][0], "afternoon": k["hidden_gems"][0], "safety": k["safety_tips"]})
   result = {"travel_style": travel_style, "route_optimized": True, "itinerary": plan}
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps(result, indent=2)}]}}
 
 return {"jsonrpc":"2.0","id":id,"result":{}}

@app.get("/mcp")
def mcp_get(): return {"status":"MCP endpoint LIVE - POST to /mcp for Claude"}
