# pcm-zces-parser

`pcm-zces-parser` reads and writes Pro Cycling Manager 26 `.zces` stage
files and turns them into things you can look at: an elevation profile, a
route map, a GeoJSON or GPX route on the real-world map, and a readable JSON
summary of the stage.

A `.zces` file holds a stage's 3D world: terrain, roads, fences, houses,
cities, vegetation, water, sprints and more. The matching `.cds` file holds
the game's race profile, which
[pcm-cds-profile](https://github.com/Strandfelt/pcm-cds-profile) reads.

The format was reverse engineered from the PCM 26 Stage Editor and is
described in [docs/FORMAT.md](docs/FORMAT.md); every class is listed in
[docs/classes.md](docs/classes.md). Tested on 3,367 workshop stages: all of
them convert to JSON and back to identical data.

## Install

```powershell
python -m pip install "git+https://github.com/Strandfelt/pcm-zces-parser.git"
```

Python 3.12 or later. No dependencies. To take elevation and race points from
the stage's `.cds` file (recommended), install the `cds` extra:

```powershell
python -m pip install "pcm-zces-parser[cds] @ git+https://github.com/Strandfelt/pcm-zces-parser.git"
```

## Command line

```powershell
pcm-zces export topclas_rondevv_2026.zces -o out
```

writes, next to each other:

| File | Contents |
|---|---|
| `STAGE.profile.svg` | Elevation profile coloured by gradient, with climbs, KOMs, sprints, start and finish labelled and cobbled/gravel sectors marked |
| `STAGE.map.svg` | Route map, north up, with the stage's other roads, climbs and sectors highlighted, race points and a scale bar |
| `STAGE.geojson` | The route, every climb and sector as lines and the race points, in real-world coordinates with elevation |
| `STAGE.gpx` | The route as a GPX track with waypoints, for gpx.studio, Garmin, Strava and the like |
| `STAGE.stage.json` | Everything above as readable JSON (see below) |
| `STAGE.html` | Interactive page: profile, map on OpenStreetMap and event list, linked on hover |

`--only profile-svg,geojson` picks formats, `--theme dark` switches the SVG
colours, `--no-cds` ignores the `.cds` file. `pcm-zces profile` and
`pcm-zces gpx [--format geojson]` are shortcuts for single formats.

Lossless conversion of the whole file:

```powershell
pcm-zces to-json c0_almeria_2020.zces            # writes c0_almeria_2020.json
pcm-zces from-json c0_almeria_2020.json -o out   # writes out\c0_almeria_2020.zces
pcm-zces info c0_almeria_2020.zces               # stage name, version, object counts
```

`from-json` reads its own output back before saving, so a broken edit fails
instead of producing a file the game cannot load. `python -m pcm_zces_parser`
works too.

## Library

```python
from pcm_zces_parser import export_stage, load_stage, map_svg, profile_svg, stage_report

view = load_stage("topclas_rondevv_2026.zces")   # uses the .cds next to it when available
print(view["name"], view["distance_km"], "km")

for climb in stage_report(view)["climbs"]:
    print(f'{climb["summit_km"]:6.1f} km  {climb["name"]}  {climb["avg_gradient_pct"]} %')

svg = profile_svg(view, width=1600, theme="dark")
export_stage(view, "out", formats=["map-svg", "geojson"])
```

| Function | Returns |
|---|---|
| `load_stage(path, cds="auto")` | Stage view: route samples, gradients, race points, climbs, sectors, roads |
| `stage_view(doc, cds=None)` | The same from an already decoded file and an optional `pcm_cds_profile.read_cds` result |
| `profile_svg(view, width=1200, plot_height=300, theme="light", title=True)` | SVG text |
| `map_svg(view, size=800, theme="light", roads=True, title=True)` | SVG text |
| `geojson(view)` / `geojson_text(view)` | GeoJSON dict / text |
| `gpx_text(view)` | GPX text |
| `stage_report(view)` / `stage_report_json(view)` | Readable summary dict / JSON text |
| `profile_html(view, source_name="", standalone=True)` | HTML page |
| `export_stage(view, out_dir, stem=None, formats=None, theme="light")` | `{format: path}` of the files written |
| `read_zces(path)`, `write_zces(doc, path)`, `to_json(doc)`, `from_json(text)` | Lossless access to every object in the file |
| `gps_transform(doc)` | Function `(x, y) -> (lat, lon)` for game coordinates, or `None` |

A stage view's `samples` are rows of `[km, altitude_m, x, y, lat, lon]`
every 200 m (`lat`/`lon` only when the stage has a location), and `events`
lists the race points, climbs and sectors with their km.

## The stage JSON

```json
{
  "format": "pcm-zces-stage-report",
  "stage": {"name": "Antwerpen - Oudenaarde", "region": "Belgium - Flanders", "distance_km": 271.89,
            "climbing_m": 2038, "highest_point_m": 149.4, "cobbles_km": 17.11,
            "location": {"start": {"lat": 51.2123, "lon": 4.378317}, "finish": {...}, "bounds": {...}}, ...},
  "race_points": [{"type": "start", "name": "Antwerpen", "km": 0.0, "altitude_m": 7.2, "lat": 51.2123, "lon": 4.378317}, ...],
  "climbs": [{"name": "Oude Kwaremont", "start_km": 137.07, "summit_km": 138.79, "length_km": 1.72,
              "avg_gradient_pct": 5.6, "max_gradient_pct": 10.0, "kom_category_code": null,
              "summit": {"altitude_m": 119.8, "lat": 50.77124, "lon": 3.531038}}, ...],
  "sectors": [{"type": "cobbles", "name": "Paterberg", "start_km": 219.56, "end_km": 220.13,
               "length_km": 0.57, "difficulty_stars": 3, "start": {...}, "end": {...}}, ...],
  "profile": [{"km": 0.04, "altitude_m": 7.2, "gradient_pct": 0.1, "lat": 51.2123, "lon": 4.378317}, ...]
}
```

Distances are km from the start line and heights metres, converted from game
units (distance ×10, height ×7.5). The file's `units` block explains each
field.

## Where the numbers come from

* **Route.** The route's waypoints are road points; between two waypoints the
  race follows the road they share, built from its cubic Bézier curves.
  Circuits are repeated for their number of laps.
* **Elevation and race points.** With the `.cds` file, the elevation, start,
  finish, sprints and KOMs are the game's own, and the route is matched to
  that profile by elevation. 97% of the stages tested match exactly; the rest
  keep the game's elevation with approximate map positions. Without the
  `.cds` file the elevation comes from the road geometry.
* **Climbs and sectors** come from the `.zces` file: climbs with average and
  maximum gradient, cobbled sectors rated 1–5 stars and gravel sectors 1–3.
* **Real-world position.** The editor builds the terrain from real elevation
  data over the stage's GPS box, so a stage is the real area at 1:10 scale and
  converts to latitude and longitude linearly. Positions are as accurate as the
  stage's own roads; well-built stages land within a few hundred metres. About
  6% of the stages tested were built without real terrain and have no
  location, so GeoJSON and GPX are skipped for them.

## The lossless JSON

`to-json` writes every object of the file:

```json
{
  "format": "pcm-zces",
  "format_version": 1,
  "archive_version": 115,
  "flag": 1,
  "roots": [1],
  "objects": [
    {"id": 1, "class": "CTStage", "class_version": 0, "landscape": 2, "route": 721, ...},
    {"id": 2, "class": "CTLandscape", "class_version": 0, "gps_min": [-32484210, 361073696], ...}
  ]
}
```

* Each object has an `id`, its C++ `class` name and the fields of that class
  in file order. Fields that point to other objects hold that object's `id`.
* Floats are written with as few digits as still give back the same 32-bit
  value; NaN and infinity as `{"f32bits": "..."}`. Strings that are not UTF-8
  are written as `{"cp1252": "..."}` so the original bytes survive.
* Fields without a known meaning keep the member offset from the game's code,
  e.g. `f_0x124`.

When editing, counts come from list lengths and ids must stay `1..n` in
order. Recompressed files can differ byte for byte from the originals because
the game uses a different zlib build; the decompressed data is identical.

## Development

```powershell
python -m pip install -e ".[cds]"
python -m unittest discover -s tests -v
```

Tests on real stages look for the Steam workshop stage folder and are skipped
without it; set `PCM_ZCES_STAGES` to point elsewhere and `PCM_ZCES_STEP` to
test more or fewer files. `python tools/make_class_docs.py STAGE_FOLDER`
regenerates `docs/classes.md`.

No game files are included in this repository. This is an independent
project and is not affiliated with Cyanide or Nacon.

## License

MIT
