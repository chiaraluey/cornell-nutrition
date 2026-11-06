"""Turn data.json into the finished site (index.html).

Adds a "parts" list to each item: the ingredients you can leave off, with nutrition for
each. A part's numbers come from Cornell's own label when that ingredient is also sold
as its own item (e.g. a cheese slice); otherwise from typical per-portion values below,
and the app marks those as estimates.
"""
import base64
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
KEYS = ["calories", "fat", "satFat", "carbs", "fiber", "sugars", "protein", "sodium", "cholesterol"]


def n(cal, fat=0, sat=0, carb=0, fib=0, sug=0, prot=0, na=0, chol=0):
    return dict(zip(KEYS, [cal, fat, sat, carb, fib, sug, prot, na, chol]))


# (pattern on the ingredient name, display label, typical amount used in one dish).
# First match wins, so specific patterns come before general ones.
TYPICAL = [
    (r"cream cheese", "Cream cheese", n(100, 10, 6, 1, 0, 1, 2, 90, 30)),
    (r"shredded.*cheese|cheese.*shredded|parmesan|feta|mozzarella|queso", "Cheese", n(110, 9, 5.5, 1, 0, 0, 7, 180, 27)),
    (r"cheese", "Cheese", n(80, 6.5, 4, 0.5, 0, 0, 5, 140, 20)),
    (r"bacon", "Bacon", n(80, 6, 2, 0, 0, 0, 6, 280, 15)),
    (r"mayo|aioli", "Mayo", n(100, 11, 1.5, 0, 0, 0, 0, 90, 5)),
    (r"ranch|caesar|blue cheese dressing", "Creamy dressing", n(130, 13, 2, 2, 0, 1, 0, 260, 5)),
    (r"vinaigrette|dressing", "Dressing", n(90, 9, 1, 3, 0, 2, 0, 220, 0)),
    (r"pesto", "Pesto", n(160, 16, 3, 2, 0, 0, 2, 220, 5)),
    (r"guacamole", "Guacamole", n(50, 4.5, 0.5, 3, 2, 0, 1, 115, 0)),
    (r"avocado", "Avocado", n(80, 7.5, 1, 4, 3.5, 0, 1, 3, 0)),
    (r"egg white", "Egg white", n(25, 0, 0, 0, 0, 0, 5, 80, 0)),
    (r"just egg|vegan egg", "Plant-based egg", n(70, 5, 0.5, 1, 0, 0, 5, 160, 0)),
    (r"\begg", "Egg", n(90, 6, 2, 0.5, 0, 0, 6.5, 70, 185)),
    (r"\bham\b", "Ham", n(60, 2, 0.5, 1, 0, 1, 10, 600, 30)),
    (r"turkey", "Turkey", n(60, 1, 0, 2, 0, 1, 11, 500, 25)),
    (r"salami|pepperoni", "Salami", n(110, 9, 3.5, 0, 0, 0, 6, 450, 25)),
    (r"sausage", "Sausage", n(170, 15, 5, 1, 0, 0, 8, 380, 40)),
    (r"chicken", "Chicken", n(140, 3, 1, 0, 0, 0, 26, 300, 70)),
    (r"beef|burger patty", "Beef", n(230, 15, 6, 0, 0, 0, 22, 70, 75)),
    (r"tofu", "Tofu", n(80, 4.5, 0.5, 2, 1, 0, 8, 10, 0)),
    (r"hummus", "Hummus", n(70, 5, 0.5, 4, 1, 0, 2, 130, 0)),
    (r"butter(?!milk)", "Butter", n(100, 11.5, 7, 0, 0, 0, 0, 90, 30)),
    (r"sour cream", "Sour cream", n(60, 6, 3.5, 1, 0, 1, 1, 15, 20)),
    (r"tortilla|wrap", "Tortilla", n(300, 8, 3.5, 50, 2, 1, 8, 600, 0)),
    (r"english muffin", "English muffin", n(130, 1, 0, 26, 1.5, 2, 5, 250, 0)),
    (r"bagel", "Bagel", n(280, 1.5, 0, 56, 2, 5, 11, 450, 0)),
    (r"croissant", "Croissant", n(230, 12, 7, 26, 1, 6, 5, 260, 40)),
    (r"bread|bun\b|roll\b|panini|ciabatta|focaccia|baguette|pita|naan", "Bread", n(160, 2, 0.5, 30, 2, 3, 6, 300, 0)),
    (r"brown rice", "Brown rice", n(215, 1.5, 0.5, 45, 3.5, 0, 5, 10, 0)),
    (r"rice", "Rice", n(200, 0.5, 0, 45, 0.5, 0, 4, 5, 0)),
    (r"quinoa", "Quinoa", n(110, 2, 0, 20, 2.5, 0, 4, 5, 0)),
    (r"noodle|pasta|spaghetti|penne|ramen|udon", "Noodles", n(200, 1, 0, 42, 2, 1, 7, 5, 0)),
    (r"black beans|garbanzo|chickpea|kidney bean|pinto|lentil|beans", "Beans", n(110, 0.5, 0, 20, 6, 0, 7, 200, 0)),
    (r"granola", "Granola", n(140, 5, 1, 21, 2, 8, 3, 30, 0)),
    (r"peanut butter|almond butter", "Nut butter", n(190, 16, 3, 7, 2, 3, 7, 140, 0)),
    (r"crouton", "Croutons", n(30, 1, 0, 5, 0, 0, 1, 70, 0)),
    (r"tortilla chip|chips", "Chips", n(140, 7, 1, 18, 1, 0, 2, 120, 0)),
    (r"honey", "Honey", n(60, 0, 0, 17, 0, 17, 0, 0, 0)),
    (r"maple|syrup", "Syrup", n(50, 0, 0, 13, 0, 12, 0, 0, 0)),
    (r"bbq|barbecue|teriyaki|sweet chili|hoisin", "Sweet sauce", n(60, 0, 0, 14, 0, 12, 0, 330, 0)),
    (r"ketchup", "Ketchup", n(20, 0, 0, 5, 0, 4, 0, 160, 0)),
    (r"buffalo|hot sauce|sriracha", "Hot sauce", n(5, 0, 0, 1, 0, 0, 0, 200, 0)),
    (r"mustard", "Mustard", n(5, 0, 0, 0, 0, 0, 0, 60, 0)),
    (r"salsa|pico", "Salsa", n(10, 0, 0, 2, 0.5, 1, 0, 150, 0)),
    (r"olive(?! oil)|olives", "Olives", n(25, 2.5, 0, 1, 0.5, 0, 0, 200, 0)),
    (r"pickle", "Pickles", n(5, 0, 0, 1, 0.5, 0, 0, 280, 0)),
    (r"pepitas|sunflower seed|almond|walnut|pecan|cashew|peanut", "Nuts & seeds", n(50, 4.5, 0.5, 1.5, 0.5, 0, 2, 20, 0)),
    (r"lettuce|spinach|arugula|greens|kale|romaine|spring mix", "Greens", n(5, 0, 0, 1, 0.5, 0, 0.5, 10, 0)),
    (r"tomato(?!.*sauce)(?!.*paste)", "Tomato", n(5, 0, 0, 1, 0.5, 1, 0, 2, 0)),
    (r"\bonion", "Onion", n(5, 0, 0, 1, 0, 0.5, 0, 0, 0)),
    (r"cucumber", "Cucumber", n(3, 0, 0, 0.5, 0, 0.5, 0, 0, 0)),
    (r"banana", "Banana", n(105, 0.5, 0, 27, 3, 14, 1, 1, 0)),
    (r"strawberr|blueberr|raspberr|berries", "Berries", n(25, 0, 0, 6, 1.5, 4, 0.5, 0, 0)),
    (r"chocolate chip|chocolate chunk", "Chocolate chips", n(70, 4, 2.5, 9, 1, 8, 1, 0, 0)),
]

