"""
planner.py - Garden Route engine v7.6

Adds to v7.5:
  1. Transit fallback: if a town has nothing left/open (or it's raining), the day becomes
     a trip to the nearest hub instead of "Free time".
  2. Walking clusters: afternoon must be walkable (<= WALK_KM) from the morning stop, or
     a short taxi/shuttle hop (<= HOP_KM) that is costed. Evenings must be walkable or
     self-cook. No cross-region zig-zags.
  3. Month of travel: season-aware picks, whale season, seasonal hostel prices,
     rainy_days (days the traveller wants rain-proofed).

ALL travel times/fares below are ESTIMATES. Verify them before showing to travellers.
Env (optional): FOOD_ALLOWANCE, BOOKING_AID, TAXI_R_PER_KM, LOCAL_HOP_COST, SEASON_PRICING
"""
import math, os, random, re, urllib.parse

KB = {}  # set by setup() from main.py


def setup(knowledge):
    global KB
    KB = knowledge


# ============================ CONFIG ============================
FOOD_ALLOWANCE = int(os.getenv("FOOD_ALLOWANCE", "100"))
BOOKING_AID = os.getenv("BOOKING_AID")
TAXI_R_PER_KM = float(os.getenv("TAXI_R_PER_KM", "1.2"))   # assumption - tune it
LOCAL_HOP_COST = int(os.getenv("LOCAL_HOP_COST", "30"))    # assumption: short in-town taxi/shuttle
SEASON_PRICING = os.getenv("SEASON_PRICING", "1") != "0"
WALK_KM = 3.0     # walkable between stops
HOP_KM = 15.0     # max for a same-day taxi/shuttle hop inside a town's area
MAX_DAYS = 30
VALID_STYLES = {"adventure", "backpacker", "family", "chill", "foodie"}
DIET_OK = {"vegan": {"vegan"}, "vegetarian": {"vegetarian", "vegan"}, "halal": {"halal"}}
REST_NAME = "Free time - rest or explore on your own"

ROUTE_ORDER = ["mossel_bay", "george", "wilderness", "knysna", "plettenberg_bay", "tsitsikamma"]  # west -> east
TOWN_ALIASES = {
    "mossel": "mossel_bay", "plett": "plettenberg_bay", "plettenberg": "plettenberg_bay",
    "brenton": "knysna", "brenton_on_sea": "knysna",
    "storms_river": "tsitsikamma", "stormsriver": "tsitsikamma",
}

# (minutes, km) between consecutive towns in ROUTE_ORDER. ESTIMATES - verify.
SEGMENTS = [(45, 50), (20, 15), (40, 50), (40, 35), (55, 70)]
# Where to go when a town has nothing (left) to do.
HUBS = {
    "mossel_bay": "george", "george": "knysna", "wilderness": "george",
    "knysna": "plettenberg_bay", "plettenberg_bay": "knysna", "tsitsikamma": "plettenberg_bay",
}

# ============================ SEASONS ============================
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
SEASON_OF = {12: "summer", 1: "summer", 2: "summer", 3: "autumn", 4: "autumn", 5: "autumn",
             6: "winter", 7: "winter", 8: "winter", 9: "spring", 10: "spring", 11: "spring"}
WHALE_MONTHS = {6, 7, 8, 9, 10, 11}
WHALE_SPOTS = ("robberg", "st blaize", "point", "heads")
PRICE_MULT = {12: 1.35, 1: 1.30, 2: 1.10, 4: 1.05}  # assumption: peak/holiday uplift on dorm beds
SEASON_NOTES = {
    "summer": "Warm and busy. Peak hostel prices around Dec-Jan: book early. Best beach/lagoon weather.",
    "autumn": "Mild and quieter. Good hiking weather.",
    "winter": "Cold with rain fronts and early dark (about 17:30). Beach days are down-ranked; markets and covered spots favoured. Whale season.",
    "spring": "Warming up, often windy, sea still cold. Whale watching at its best.",
}
# score adjustments by activity kind
SEASON_WEIGHTS = {
    "winter": {"beach": -3, "night": -2, "indoor": 2},
    "spring": {"beach": -1},
    "summer": {"beach": 2},
}
RAIN_OK = {"indoor", "covered"}  # on a rainy day only these are offered


def parse_month(m):
    if m is None or str(m).strip() == "":
        return None
    s = str(m).strip().lower()
    if s.isdigit():
        n = int(s)
    else:
        n = MONTHS.get(s[:3])
    if not n or not 1 <= n <= 12:
        raise ValueError("month must be a month name (e.g. 'July') or a number 1-12")
    return n


