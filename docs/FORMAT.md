# The PCM `.zces` stage format

A `.zces` file holds a stage's 3D world for Pro Cycling Manager 26: terrain,
roads, fences, houses, cities, vegetation, water, sprints, the podium and
more. It sits next to the stage's `.cds` file, which holds the profile and
race data (see [pcm-cds-profile](https://github.com/Strandfelt/pcm-cds-profile)).
The Stage Editor's own autosaves use `.zcts`, and the editor has an
`-exportzces` command-line option.

This description was worked out from `CTStageEditorPCMMaster64.exe`
(PCM 26 Stage Editor) and checked against all 3,367 stages of a large
workshop pack: every file decodes and re-encodes to the same bytes.
RVAs in brackets point to the relevant code in that executable.

All integers are little-endian.

## 1. Container

```
u32  0
repeat:
    u32  comp_size + 16
    u32  raw_size            (0x500000 = 5 MiB for every chunk except the last)
    u32  comp_size
    u32  0
    u32  0x12345678
    comp_size bytes          zlib stream (level 1, header 78 01)
u32  0                       terminator
```

Joining the decompressed chunks gives the archive. The game's compressor is
not Python's zlib, so recompressed files can differ byte for byte from the
originals; the decompressed archive is the same.

## 2. Archive

```
u32  version        archive version; 112..134 (0x70..0x86) in PCM 26 files
u32  flag           1 in game files; some loaders check it
u32  object_count
object_count x string   class name of each object (object ids are 1..object_count)
u32  root_count
root_count x u32        root object ids; always [1], the CTStage
object data             one record per object, in id order, no padding
```

The loader [0x35dee0] rejects versions below 0x67, creates an empty object
for each class name, then calls each object's `Load(stream)` in id order.
Objects refer to each other by id, so the whole stage is one object graph
rooted at the `CTStage`.

### Object header

Almost every `Load` first calls `CTBaseObject::Load` [0x35ea40], which reads:

```
u16  class_version
u16  0xCEAD
```

The class version gates fields within that class. Two classes skip this
header: `CTCitySplineHeightMap` and `CTBloc`.

## 3. Value encodings

| Name | Encoding | JSON |
|---|---|---|
| u8, u16, u32, i32 | fixed size | number |
| f32 | IEEE single | number; NaN/inf as `{"f32bits": "7fc00000"}` |
| vec2 / vec3 / vec4 | 2 / 3 / 4 f32 | list |
| string | u32 byte length, bytes, no terminator | string; non-UTF-8 text as `{"cp1252": "..."}` |
| ref | u32 object id, 0 = none | id or `null` |
| list | u32 count, then the items | list |
| table | u32 count, then fixed-size records | list of rows |
| tagged block | u32 tag, u32 size, body | object under `block_<tag>` |
| marker | optional u32 that is only consumed when it equals a magic value | `true`/`false` |

Notes:

* **Strings** are mostly ASCII. Place names use either UTF-8 or Windows-1252,
  sometimes both within one file, so the JSON keeps track of which.
* **Floats** sometimes hold uninitialised memory (NaN patterns), which is why
  NaN/inf keep their exact bits.
* **Tagged blocks** (`CTCity`, `CTPart`, `CTZone`, `CTBloc`) carry their own
  version tag, e.g. `0x70008`. `size` counts from the size field itself to
  the end of the block. When the tag is not the expected one the engine skips
  `size` bytes; this tool keeps such a block as raw base64.
* **Markers** (`CTCity`, `CTCityView`): the loader peeks at the next u32 and
  only consumes it when it equals `0xFFFFFFFF` or `0xFFFFFFFE` [0x35d8b0].
* **Handles**: some `CTCityView`, `CTBloc`, `CTPart` and `CTZone` record
  columns hold values like `0x0E000001`, i.e. `(kind << 24) | index`. They
  link city geometry elements together.

## 4. Version gates

Fields are added over time and guarded by either

* the archive version (`stream+0x70`), e.g. `CTStage` reads the stage-info
  reference only when `version >= 0x49`, or
* the object's class version, e.g. `CTRoadPoint` has a name only from class
  version 1.

`pcm_zces_parser/classes.py` spells out each condition. The PCM 26 files seen use
archive versions 112, 113, 114, 115, 129, 131, 132 and 134.

## 5. The object graph

```
CTStage
├── CTLandscape ── CTLandscapeTree (quadtree, 65x65 heightmap per tile)
├── CTRoute ── CTRouteDescriptor ── road points along the race route
├── CTRoadNetwork ── CTRoad ── CTRoadCurve ── CTRoadPoint / CTRoadTangentControlPoint
│                 ├─ CTRoadIntersection
│                 └─ CTSectionManager (named cobbled/dirt sectors, e.g. "Oude Kwaremont")
├── CTRiverNetwork / CTWaterNetwork / CTElectricNetwork / CTFenceNetwork
├── CTWallHouseNetwork (rows of houses) / CTSplineSpawnableNetwork
├── CTVegetation ── field areas, forest areas, tree rows
├── CTCities ── CTCity ── CTPart ── CTZone ── CTBloc, plus CTCityView geometry
├── CTRoadSpline ── CTCitySplineHeightMap, RoadBestTraj (racing line)
├── CTSpawnableObjectManager ── CTSpawnedObject (placed models)
├── CTSprintManager ── CTSprint (start, finish, KOM, sprint lines)
├── CTCircuitManager, CTPodium, CTMonumentManager, CTAudioCommentaryManager,
├── CTSplineDescriptionManager (climb names), CTProfileCameraManager
└── CTStageInfo (stage name, region)
```

### Splines

Roads, rivers, fences, house rows, field and forest areas, power lines and
cities all build on one cubic Bézier system:

* a **network** (`splines`, `control_points`, `intersections` lists);
* a **spline** (length, 2D bounding box, network, first and last curve);
* a **curve** per segment (start/end point, start/end tangent, previous/next
  curve, owning spline, length, 3D bounding box);
* **main control points** (position, the curves that meet there, an optional
  intersection);
* **tangent control points** (position plus two vectors, owning curve).

The class names differ per network (`CTRoadCurve`, `CTFenceCurve`, ...) and
add their own fields after the shared part.

### Terrain

`CTLandscape` holds the GPS bounds as integer (longitude, latitude) pairs in
units of 1e-7 degrees, the map size in game units and the root `CTLandscapeTree`.

The editor creates terrain from the 5° × 5° lat/lon elevation tiles in its
`Data/Dem` folder (6000 × 6000 samples each), sampled over the GPS box. The
map covers `0..size` in both axes, x east and y north, so game coordinates
convert to the real world linearly:

```
lat = lat_min + y / size * (lat_max - lat_min)
lon = lon_min + x / size * (lon_max - lon_min)
```

This makes every stage the real area at 1:10 scale, which is where the ×10
distance factor comes from; heights use ×7.5. Stages built without real
terrain have a placeholder box starting at 0,0.
Each tree node is a quadtree tile with four children and a `CTHeightData`:

* `resolution` = 65, so `height_map.values` has 65 × 65 = 4225 u16 samples;
* height in metres = `sample * 0.1 + height_offset`. `height_offset` is
  usually −225.0; high or very low stages use other values (−180, −135, 175,
  1125 were seen);
* `min_height` / `max_height` and the per-quadrant min/max describe the tile;
* `terraform_map` (4-byte samples) is only present when `heightmap_only` is 0.

## 6. What is not known

Field names come from what the code does with a value and from the values
themselves. Fields without a clear meaning keep the C++ member offset, e.g.
`f_0x124`. Those are still decoded with the right size and type, so editing
them works; their meaning just isn't documented.

Things kept opaque:

* `CTLandscapeTree.uv_map` (0x8408 bytes, only present with geometry);
* `CTSectionManager.legacy` (class version 0 only, 0x30 bytes).

See [classes.md](classes.md) for every class's fields with examples.