# Anything matching these is seasoning or process, not something you'd ask to leave off.
SKIP = re.compile(
    r"^(water|kosher salt|salt|sea salt|black pepper|.*pepper flakes|ground .*pepper|garlic( powder)?|granulated .*|"
    r".*spray|.*oil|.*vinegar|cumin|.*paprika|oregano|.*powder|lemon juice|lime juice|sugar|granulated sugar|"
    r"enzymes|cheese culture|yeast|.*gum|corn ?starch|ascorbic acid|calcium chloride|.*spice|.*seasoning|"
    r"fresh (cilantro|flat leaf parsley|parsley|basil|dill|mint|thyme|rosemary)|dried .*|ginger|cinnamon|vanilla.*|"
    r"sesame seed|.*extract|baking .*|pasteurized milk|enriched .*flour|soy sauce|.*tamari.*)$"
)


# Cornell doesn't publish drinks, so these are typical values (USDA milk, standard café
# recipes, and the brands' own labels for bottled drinks). The app marks them as such.
# Café drinks: "base" is the non-milk part of a 16 oz drink; "milkOz" is how much milk
# a 16 oz drink holds; the app scales both by cup size and swaps the milk.
MILKS = {  # per 8 fl oz
    "None": n(0),
    "Whole": n(150, 8, 4.5, 12, 0, 12, 8, 105, 24),
    "2%": n(120, 5, 3, 12, 0, 12, 8, 115, 20),
    "Skim": n(90, 0, 0, 12, 0, 12, 8, 130, 5),
    "Oat": n(120, 5, 0.5, 16, 2, 7, 3, 100, 0),
    "Almond": n(40, 3, 0, 1, 0.5, 0, 1, 170, 0),
    "Soy": n(110, 4.5, 0.5, 9, 1, 6, 8, 90, 0),
}
MILK_ALLERGEN = {"Whole": "Milk", "2%": "Milk", "Skim": "Milk", "Almond": "Tree Nuts", "Soy": "Soy"}
SYRUP = n(20, 0, 0, 5, 0, 5)  # one pump
WHIP = n(80, 7, 4.5, 2, 0, 2, 0, 10, 25)