def parse_rainy(rainy_days, days):
    if not rainy_days:
        return set()
    try:
        out = {int(d) for d in rainy_days}
    except (TypeError, ValueError):
        raise ValueError("rainy_days must be a list of day numbers, e.g. [2, 3]")
    if any(d < 1 or d > days for d in out):
        raise ValueError(f"rainy_days must be between 1 and {days}")
    return out


def season_info(month):
    if not month:
        return None
    s = SEASON_OF[month]
    return {
        "month": MONTH_NAMES[month], "season": s, "notes": SEASON_NOTES[s],
        "whale_season": month in WHALE_MONTHS,
        "hostel_price_multiplier": PRICE_MULT.get(month, 1.0) if SEASON_PRICING else 1.0,
        "tip": "Rain is possible in any month on the Garden Route. Pass rainy_days to plan indoor/hub days.",
    }


def season_price(cost, month):
    mult = PRICE_MULT.get(month, 1.0) if (SEASON_PRICING and month) else 1.0
    return int(round(cost * mult / 10.0)) * 10


def activity_kind(item):
    n = item["name"].lower()
    if any(w in n for w in ("market", "curry", "wrap", "soup", "self-cook")):
        return "indoor"
    if "hide" in n:
        return "covered"
    if any(w in n for w in ("stargaz", "sunset")):
        return "night"
    if any(w in n for w in ("beach", "lagoon", "kayak")):
        return "beach"
    if any(w in n for w in ("hike", "trail", "walk", "bridge", "viewpoint", "stroll",
                            "botanical", "reserve", "fynbos")):
        return "hike"
    return "outdoor"


# ============================ GEO / TRANSIT ============================
def item_coords(item):
    try:
        a, b = str(item.get("coords", "")).split(",")
        return float(a), float(b)
    except ValueError:
        return None


