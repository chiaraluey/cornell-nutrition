# Cornell Nutrition

An unofficial, faster way to browse Cornell Dining menus and nutrition: search any food on campus, filter by what you're in the mood for, see what's open now, and customize items (leave off the cheese, see the new numbers).

Live: https://chiaraluey.github.io/cornell-nutrition/ · Promo: https://chiaraluey.github.io/cornell-nutrition/promo.html

## Data sources

- [NetNutrition](https://netnutrition.dining.cornell.edu/NetNutrition/1): eateries, menus, nutrition labels, ingredients, allergens
- [Cornell Dining live feed](https://admin-now.dining.cornell.edu/api/1.0/dining/eateries.json): hours and open/closed
- [Cornell events calendar](https://events.cornell.edu): food events at dining locations
- [Cornell Dairy flavors](https://cals.cornell.edu/cornell-dairy/products/ice-cream-flavors): ice cream labels (transcribed in `dairy.json`)

## Build locally

Python 3.10+, no dependencies.

```sh
python3 scrape.py   # writes data.json, live.json, events.json (~2 min)
python3 build.py    # injects the data into app.html -> index.html
python3 -m http.server   # open http://localhost:8000
```

`app.html` is the whole front end (HTML, CSS, JS in one file). `build.py` also estimates per-ingredient nutrition so items can be customized; estimates are marked in the UI.

## Deploy

`.github/workflows/deploy.yml` re-scrapes and deploys to GitHub Pages on every push to `main` and twice a day (6am and noon Eastern). If a scrape fails, the previous deploy stays live.