# Feed items that mean "this café has a coffee bar".
COFFEE = ["La Colombe Coffee", "Peet's Coffee", "Finger Lakes Specialty Coffees", "Copper Horse Coffee",
          "Coffee (Hot)", "Javiva", "Sun Coffee Roasters coffee", "96oz Coffee2Go"]
TEA = ["Bigelow Tea", "Mighty Leaf Tea"]

# Only drinks Cornell's live feed shows being sold. "where" lists the feed items that
# prove it; "exact" is False when the feed names the coffee bar but not the drink itself.
CAFE_DRINKS = [
    # course, name, base (16 oz), milk oz in 16 oz, default milk, allergens in base, where, exact
    ("Coffee & tea", "Brewed Coffee", n(5, 0, 0, 0, 0, 0, 0.5, 10), 2, "None", [], COFFEE, True),
    ("Coffee & tea", "Hot Tea", n(0), 2, "None", [], TEA, True),
    ("Coffee & tea", "Hot Cocoa", n(100, 2, 1.5, 20, 1, 16, 2, 30), 13, "2%", ["Milk"], ["Hot Cocoa"], True),
    ("Coffee & tea", "Fruit Smoothie", n(270, 1, 0, 64, 3, 54, 3, 20), 0, "None", [], ["Smoothies"], True),
    ("Espresso drinks", "Latte", n(5, 0, 0, 1, 0, 0, 0.5, 5), 13, "2%", [], COFFEE, False),
    ("Espresso drinks", "Iced Latte", n(5, 0, 0, 1, 0, 0, 0.5, 5), 10, "2%", [], COFFEE, False),
    ("Espresso drinks", "Cappuccino", n(5, 0, 0, 1, 0, 0, 0.5, 5), 8, "2%", [], COFFEE, False),
    ("Espresso drinks", "Mocha", n(80, 1.5, 1, 16, 1, 12, 2, 10), 11, "2%", ["Milk"], COFFEE, False),
    ("Espresso drinks", "Chai Latte", n(120, 0, 0, 30, 0, 28, 0, 10), 8, "2%", [], COFFEE, False),
    # Cornell's feed doesn't list matcha anywhere, so this names where the Daily Sun found it.
    ("Espresso drinks", "Matcha Latte", n(80, 0, 0, 19, 1, 17, 1, 5), 13, "2%", [],
     {"names": ["Café Jennie"], "note": "Cornell doesn't list matcha on any café menu. The Daily Sun ranked Café Jennie's matcha latte among the best on campus (2019), so ask at the counter."}, False),
]
FIXED_DRINKS = [
    # course, name, size, nutrition, allergens, where
    ("Coffee & tea", "Frappuccino", "16 fl oz", n(230, 3, 2, 46, 0, 45, 3, 220, 10), ["Milk"], ["Frappuccino"]),
    ("Coffee & tea", "Bubble Tea", "16 fl oz", n(300, 6, 5, 60, 0, 38, 2, 60, 5), ["Milk"], ["Bubble Tea"]),
    # "Pepsi Beverages": Cornell's soft-drink contract is with Pepsi; these are its core lineup.
    ("Pepsi bottles", "Pepsi", "20 fl oz bottle", n(250, 0, 0, 69, 0, 69, 0, 55), [], ["Pepsi Beverages"]),
    ("Pepsi bottles", "Diet Pepsi", "20 fl oz bottle", n(0, 0, 0, 0, 0, 0, 0, 60), [], ["Pepsi Beverages"]),
    ("Pepsi bottles", "Mountain Dew", "20 fl oz bottle", n(290, 0, 0, 77, 0, 77, 0, 105), [], ["Pepsi Beverages"]),
    ("Pepsi bottles", "Gatorade", "20 fl oz bottle", n(140, 0, 0, 36, 0, 34, 0, 270), [], ["Pepsi Beverages"]),
    ("Pepsi bottles", "Aquafina Water", "20 fl oz bottle", n(0), [], ["Pepsi Beverages"]),
    ("Pepsi bottles", "bubly Sparkling Water", "12 fl oz can", n(0), [], ["Pepsi Beverages"]),
]


