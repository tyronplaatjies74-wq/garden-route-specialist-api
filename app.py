from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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

@app.get("/")
def root(): return {"status":"Specialist LIVE","endpoints":["/knowledge/{town}","/itinerary/generate"]}

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
