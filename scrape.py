"""Pull every eatery, course, item and nutrition label from Cornell's NetNutrition.

Usage: python3 scrape.py            -> writes data.json next to this file
"""
import html as htmllib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
from pathlib import Path

BASE = "https://netnutrition.dining.cornell.edu/NetNutrition/1"
OUT = Path(__file__).with_name("data.json")
# Cornell Dining's live feed (the one behind now.dining.cornell.edu): hours and what each
# eatery sells, by category. Used to check NetNutrition against and to show open/closed.
LIVE_URL = "https://admin-now.dining.cornell.edu/api/1.0/dining/eateries.json"
LIVE_OUT = Path(__file__).with_name("live.json")


class Session:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.opener.addheaders = [("User-Agent", "Mozilla/5.0 (cornell-nutrition redesign)")]
        self.get(BASE)

    def get(self, url):
        return self.opener.open(url, timeout=30).read().decode("utf-8", "replace")

    def post(self, path, **data):
        body = urllib.parse.urlencode(data).encode()
        for attempt in range(3):
            try:
                raw = self.opener.open(f"{BASE}/{path}", body, timeout=30).read().decode("utf-8", "replace")
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        try:
            return {p["id"]: p["html"] for p in json.loads(raw).get("panels", []) if p.get("html")}
        except ValueError:
            return raw


def text(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def find_calls(html, fn):
    """Return [(oid, label)] for anchors whose onclick calls NetNutrition.UI.<fn>(oid)."""
    pat = rf"{fn}\((\d+)\);?\"?'?[^>]*>(.*?)</a>"
    return [(int(o), text(l)) for o, l in re.findall(pat, html, re.S)]


def parse_items(html):
    items = []
    for row in re.findall(r"<tr\s+data-categoryid=.*?</tr>", html, re.S):
        m = re.search(r"getItemNutritionLabelOnClick\(event,(\d+)\)", row)
        if not m:
            continue
        a = re.search(r"class='cbo_nn_itemHover'>(.*?)</a>", row, re.S)
        tds = re.findall(r"<td class='align-middle'>(.*?)</td>", row, re.S)
        traits = re.findall(r"alt='([^']+)'", a.group(1)) if a else []
        items.append({
            "id": int(m.group(1)),
            "name": text(re.sub(r"<img[^>]*>", "", a.group(1))) if a else "",
            "serving": text(tds[0]) if tds else "",
            "traits": traits,
        })
    return items


NUM = r"&nbsp;([\d.]+)\s*(m?g)"


def parse_label(html):
    t = text(html)
    lab = {}
    m = re.search(r"Serving Size:\s*(.*?)\s*Amount Per Serving", t)
    lab["servingSize"] = m.group(1) if m else ""
    m = re.search(r"Calories\s+([\d.]+)", t)
    lab["calories"] = float(m.group(1)) if m else None
    fields = {
        "fat": "Total Fat", "satFat": "Saturated Fat", "transFat": "Trans Fat",
        "cholesterol": "Cholesterol", "sodium": "Sodium", "potassium": "Potassium",
        "carbs": "Total Carbohydrate", "fiber": "Dietary Fiber", "sugars": "Sugars",
        "addedSugars": "Added Sugars", "protein": "Protein",
    }
    for key, name in fields.items():
        m = re.search(rf"(?<![A-Za-z]){name}\s+([\d.]+)\s*(m?g)", t)
        if m:
            lab[key] = float(m.group(1))
    m = re.search(r"Ingredients:\s*(.*?)\s*(Contains:|$)", t)
    lab["ingredients"] = m.group(1).strip() if m else ""
    m = re.search(r"Contains:\s*(.*?)\s*$", t)
    lab["allergens"] = [a.strip() for a in m.group(1).split(",") if a.strip()] if m else []
    return lab


def walk_unit(s, unit_name, panels, seen_menus, out_courses, depth=0):
    """Follow whatever the unit returns (child units, menus, or courses) down to courses."""
    if not isinstance(panels, dict) or depth > 4:
        return
    if "coursesPanel" in panels:
        for oid, name in find_calls(panels["coursesPanel"], "selectCourse"):
            out_courses.append((oid, name))
    if "menuPanel" in panels:
        for oid, name in find_calls(panels["menuPanel"], "menuListSelectMenu"):
            if oid in seen_menus:
                continue
            seen_menus.add(oid)
            walk_unit(s, unit_name, s.post("Menu/SelectMenu", menuOid=oid), seen_menus, out_courses, depth + 1)
    if "childUnitsPanel" in panels:
        for oid, name in find_calls(panels["childUnitsPanel"], "childUnitsSelectUnit"):
            walk_unit(s, unit_name, s.post("Unit/SelectUnitFromChildUnitsList", unitOid=oid), seen_menus, out_courses, depth + 1)
    if "itemPanel" in panels and "getItemNutritionLabelOnClick" in panels["itemPanel"]:
        out_courses.append((None, "Menu", panels["itemPanel"]))


def main():
    s = Session()
    home = s.get(BASE)
    units = []
    seen = set()
    for oid, name in find_calls(home, "unitTreeSelectUnit"):
        if oid not in seen:
            seen.add(oid)
            units.append((oid, name))
    print(f"{len(units)} eateries", file=sys.stderr)

    # Labels only resolve for items in the session's currently selected unit, so each
    # eatery gets its own session and fetches its labels before moving on.
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(lambda u: scrape_unit(*u), units))

    data = {"scrapedAt": time.strftime("%Y-%m-%d"), "eateries": [], "items": {}}
    for eatery, items in results:
        if eatery["courses"]:
            data["eateries"].append(eatery)
        for i in items:
            data["items"].setdefault(str(i["id"]), i)
    missing = sum(1 for i in data["items"].values() if i.get("calories") is None)
    print(f"{len(data['items'])} items, {missing} without a label", file=sys.stderr)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    LIVE_OUT.write_text(Session().get(LIVE_URL))
    fetch_events()
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)", file=sys.stderr)