def sellers(live, feed_items):
    return sorted({e["name"] for e in live for i in (e.get("diningItems") or []) if i["item"] in feed_items})


def add_drinks(data, live):
    items, courses, oid = data["items"], {}, 900000
    for course, name, base_n, milk_oz, milk, allergens, where, exact in CAFE_DRINKS:
        oid += 1
        total = {k: base_n[k] + MILKS[milk][k] * milk_oz / 8 for k in KEYS}
        items[str(oid)] = {
            "id": oid, "name": name, "serving": "16 fl oz", "servingSize": "16 fl oz",
            "traits": [], "parts": [], "ingredients": "", "allergens": sorted(set(allergens + ([MILK_ALLERGEN[milk]] if milk in MILK_ALLERGEN else []))),
            "typical": True, "where": where["names"] if isinstance(where, dict) else sellers(live, where), "whereExact": exact,
            **({"whereNote": where["note"]} if isinstance(where, dict) else {}),
            "drink": {"base": base_n, "milkOz": milk_oz, "milk": milk, "allergens": allergens},
            **{k: round(v, 1) for k, v in total.items()},
        }
        courses.setdefault(course, []).append(oid)
    for course, name, size, nut, allergens, where in FIXED_DRINKS:
        oid += 1
        items[str(oid)] = {"id": oid, "name": name, "serving": size, "servingSize": size, "traits": [],
                           "parts": [], "ingredients": "", "allergens": allergens, "typical": True,
                           "where": sellers(live, where), "whereExact": True, **nut}
        courses.setdefault(course, []).append(oid)
    data["eateries"].append({"id": 9000, "name": "Drinks", "typical": True, "kind": "drinks",
                             "courses": [{"name": c, "items": ids} for c, ids in courses.items()]})
    data["drinkOptions"] = {"milks": MILKS, "milkAllergen": MILK_ALLERGEN, "syrup": SYRUP, "whip": WHIP}