def km_between(c1, c2):
    if not c1 or not c2:
        return None
    la1, lo1, la2, lo2 = map(math.radians, (*c1, *c2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def route_leg(a, b):
    """(minutes, km) between two towns, summed along the N2."""
    i, j = sorted((ROUTE_ORDER.index(a), ROUTE_ORDER.index(b)))
    seg = SEGMENTS[i:j]
    return sum(s[0] for s in seg), sum(s[1] for s in seg)


def fare_for(km):
    return max(LOCAL_HOP_COST, int(round(km * TAXI_R_PER_KM / 5.0)) * 5)


MODE_TEXT = "a shared minibus taxi, the Baz Bus or a hostel lift (ask at reception)"


# ============================ HELPERS ============================
def display(key):
    return key.replace("_", " ")


def resolve_town(name):
    key = re.sub(r"[\s\-]+", "_", str(name).strip().lower())
    key = TOWN_ALIASES.get(key, key)
    return key if key in KB else None


def valid_towns_text():
    return ", ".join(display(k) for k in ROUTE_ORDER)


def optimize_route(keys):
    return sorted(keys, key=lambda k: ROUTE_ORDER.index(k) if k in ROUTE_ORDER else 99)


def allocate_days(n_towns, days):
    base, extra = divmod(days, n_towns)
    return [base + (1 if i < extra else 0) for i in range(n_towns)]


def fmt_cost(c):
    return f"R{c}" if c and c > 0 else "FREE"


def clean_name(name):
    name = re.sub(r"\s*-\s*FREE\b", "", name, flags=re.I)
    name = re.sub(r"\s*-\s*torch\b", " (bring a torch)", name, flags=re.I)
    return name.strip()


def is_self_cook(item):
    return "self-cook" in item["name"].lower()


def maps_link(query):
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(query, safe=",-.")


def clean_booking_link(url):
    if not url:
        return None
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "aid"]
    if BOOKING_AID:
        query.append(("aid", BOOKING_AID))
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def normalize_diet(d):
    if not d:
        return None
    d = str(d).strip().lower()
    for key in ("vegan", "vegetarian", "halal"):
        if key in d:
            return key
    return None


def diet_status(item, diet, is_meal):
    tags = {t.lower() for t in item.get("dietary_tags", [])}
    if DIET_OK[diet] & tags:
        return "verified"
    return "unverified" if is_meal else "no_meal"


# ============================ PICKING ============================
def season_score(item, ctx):
    kind = activity_kind(item)
    s = SEASON_WEIGHTS.get(ctx["season"], {}).get(kind, 0)
    if ctx["rain"] and kind in RAIN_OK:
        s += 4
    if ctx["month"] in WHALE_MONTHS and any(w in item["name"].lower() for w in WHALE_SPOTS):
        s += 3
    return s


def score(item, ctx, used, is_meal, km=None):
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
    s += season_score(item, ctx)
    if km is not None:
        s += 2 if km <= WALK_KM else -0.3 * (km - WALK_KM)
    s += ctx["rng"].random() * (5 if ctx["shuffle"] else 0.01)
    return s


def pick(pool, used, remaining, ctx, is_meal=False, repeatable=lambda i: False, anchor=None, max_km=HOP_KM):
    """Returns (item, local_hop_cost). Item is None if nothing fits."""
    limit = max(remaining, 0)
    best, best_hop, best_s = None, 0, None
    a_xy = item_coords(anchor) if anchor else None
    for i in pool:
        if not (repeatable(i) or i["name"] not in used):
            continue
        if ctx["family"] and not i.get("family", True):
            continue
        if ctx["rain"] and activity_kind(i) not in RAIN_OK:
            continue
        km, hop = None, 0
        if a_xy and not repeatable(i):
            km = km_between(a_xy, item_coords(i))
            if km is not None:
                if km > max_km:
                    continue
                if km > WALK_KM:
                    hop = LOCAL_HOP_COST
        if i.get("cost", 0) + hop > limit:
            continue
        sc = score(i, ctx, used, is_meal, km)
        if best is None or sc > best_s:
            best, best_hop, best_s = i, hop, sc
    return best, best_hop


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


def make_slot(item, hotel, town, diet, is_meal, extra=0, ctx=None, suffix=""):
    if item is None:
        return {"name": REST_NAME, "cost": 0, "maps": None, "diet": None, "text": REST_NAME}
    name = clean_name(item["name"])
    q = f"{hotel['name']} {town}" if is_self_cook(item) else (item.get("coords") or f"{name} {town}")
    cost = item.get("cost", 0) + extra
    text = f"{name} - {fmt_cost(cost)}"
    if extra:
        text += f" (incl. R{extra} ride)"
    if ctx and ctx["month"] in WHALE_MONTHS and any(w in name.lower() for w in WHALE_SPOTS):
        text += " [whale-watching season - sightings not guaranteed]"
    text += suffix
    return {"name": name, "cost": cost, "maps": maps_link(q),
            "diet": diet_status(item, diet, is_meal) if diet else None, "text": text}


# ============================ CORE ============================
def generate_smart_itinerary(keys, days, style, budget_max, diet, family_mode, shuffle, seed, warnings,
                             month=None, rainy_days=()):
    def warn(msg):
        if msg not in warnings:
            warnings.append(msg)

    budget = float(budget_max) if budget_max is not None else float("inf")
    ctx = {
        "style": style, "diet": diet,
        "family": bool(family_mode) or style == "family",
        "shuffle": bool(shuffle),
        "frugal": style == "backpacker" or (budget_max is not None and budget_max <= 500),
        "rng": random.Random(seed),
        "month": month, "season": SEASON_OF.get(month),
        "rainy": set(rainy_days or ()), "rain": False,
    }

    towns = optimize_route(keys)
    if len(towns) > days:
        dropped = ", ".join(display(t) for t in towns[days:])
        warn(f"{len(towns)} towns but only {days} day(s): skipping {dropped}. Add days to include them.")
        towns = towns[:days]
    blocks = allocate_days(len(towns), days)

    used, plan, base_costs, unverified_days = set(), [], [], []
    day_no, prev = 1, None
    for key, n_days in zip(towns, blocks):
        k = KB[key]
        town = display(key)
        day_pool = k["hidden_gems"] + k["top_activities"]
        eve_pool = k["free_evenings"] + k["paid_evenings"]
        hotels = [dict(h, cost=season_price(h["cost"], month)) for h in k["hotels"]]
        block_start, ran_out, hop_days = day_no, False, 0

        for _ in range(n_days):
            ctx["rain"] = day_no in ctx["rainy"]
            hotel = pick_hotel(hotels, ctx, budget, town, warn)
            remaining = budget - hotel["cost"] - FOOD_ALLOWANCE

            # morning, then an afternoon within walking/short-hop range of it
            m_item, m_hop = pick(day_pool, used, remaining, ctx)
            if m_item:
                used.add(m_item["name"])
                remaining -= m_item.get("cost", 0) + m_hop
            a_item, a_hop = pick(day_pool, used, remaining, ctx, anchor=m_item)
            if a_item:
                used.add(a_item["name"])
                remaining -= a_item.get("cost", 0) + a_hop

            morning = make_slot(m_item, hotel, town, diet, False, m_hop, ctx)
            afternoon = make_slot(a_item, hotel, town, diet, False, a_hop, ctx)
            fallback, eve_anchor = None, a_item or m_item

            # nothing here today -> trip to the nearest hub instead of free time
            if m_item is None and a_item is None:
                hub = HUBS[key]
                hub_town = display(hub)
                mins, km = route_leg(key, hub)
                fare = fare_for(km)
                hub_pool = KB[hub]["hidden_gems"] + KB[hub]["top_activities"]
                if remaining < 2 * fare:
                    warn(f"Day {day_no}: the trip to {hub_town} costs ~R{2 * fare} return and pushes this day over budget "
                         f"- only free activities there were considered. Raise the budget or take a rest day.")
                h_item, _ = pick(hub_pool, used, remaining - 2 * fare, ctx)
                if h_item:
                    used.add(h_item["name"])
                    remaining -= 2 * fare + h_item.get("cost", 0)
                    why = "rain" if ctx["rain"] else "nothing new left here"
                    morning = {"name": f"Trip to {hub_town}", "cost": fare, "maps": maps_link(f"{hub_town} South Africa"),
                               "diet": None,
                               "text": (f"Not much on in {town} today ({why}) - head to {hub_town} (~{mins} min, ~R{fare}) "
                                        f"by {MODE_TEXT}")}
                    afternoon = make_slot(h_item, hotel, hub_town, diet, False, fare, ctx,
                                          suffix=" - includes the ride back; confirm the last one before you go")
                    fallback = {"type": "hub_trip", "hub": hub_town, "minutes_each_way": mins,
                                "fare_each_way": f"R{fare}", "reason": why, "estimate": True}
                    eve_anchor = None
                    hop_days += 1

            e_item, _ = pick(eve_pool, used, remaining, ctx, is_meal=True, repeatable=is_self_cook,
                             anchor=eve_anchor, max_km=WALK_KM)
            if e_item:
                used.add(e_item["name"])
            evening = make_slot(e_item, hotel, town, diet, True, 0, ctx)

            if fallback is None and (m_item is None or a_item is None):
                ran_out = True
                if ctx["rain"] and m_item is None and a_item is None:
                    warn(f"Day {day_no} (rain): no covered/indoor option within budget in {town} or {display(HUBS[key])}. "
                         f"Rest day, or raise the budget for a market/indoor trip.")

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
            elif e_item is None:
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
            if ctx["season"] == "winter":
                safety += " - Winter: dark by ~17:30, be back at the hostel before then."

            getting_here = None
            if day_no == block_start and prev:
                mins, km = route_leg(prev, key)
                getting_here = (f"Travel day {display(prev)} -> {town}: ~{mins} min, ~{km} km via the N2. "
                                f"Use the Baz Bus (hostel to hostel, book ahead), a hostel lift or a shared minibus taxi. "
                                f"Estimates - confirm times.")

            plan.append({
                "day": day_no, "town": town, "town_verified": town,
                "weather_mode": "rain" if ctx["rain"] else None,
                "getting_here": getting_here,
                "fallback": fallback,
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

        if hop_days >= 2:
            warn(f"{town}: {hop_days} day(s) need a trip to {display(HUBS[key])}. Consider spending fewer nights in {town} "
                 f"or basing in {display(HUBS[key])}.")
        if ran_out:
            warn(f"{town}: still some free-time slots after the hub fallback. Consider fewer days here.")
        prev = key

    if diet and unverified_days:
        d = ", ".join(str(x) for x in unverified_days)
        warn(f"Day(s) {d}: evening isn't verified {diet}. Self-cater or check with the venue.")

    min_daily = max(base_costs)
    if budget_max is not None and min_daily > budget_max:
        warn(f"Budget R{budget_max}/day is below the cheapest workable plan (about R{min_daily}/day: "
             f"dorm + R{FOOD_ALLOWANCE} groceries). Raise the budget to R{min_daily}+, shorten the trip, or look for cheaper beds.")

    days_over = sum(1 for d in plan if budget_max is not None and d["_totals"][2] > budget_max)
    return plan, towns, min_daily, days_over