def scrape_unit(uoid, uname):
    s = Session()
    all_items = {}
    courses = []
    walk_unit(s, uname, s.post("Unit/SelectUnitFromTree", unitOid=uoid), set(), courses)
    eatery = {"id": uoid, "name": uname, "courses": []}
    seen_courses = set()
    for c in courses:
        if c[0] is None:
            items = parse_items(c[2])
            cname = c[1]
        else:
            if c[0] in seen_courses:
                continue
            seen_courses.add(c[0])
            panels = s.post("Menu/SelectCourse", oid=c[0])
            items = parse_items(panels.get("itemPanel", "")) if isinstance(panels, dict) else []
            cname = c[1]
        if items:
            eatery["courses"].append({"name": cname, "items": [i["id"] for i in items]})
            for i in items:
                all_items.setdefault(i["id"], i)
    s.post("Unit/SelectUnitFromTree", unitOid=uoid)
    for item in all_items.values():
        raw = s.post("NutritionDetail/ShowItemNutritionLabel", detailOid=item["id"])
        item.update(parse_label(raw if isinstance(raw, str) else ""))
    print(f"  {uname}: {len(eatery['courses'])} courses, {len(all_items)} items", file=sys.stderr)
    return eatery, list(all_items.values())


EVENTS_OUT = Path(__file__).with_name("events.json")
EVENTS_API = "https://events.cornell.edu/api/2/events/search"
FOODISH = re.compile(r"\b(dining|dinner|lunch|brunch|cuisine|food|nutrition|tasting|chef|feast|takeout|bake|cooking|harvest)\b", re.I)


def fetch_events():
    """Food and dining events from Cornell's events calendar for the next three weeks."""
    # Only dining halls count as a venue on their own; cafés also host meetings and talks.
    # A dining hall is named by its first two words ("north star", "rose house") or its
    # one distinctive word ("okenshields"); "cornell"/"college" alone would match half of campus.
    keys = set()
    halls = [e for e in json.loads(LIVE_OUT.read_text())["data"]["eateries"] if not e.get("diningItems")]
    for n in (e["name"] for e in halls):
        words = n.lower().split()
        keys.add(" ".join(words[:2]) if len(words) > 1 and words[0] not in ("cornell", "college") else words[-1] if words[0] in ("cornell", "college") else words[0])
    at_dining = lambda loc: any(k in (loc or "").lower() for k in keys)
    found = {}
    for q in ["dining", "Cornell Dining", "food", "nutrition", "cuisine", "dinner"]:
        url = f"{EVENTS_API}?" + urllib.parse.urlencode({"search": q, "days": 21, "pp": 100})
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
        except Exception as ex:
            print(f"  events search '{q}' failed: {ex}", file=sys.stderr)
            continue
        for x in json.loads(raw).get("events", []):
            e = x["event"]
            # Food events only: held at a dining location, or a food word in the title
            # (but not talks and competitions that merely mention food).
            if not (at_dining(e.get("location_name")) or (FOODISH.search(e["title"]) and not re.search(r"seminar|lecture|hackathon|course", e["title"], re.I))):
                continue
            inst = e["event_instances"][0]["event_instance"]
            found.setdefault(e["id"], {
                "title": e["title"].strip(), "start": inst["start"], "end": inst.get("end"),
                "place": (e.get("location_name") or "").strip(), "url": e.get("localist_url"),
                "photo": photo_data_uri(e.get("photo_url")),
            })
    events = sorted(found.values(), key=lambda v: v["start"])
    EVENTS_OUT.write_text(json.dumps(events))
    print(f"{len(events)} food events", file=sys.stderr)


def photo_data_uri(url):
    """Download an event photo, shrink it to 480px wide, and return it as a data URI."""
    if not url:
        return None
    import base64, subprocess, tempfile
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d, "in.jpg"), Path(d, "out.jpg")
            src.write_bytes(raw)
            ok = subprocess.run(["sips", "-Z", "480", "-s", "format", "jpeg", "-s", "formatOptions", "70", str(src), "--out", str(dst)],
                                capture_output=True).returncode == 0
            data = dst.read_bytes() if ok else raw
        return "data:image/jpeg;base64," + base64.b64encode(data).decode()
    except Exception:
        return None


if __name__ == "__main__":
    if sys.argv[1:] == ["events"]:
        fetch_events()
    else:
        main()