# NetNutrition name -> live feed name. Units missing here aren't places you can walk into;
# they're product lines (baked goods, grab-and-go meals) sold at several cafés.
LIVE_NAMES = {
    "Cafe Jennie": "Café Jennie", "Bus Stop Bagels": "Bus Stop Bagels", "Mann Cafe": "Mann Café",
    "Goldie's Cafe": "Goldie's Café", "Mattin's": "Mattin's Café", "Atrium Cafe": "Atrium Café",
    "Trillium": "Trillium", "Dairy Bar": "Cornell Dairy Bar", "Big Red Barn": "Big Red Barn",
    "Crossings Cafe": "Crossings Café", "Martha's": "Martha's Café",
    "College of Veterinary Medicine Cafe": "College of Veterinary Medicine Café",
    "Straight From The Market": "Straight from the Market",
}


def attach_live(data, live):
    by_name = {e["name"]: e for e in live}
    for e in data["eateries"]:
        src = by_name.get(LIVE_NAMES.get(e["name"], ""))
        if not src:
            e["kind"] = "line"
            continue
        e["kind"] = "place"
        e["live"] = {
            "name": src["name"],
            "area": (src.get("campusArea") or {}).get("descrshort", ""),
            "location": src.get("location", ""),
            "lat": src.get("latitude"), "lng": src.get("longitude"),
            "hours": [[ev["startTimestamp"], ev["endTimestamp"]] for day in src.get("operatingHours", [])
                      for ev in day.get("events", []) if ev.get("startTimestamp")],
            "sells": [i["item"] for i in (src.get("diningItems") or []) if i["category"] not in ("Coffee Bar", "Beverages")],
        }


# Cornell doesn't publish sales numbers, so "fan favorites" are only items a named source calls
# a top seller or a standout, and only when the item is on today's menu.
FAVORITES = [
    ("Dairy Bar", r"^Bavarian Raspberry Fudge$", "Cornell Dairy calls it a top seller",
     "https://cals.cornell.edu/cornell-dairy/products/ice-cream-flavors"),
    ("Bus Stop Bagels", r"^Route 81 .*Egg & Cheese$", "The Daily Sun says many people love these egg sandwiches (2023)",
     "https://www.cornellsun.com/article/2023/04/top-5-hidden-gems-of-cornell-dining"),
    ("Goldie's Cafe", r"^Spicy BLT Sandwich$", "Named a best food on campus in a Daily Sun survey (2017)",
     "https://www.cornellsun.com/article/2017/11/food-week-what-is-the-best-food-item-at-cornell"),
]


def mark_favorites(data):
    for place, pat, why, url in FAVORITES:
        e = next((e for e in data["eateries"] if e["name"] == place), None)
        for iid in (i for c in (e["courses"] if e else []) for i in c["items"]):
            it = data["items"][str(iid)]
            if re.search(pat, it["name"]):
                it["fav"] = {"why": why, "url": url}


def add_dairy(data):
    """Cornell Dairy ice cream, sold at the Dairy Bar. NetNutrition doesn't list it, so these come
    from the nutrition labels on Cornell Dairy's flavors page (transcribed into dairy.json)."""
    f = HERE / "dairy.json"
    if not f.exists():
        return
    dairy = json.loads(f.read_text())
    bar = next((e for e in data["eateries"] if e["name"] == "Dairy Bar"), None)
    if not bar:
        return
    ids = []
    for n, fl in enumerate(dairy["flavors"], 950001):
        data["items"][str(n)] = {
            "id": n, "name": fl["name"], "serving": "2/3 cup", "servingSize": fl["servingSize"], "traits": [], "parts": [],
            "ingredients": fl["ingredients"], "allergens": fl["allergens"], "source": "dairy", "seasonal": fl["seasonal"],
            "desc": fl["desc"], "labelNote": fl["labelNote"], "addedSugars": fl["addedSugars"],
            **{k: fl[k] for k in KEYS},
        }
        ids.append(n)
    bar["courses"].insert(0, {"name": "Cornell Ice Cream", "items": ids})
    data["dairySource"] = dairy["source"]


