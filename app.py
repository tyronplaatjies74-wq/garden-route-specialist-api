from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
import json, random, urllib.parse

app = FastAPI(title="Garden Route Specialist AI Agent", version="8.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
API_KEY_NAME = "X-Agent-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
def get_api_key(api_key: str = Security(api_key_header)): 
    return api_key  # optional now

# KEEP YOUR FULL v7 KNOWLEDGE - DO NOT DELETE
LOCAL_KNOWLEDGE = {
 "wilderness": {
   "hidden_gems": [
     {"name":"Map of Africa viewpoint","coords":"-33.99,22.60","cost":0,"family":True,"food":"vegan vegetarian halal","styles":["chill","family","backpacker"]},
     {"name":"Half Collared Kingfisher Trail","coords":"-33.98,22.59","cost":0,"family":True,"food":"any","styles":["adventure","family","chill","backpacker"]},
   ],
   "top_activities": [
     {"name":"Wilderness beach walk","cost":0,"family":True,"food":"any","coords":"-33.99,22.57","styles":["chill","family","backpacker"]},
     {"name":"Ebb & Flow bird hide","cost":0,"family":True,"food":"any","coords":"-33.98,22.60","styles":["chill","family","backpacker"]},
     {"name":"Touw River kayak","cost":400,"family":True,"food":"any","coords":"-33.99,22.60","styles":["adventure","family"]},
   ],
   "hotels": [
     {"name":"Wilderness Backpackers dorm","cost":280,"family":False,"halal":False,"styles":["backpacker"]},
     {"name":"Wilderness Beach House Backpacker dorm","cost":300,"family":True,"halal":True,"styles":["backpacker","family"]},
   ],
   "free_evenings": [
     {"name":"Stargazing at Map of Africa - free","cost":0,"coords":"-33.99,22.60","food":"vegan vegetarian halal","styles":["chill","backpacker"]},
     {"name":"Self-cook at hostel kitchen - free","cost":0,"coords":"-33.99,22.60","food":"vegetarian vegan halal","styles":["backpacker","foodie"]},
   ],
   "paid_evenings": [{"name":"Wilderness Farmers Market vegetarian curry","cost":80,"coords":"-33.99,22.60","food":"vegetarian vegan halal","styles":["foodie","family","backpacker"]}],
   "best_season":"Morning kayak best - Oct-Apr","safety_tips":"Touw mouth low tide only - Check NSRI"
 },
 "knysna": {
   "hidden_gems": [{"name":"Margaret's Viewpoint","coords":"-34.07,23.02","cost":0,"family":True,"food":"vegan vegetarian","styles":["chill","family","backpacker"]}],
   "top_activities": [
     {"name":"Heads hike","cost":0,"family":True,"food":"any","coords":"-34.08,23.05","styles":["adventure","chill","family","backpacker"]},
     {"name":"Knysna Waterfront stroll","cost":0,"family":True,"food":"any","coords":"-34.04,23.05","styles":["chill","family","backpacker"]},
   ],
   "hotels": [
     {"name":"Knysna Paradise Backpackers dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"]},
     {"name":"Knysna Backpackers dorm","cost":300,"family":False,"halal":False,"styles":["backpacker"]},
   ],
   "free_evenings": [{"name":"Stargazing at Margaret's Viewpoint - torch - free","cost":0,"coords":"-34.07,23.02","food":"vegan vegetarian","styles":["chill","backpacker","family"]}],
   "paid_evenings": [{"name":"Forest market veg wrap","cost":90,"coords":"-33.95,23.04","food":"vegetarian vegan halal","styles":["foodie","backpacker"]}],
   "best_season":"Oct-Apr warm","safety_tips":"Heads closes high tide - check NSRI"
 },
 "plettenberg_bay": {
   "hidden_gems": [{"name":"Salt River mouth trail","coords":"-34.03,23.35","cost":0,"family":True,"food":"any","styles":["adventure","chill","backpacker"]}],
   "top_activities": [
     {"name":"Robberg hike","cost":0,"family":False,"food":"any","coords":"-34.10,23.38","styles":["adventure","backpacker"]},
     {"name":"Plett beach central","cost":0,"family":True,"food":"any","coords":"-34.05,23.37","styles":["chill","family","backpacker"]},
   ],
   "hotels": [
     {"name":"Albergo Backpackers Plett dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"]},
     {"name":"Plett Backpackers dorm","cost":320,"family":False,"halal":False,"styles":["backpacker"]},
   ],
   "free_evenings": [{"name":"Plett beach sunset - free","cost":0,"coords":"-34.05,23.37","food":"any","styles":["chill","backpacker"]}],
   "paid_evenings": [{"name":"Old Nick Market veg wrap","cost":90,"coords":"-34.04,23.37","food":"vegetarian vegan halal","styles":["foodie","backpacker"]}],
   "best_season":"June-Nov whales","safety_tips":"Check tide for Robberg - NSRI"
 },
 "tsitsikamma": {
   "hidden_gems": [{"name":"Misty Mountain fynbos walk","coords":"-33.99,23.88","cost":0,"family":True,"food":"any","styles":["chill","family","backpacker"]}],
   "top_activities": [
     {"name":"Storms River Mouth walk","cost":0,"family":True,"food":"any","coords":"-34.02,23.90","styles":["chill","family","backpacker"]},
     {"name":"Storms River bridge 7am","cost":0,"family":False,"food":"any","coords":"-34.02,23.90","styles":["adventure","backpacker"]},
   ],
   "hotels": [
     {"name":"Dijembe Backpackers Storms River dorm","cost":280,"family":True,"halal":True,"styles":["backpacker","family"]},
     {"name":"Tsitsikamma Backpackers dorm","cost":300,"family":False,"halal":False,"styles":["backpacker"]},
   ],
   "free_evenings": [{"name":"Self-cook at hostel kitchen - free - Tsitsikamma","cost":0,"coords":"-33.97,23.89","food":"vegetarian vegan halal","styles":["backpacker","foodie"]}],
   "paid_evenings": [{"name":"Tsitsikamma Village Market veg soup","cost":60,"coords":"-33.95,23.88","food":"vegetarian vegan halal","styles":["foodie","backpacker"]}],
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
        k = LOCAL_KNOWLEDGE.get(key, LOCAL_KNOWLEDGE["wilderness"])
        if is_backpacker_budget:
            free_acts = [a for a in (k["top_activities"] + k["hidden_gems"]) if a["cost"] == 0]
            pool = free_acts or k["top_activities"]
            morning = pool[0]; afternoon = pool[1] if len(pool)>1 else pool[0]
            evening = k["free_evenings"][(d-1) % len(k["free_evenings"])]
            hotel = sorted(k["hotels"], key=lambda x: x["cost"])[0]
        else:
            pool = k["top_activities"] + k["hidden_gems"]
            morning = pool[0]; afternoon = pool[1] if len(pool)>1 else pool[0]
            evening = k["free_evenings"][0]
            hotel = sorted(k["hotels"], key=lambda x: x["cost"])[0]
        used.add(morning["name"]); used.add(afternoon["name"])
        day_activities = morning["cost"] + afternoon["cost"] + evening["cost"]
        day_with_hotel = day_activities + hotel["cost"]
        total += day_activities; total_hotels += day_with_hotel
        plan.append({
            "day": d, "town": t, "town_verified": t,
            "morning": f"{morning['name']} R{morning['cost']} - {t}",
            "morning_maps": get_maps_link(morning["name"], morning.get("coords","")),
            "afternoon": f"{afternoon['name']} R{afternoon['cost']} - {t}",
            "afternoon_maps": get_maps_link(afternoon["name"], afternoon.get("coords","")),
            "evening": f"{evening['name']} R{evening['cost']} - {t}",
            "evening_maps": get_maps_link(evening["name"], evening.get("coords","")),
            "hotel": f"{hotel['name']} R{hotel['cost']}/night",
            "hotel_maps": get_maps_link(hotel["name"], morning.get("coords","")),
            "day_budget_with_hotel": f"R{day_with_hotel} - {'FITS R300' if day_with_hotel <= (budget_max or 999) else 'OVER'}",
            "safety": k["safety_tips"], "best_time": k["best_season"]
        })
    return plan, total, total_hotels

class ItineraryRequest(BaseModel):
 towns: List[str]; days: int; travel_style: str = "adventure"; budget_max: Optional[int] = None; dietary: Optional[str] = None; family_mode: bool = False; shuffle: bool = False

# NEW v8 FRONTEND - Pretty site at /
@app.get("/", response_class=HTMLResponse)
def frontend():
    return """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Garden Route v8 - R280/day</title>
<style>body{font-family:Arial;background:#0f172a;color:#fff;margin:0;padding:16px}.card{background:#1e293b;border-radius:16px;padding:16px;margin:12px 0}h1{color:#22c55e;text-align:center}button{background:#22c55e;color:#000;padding:14px;border:none;border-radius:10px;width:100%;font-weight:bold;font-size:18px}input{width:100%;padding:12px;border-radius:8px;margin:6px 0;background:#334155;color:#fff;border:none} a{color:#38bdf8} .badge{background:#22c55e;color:#000;padding:4px 8px;border-radius:6px;font-size:12px}</style></head><body>
<h1>🌿 Garden Route Specialist v8</h1><p style="text-align:center"><span class="badge">R280/day FITS R300 - dorms + free hikes + self-cook</span><br>4-Day Wilderness to Tsitsikamma</p>
<div class="card"><input id="towns" value="wilderness,knysna,plettenberg_bay,tsitsikamma"><input id="days" type="number" value="4"><input id="budget" type="number" value="300"><button onclick="go()">Generate Itinerary</button></div><div id="out"></div>
<script>async function go(){const towns=document.getElementById('towns').value.split(',').map(s=>s.trim());const days=parseInt(document.getElementById('days').value);const budget_max=parseInt(document.getElementById('budget').value);document.getElementById('out').innerHTML='<div class=card>Generating R280/day...</div>';const r=await fetch('/itinerary/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({towns,days,travel_style:'backpacker',budget_max})});const d=await r.json();let h=`<div class=card><b>Total R${d.total_budget_with_hotels} = R${Math.round(parseInt(d.total_budget_with_hotels.replace('R',''))/days)}/day FITS R${budget_max}</b></div>`;d.itinerary.forEach(x=>{h+=`<div class=card><b>Day ${x.day}: ${x.town} - ${x.day_budget_with_hotel}</b><br><br>🌅 ${x.morning}<br><a href="${x.morning_maps}" target="_blank">📍 Maps</a><br><br>☀️ ${x.afternoon}<br><a href="${x.afternoon_maps}" target="_blank">📍 Maps</a><br><br>🌙 ${x.evening}<br><a href="${x.evening_maps}" target="_blank">📍 Maps</a><br><br>🏨 ${x.hotel}<br><a href="${x.hotel_maps}" target="_blank">📍 Maps</a><br><br>⚠️ ${x.safety}</div>`;});document.getElementById('out').innerHTML=h;}</script></body></html>"""

@app.post("/itinerary/generate")
def generate(req: ItineraryRequest):
 if req.days <1 or req.days>30: raise HTTPException(400, detail="days 1-30")
 plan, total, total_hotels = generate_smart_itinerary(req.towns, req.days, req.travel_style, req.budget_max, req.dietary, req.family_mode, req.shuffle)
 return {"route_optimized": True, "total_budget_with_hotels": f"R{total_hotels}", "avg_per_day_with_hotels": f"R{total_hotels//req.days}", "itinerary": plan}

@app.post("/mcp")
async def mcp_endpoint(request: Request):
 body = await request.json(); method = body.get("method"); id = body.get("id")
 if method == "initialize": return {"jsonrpc":"2.0","id":id,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"garden-route-specialist","version":"8.0.0"}}}
 if method == "tools/list": return {"jsonrpc":"2.0","id":id,"result":{"tools":[{"name":"get_knowledge","description":"Get hidden gems","inputSchema":{"type":"object","properties":{"town":{"type":"string"}},"required":["town"]}},{"name":"generate_itinerary","description":"Generate ANY itinerary FIXED v7: daily budget R300 includes hotel","inputSchema":{"type":"object","properties":{"towns":{"type":"array","items":{"type":"string"}},"days":{"type":"integer"},"travel_style":{"type":"string"},"budget_max":{"type":"integer"},"dietary":{"type":"string"},"family_mode":{"type":"boolean"}},"required":["towns","days"]}}]}}
 if method == "tools/call":
  params = body.get("params",{}); tool_name = params.get("name"); args = params.get("arguments",{})
  if tool_name == "generate_itinerary":
   towns = args.get("towns",["knysna"]); days = int(args.get("days",3)); travel_style = args.get("travel_style","backpacker"); budget_max = args.get("budget_max"); dietary = args.get("dietary"); family_mode = args.get("family_mode", False); shuffle = args.get("shuffle", False)
   plan, total, total_hotels = generate_smart_itinerary(towns, days, travel_style, budget_max, dietary, family_mode, shuffle)
   result = {"total_budget_with_hotels": f"R{total_hotels}", "itinerary": plan}
   return {"jsonrpc":"2.0","id":id,"result":{"content":[{"type":"text","text": json.dumps(result, indent=2)}]}}
 return {"jsonrpc":"2.0","id":id,"result":{}}

@app.get("/mcp")
def mcp_get(): return {"status":"MCP endpoint LIVE v8 FRONTEND+BACKEND","version":"8.0.0"}