def split_top(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def base(c):
    return re.sub(r"\s+", " ", re.sub(r"[(\[].*", "", c)).strip().lower()


def main():
    data = json.loads((HERE / "data.json").read_text())
    items = data["items"]

    # Items whose ingredient list is a single thing: their label tells us what that thing costs.
    single = {}
    for k, it in items.items():
        parts = split_top(it.get("ingredients", ""))
        if len(parts) == 1 and it.get("calories") is not None:
            single.setdefault(base(parts[0]), k)

    for k, it in items.items():
        it["traits"] = [t.replace(" image", "") for t in it.get("traits", [])]
        parts = split_top(it.get("ingredients", ""))
        if it.get("calories") is None or len(parts) < 2:
            it["parts"] = []
            continue
        found, labels = [], set()
        for raw in parts:
            b = base(raw)
            if not b or SKIP.match(b):
                continue
            # One-word names ("carrot", "onion") match salad-bar portions far bigger than
            # what goes in a dish, so only trust specific names ("sliced yellow cheddar cheese").
            match = single.get(b) if " " in b else None
            if match and match != k:
                src = items[match]
                part = {"label": src["name"], "src": "cornell", "of": src.get("servingSize") or src.get("serving"),
                        "n": {key: src.get(key) or 0 for key in KEYS}}
            else:
                hit = next(((lab, nut) for pat, lab, nut in TYPICAL if re.search(pat, b)), None)
                if not hit:
                    continue
                part = {"label": hit[0], "src": "typical", "n": dict(hit[1])}
            # A part can't be most of the dish; if Cornell's standalone serving is bigger
            # than what's plausibly in here, scale it down.
            cap = 0.6 * it["calories"]
            if part["n"]["calories"] > cap > 0:
                f = cap / part["n"]["calories"]
                part["n"] = {key: round(v * f, 1) for key, v in part["n"].items()}
                part["scaled"] = True
            if part["label"] in labels:
                continue
            labels.add(part["label"])
            part["ingredient"] = re.sub(r"[(\[].*", "", raw).strip()
            found.append(part)
        it["parts"] = found

    data["eateries"] = [
        {**e, "courses": [c for c in e["courses"] if any(items[str(i)].get("calories") is not None for i in c["items"])]}
        for e in data["eateries"]
    ]
    live = json.loads((HERE / "live.json").read_text())["data"]["eateries"]
    attach_live(data, live)
    add_dairy(data)
    mark_favorites(data)
    # A plain "made with" list from the label's top-level ingredients, for names like "Route 81".
    for it in data["items"].values():
        if it.get("source") == "dairy" or not it.get("ingredients"):
            continue
        names = []
        for c in split_top(it["ingredients"]):
            b = base(c)
            if b and not SKIP.match(b) and b not in names and len(b) < 40:
                names.append(b)
        if len(names) >= 2:
            it["about"] = names[:6]
    events = HERE / "events.json"
    data["events"] = json.loads(events.read_text()) if events.exists() else []
    add_drinks(data, live)
    data["liveCheckedAt"] = data["scrapedAt"]
    # Eatery logos (logos/<eatery id>.png|jpg, saved from NetNutrition) ride along as data URIs.
    for e in data["eateries"]:
        for ext, mime in (("png", "image/png"), ("jpg", "image/jpeg")):
            f = HERE / "logos" / f"{e['id']}.{ext}"
            if f.exists():
                e["logo"] = f"data:{mime};base64,{base64.b64encode(f.read_bytes()).decode()}"
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = (HERE / "app.html").read_text().replace("/*__DATA__*/null", payload)
    (HERE / "index.html").write_text(page)
    with_parts = sum(1 for it in items.values() if it["parts"])
    print(f"index.html written; {with_parts} of {len(items)} items are customizable")


if __name__ == "__main__":
    main()
