"""Race route, profile and race markers from a decoded stage.

Distances along the race ("spline distance") are in game units. The game's
stage files store the world at reduced scale: 1 unit of distance is 10 m and
1 unit of height is 7.5 m (the same factors pcm-cds-profile uses).

The route is rebuilt from the zces data: `CTRouteDescriptor.points` lists
waypoints (road points), and the road network's curves connect them. The
shortest path between consecutive waypoints gives the driven line; each
curve is a cubic Bézier through its two road points and two tangent points.

The game measures race distance along a slightly different line than the road
centre, so road length and race distance drift apart by about 1%. When the
stage's .cds file is available its profile is the game's own, and the route
is aligned to it by elevation (dynamic time warping), which maps every race
distance to a point on the map. Without a .cds file the road length is used
directly, which is close but not exact.
"""
import bisect
import collections
import heapq
import math

DISTANCE_M_PER_UNIT = 10.0
HEIGHT_M_PER_UNIT = 7.5
PROFILE_STEP = 20.0          # race units between profile samples (= 200 m)


class Objects:
    def __init__(self, doc):
        self.list = doc['objects']
        self.by_class = collections.defaultdict(list)
        for o in self.list:
            self.by_class[o['class']].append(o)

    def __call__(self, i):
        return self.list[i - 1] if i else None

    def first(self, cls):
        objs = self.by_class.get(cls)
        return objs[0] if objs else None


def text(v):
    if isinstance(v, dict):
        return next(iter(v.values()))
    return v or ''


# ---------------------------------------------------------------- geometry
def _bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
        out.append([a * p0[k] + b * p1[k] + c * p2[k] + d * p3[k] for k in range(3)])
    return out


def curve_points(g, cv, n=24):
    p0 = g(cv['start_point'])['position']
    p3 = g(cv['end_point'])['position']
    p1 = g(cv['start_tangent'])['position'] if cv['start_tangent'] else p0
    p2 = g(cv['end_tangent'])['position'] if cv['end_tangent'] else p3
    return _bezier(p0, p1, p2, p3, n)


def road_graph(g, objs):
    adj = collections.defaultdict(list)
    for cv in objs.by_class.get('CTRoadCurve', []):
        a, b = cv['start_point'], cv['end_point']
        if a and b:
            adj[a].append((b, cv['length'], cv['id']))
            adj[b].append((a, cv['length'], cv['id']))
    return adj


def _shortest(adj, s, t):
    dist, prev, heap = {s: 0.0}, {}, [(0.0, s)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == t:
            break
        if d > dist[u]:
            continue
        for v, w, c in adj[u]:
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                prev[v] = (u, c)
                heapq.heappush(heap, (nd, v))
    if t not in dist:
        return None
    seq, u = [], t
    while u != s:
        p, c = prev[u]
        seq.append((p, c))
        u = p
    return seq[::-1]


def _road_chains(g, objs):
    """Ordered curve ids of every CTRoad, and for each road point the
    (road, node index) places where it sits on those chains."""
    chains, nodes = {}, collections.defaultdict(list)
    for road in objs.by_class.get('CTRoad', []):
        seq, c, seen = [], road['first_curve'], set()
        while c and c not in seen:
            seen.add(c)
            seq.append(c)
            c = g(c)['next_curve']
        chains[road['id']] = seq
        for i, cid in enumerate(seq):
            cv = g(cid)
            if cv['start_point']:
                nodes[cv['start_point']].append((road['id'], i))
            if cv['end_point']:
                nodes[cv['end_point']].append((road['id'], i + 1))
    return chains, nodes


def _along_road(g, chains, nodes, a, b, last_curve=None):
    """Curves from road point a to b along one road, as (start point, curve).
    The shortest option wins, except one that turns back along `last_curve`
    (closed loops have two ways between the same points)."""
    options = []
    for ra, ia in set(nodes.get(a, ())):
        for rb, ib in set(nodes.get(b, ())):
            if ra != rb or ia == ib:
                continue
            lo, hi = sorted((ia, ib))
            curves = chains[ra][lo:hi]
            if ia > ib:
                curves = curves[::-1]
            options.append((sum(g(c)['length'] for c in curves), curves))
    if not options:
        return None
    options.sort(key=lambda o: o[0])
    curves = next((c for _, c in options if c[0] != last_curve), options[0][1])
    seq, at = [], a
    for cid in curves:
        cv = g(cid)
        seq.append((at, cid))
        at = cv['end_point'] if cv['start_point'] == at else cv['start_point']
    return seq


def expand_circuits(objs, waypoints):
    """A CTCircuit is a closed loop of road points ridden `laps` times. Some
    routes list every lap, others list the loop once; add the missing laps."""
    for c in objs.by_class.get('CTCircuit', []):
        loop = [p for p in c['points'] if p and p <= len(objs.list) and 'position' in objs(p)]
        laps = c['laps']
        if len(loop) < 3 or loop[0] != loop[-1] or laps < 2 or loop[0] not in waypoints:
            continue
        ring = loop[:-1]
        n = len(ring)
        # count how many full laps the route already contains, starting at the loop's first point
        i = waypoints.index(loop[0])
        done, j = 0, i
        while waypoints[j:j + n] == ring:
            done += 1
            j += n
        if 0 < done < laps:
            waypoints = waypoints[:j] + ring * (laps - done) + waypoints[j:]
        elif done == 0:
            # the route passes through the loop without following it lap by lap
            waypoints = waypoints[:i] + ring * (laps - 1) + waypoints[i:]
    return waypoints


def route_polyline(doc, expand=True, no_uturn=True):
    """3D polyline (game units) of the race route and its cumulative length.

    Consecutive waypoints of the route lie on one road; the race follows that
    road's curve chain between them. Pairs that share no road fall back to the
    shortest path through the road network. `expand` adds circuit laps the
    route lists only once; `no_uturn` stops a segment from doubling back over
    the curve just ridden (needed on closed loops).
    """
    objs = Objects(doc)
    g = objs
    stage = objs.list[0]
    route = g(stage['route'])
    waypoints = g(route['route_descriptor'])['points'] if route else []
    # some files keep stale ids here; use only ids that point at a road point
    waypoints = [w for w in waypoints if w and w <= len(objs.list) and 'position' in objs(w)]
    if expand:
        waypoints = expand_circuits(objs, waypoints)
    if len(waypoints) < 2:
        raise ValueError('stage has no route')
    chains, nodes = _road_chains(g, objs)
    adj = None
    poly = [g(waypoints[0])['position']]
    last = None
    for a, b in zip(waypoints, waypoints[1:]):
        if a == b:
            continue
        seq = _along_road(g, chains, nodes, a, b, last if no_uturn else None)
        if seq is None:
            if adj is None:
                adj = road_graph(g, objs)
            seq = _shortest(adj, a, b)
        if seq is None:                                 # not connected: straight line
            poly.append(g(b)['position'])
            last = None
            continue
        last = seq[-1][1] if seq else last
        for start, cid in seq:
            cv = g(cid)
            pts = curve_points(g, cv)
            if cv['start_point'] != start:
                pts.reverse()
            poly.extend(pts[1:])
    cum = [0.0]
    for p, q in zip(poly, poly[1:]):
        cum.append(cum[-1] + math.dist(p, q))
    return poly, cum


def _interp(cum, poly, s):
    i = min(max(bisect.bisect_left(cum, s), 1), len(cum) - 1)
    span = cum[i] - cum[i - 1] or 1.0
    t = min(max((s - cum[i - 1]) / span, 0.0), 1.0)
    a, b = poly[i - 1], poly[i]
    return [a[k] + t * (b[k] - a[k]) for k in range(3)]


# ---------------------------------------------------------------- alignment
def align(cds_heights, cum, poly, step=5.0, band_m=800.0):
    """Map each .cds profile sample (every PROFILE_STEP units) to a distance
    along the road polyline by matching elevations. Returns (road distances,
    mean absolute height error in game units)."""
    road_len = cum[-1]
    m = int(road_len // step) + 1
    mine = [_interp(cum, poly, j * step)[2] for j in range(m)]
    n = len(cds_heights)
    k = road_len / max((n - 1) * PROFILE_STEP, 1.0)
    band = int(band_m / step)
    max_jump = int(2 * PROFILE_STEP / step)
    prev = {0: (abs(cds_heights[0] - mine[0]), -1)}
    back = []
    for i in range(1, n):
        c = i * PROFILE_STEP * k / step
        lo, hi = max(0, int(c - band)), min(m - 1, int(c + band))
        cur = {}
        for j in range(lo, hi + 1):
            best, arg = math.inf, None
            for dj in range(1, max_jump + 1):
                q = prev.get(j - dj)
                if q is not None and q[0] < best:
                    best, arg = q[0], j - dj
            if arg is not None:
                cur[j] = (best + abs(cds_heights[i] - mine[j]), arg)
        if not cur:
            return None, math.inf
        back.append(cur)
        prev = cur
    j = min(prev, key=lambda x: prev[x][0])
    cost = prev[j][0]
    path = [j]
    for i in range(n - 1, 0, -1):
        j = back[i - 1][j][1]
        path.append(j)
    path.reverse()
    return [p * step for p in path], cost / n


# ---------------------------------------------------------------- markers
def markers(doc):
    """Race events with their spline distance (game units)."""
    objs = Objects(doc)
    out = []
    for s in objs.by_class.get('CTSprint', []):
        name = s['name']
        kind = None
        if name.startswith('Depart'):
            kind = 'start'
        elif name.startswith('Arrive'):
            kind = 'finish'
        elif 'Montagne' in name:
            kind = 'kom'
        elif name.startswith('Sprint') and not name.startswith(('Sprint_', 'SprintLadder')):
            kind = 'sprint'
        if kind:
            ev = {'kind': kind, 'at': s['position'], 'name': text(s['city']), 'code': s['type'],
                  'marker': name}
            if kind == 'finish':
                ev['summit'] = 'Mont' in name
            out.append(ev)
    for d in objs.by_class.get('CTSplineDescription', []):
        if d.get('f_0x24', 0) == 0:
            out.append({'kind': 'climb', 'at': d['f_0x48'], 'end': d['f_0x4c'], 'name': text(d['name']),
                        'avg': d['f_0x50'], 'max': d['f_0x58']})
    sm = objs.first('CTSectionManager')
    if sm:
        for key, kind in (('sections', 'cobbles'), ('sections2', 'gravel')):
            for s in sm.get(key, []):
                out.append({'kind': kind, 'at': s['start'], 'end': s['end'], 'name': text(s['name']),
                            'stars': s['type']})
    out.sort(key=lambda e: e['at'])
    return out


def gps_transform(doc):
    """Function (x, y) -> (lat, lon) for game coordinates, or None.

    The editor builds a stage's terrain from 5x5 degree lat/lon DEM tiles
    (Data/Dem) over the box CTLandscape.gps_min..gps_max, mapped onto the
    square map 0..size in both axes (x east, y north). The world is therefore
    the real area at 1:10 scale, and the mapping is linear in degrees.
    Stages built without real terrain have a dummy box near 0,0 and get None.
    """
    land = Objects(doc).first('CTLandscape')
    if not land:
        return None
    (lon0, lat0), (lon1, lat1) = [(a / 1e7, b / 1e7) for a, b in (land['gps_min'], land['gps_max'])]
    size = land['size']
    if (size <= 0 or lon1 - lon0 < 0.01 or lat1 - lat0 < 0.01 or not (-90 <= lat0 < lat1 <= 90)
            or (land['gps_min'] == [0, 0])):
        return None
    return lambda x, y: (lat0 + y / size * (lat1 - lat0), lon0 + x / size * (lon1 - lon0))


def _cds_name(sprint):
    raw = bytes.fromhex(sprint.get('name_bytes_hex') or '')
    for enc in ('utf-8', 'cp1252', 'latin1'):
        try:
            return raw.decode(enc)
        except UnicodeError:
            pass
    return sprint.get('name_utf8_display', '')


# ---------------------------------------------------------------- everything
def stage_view(doc, cds=None):
    """Data for the profile page.

    `cds` is the dict returned by pcm_cds_profile.read_cds for the same stage,
    or None. Distances in the result are km from the start line, heights m.
    """
    objs = Objects(doc)
    info = objs.first('CTStageInfo') or {}
    ev = markers(doc)
    start = next((e['at'] for e in ev if e['kind'] == 'start'), 0.0)
    finish = max((e['at'] for e in ev if e['kind'] == 'finish'), default=None)
    if cds:
        # the .cds start and race length are what the game computed; zces sprint
        # positions can be stale in some files
        cstart = next((s['spline_distance_m'] / DISTANCE_M_PER_UNIT for s in cds.get('sprints', [])
                       if s.get('type_code') == 1), None)
        if cstart is not None:
            start = cstart
        if cds.get('race_length_m'):
            finish = start + cds['race_length_m'] / DISTANCE_M_PER_UNIT
        # race points from the .cds (the game's own list): 1 start, 3 flat finish,
        # 4 summit finish, 5 intermediate sprint, 6 KOM; 8 are unnamed timing points
        kinds = {1: 'start', 3: 'finish', 4: 'finish', 5: 'sprint', 6: 'kom'}
        cev = []
        for s in cds.get('sprints', []):
            kind = kinds.get(s.get('type_code'))
            if not kind:
                continue
            e = {'kind': kind, 'at': s['spline_distance_m'] / DISTANCE_M_PER_UNIT,
                 'name': _cds_name(s), 'code': s.get('category_code', 0)}
            if kind == 'start':
                e['at'] = start
            if kind == 'finish':
                e['at'] = finish
                e['summit'] = s.get('type_code') == 4
            cev.append(e)
        if cev:
            ev = sorted([e for e in ev if e['kind'] not in ('start', 'finish', 'sprint', 'kom')] + cev,
                        key=lambda e: e['at'])

    source = 'zces'
    heights = None
    road_at = None
    if cds and cds.get('raw_profile_points'):
        raw = cds['raw_profile_points']
        heights = [h for _, h in raw]
        target = (len(raw) - 1) * PROFILE_STEP
        variants = []
        for expand in (True, False):
            for no_uturn in (True, False):
                poly, cum = route_polyline(doc, expand, no_uturn)
                variants.append((abs(cum[-1] - target), poly, cum))
        variants.sort(key=lambda v: v[0])
        _, poly, cum = variants[0]
        road_at, err = align(heights, cum, poly)
        if road_at is not None and err < 0.5:
            source = 'cds'
        else:                                           # keep the game's heights, place them approximately
            source = 'cds-approx'
            scale = cum[-1] / max(target, 1.0)
            road_at = [i * PROFILE_STEP * scale for i in range(len(raw))]
    else:
        poly, cum = route_polyline(doc)
    if road_at is None:                                 # geometry only
        n = int(cum[-1] // PROFILE_STEP) + 1
        road_at = [i * PROFILE_STEP for i in range(n)]
        heights = [_interp(cum, poly, s)[2] for s in road_at]
    if finish is None:
        finish = (len(road_at) - 1) * PROFILE_STEP

    to_gps = gps_transform(doc)
    samples = []
    for i, (s_road, h) in enumerate(zip(road_at, heights)):
        at = i * PROFILE_STEP
        if at < start - PROFILE_STEP or at > finish + PROFILE_STEP:
            continue
        x, y, _ = _interp(cum, poly, s_road)
        row = [round((at - start) * DISTANCE_M_PER_UNIT / 1000, 3),
               round(h * HEIGHT_M_PER_UNIT, 1), round(x, 1), round(y, 1)]
        if to_gps:
            lat, lon = to_gps(x, y)
            row += [round(lat, 6), round(lon, 6)]
        samples.append(row)

    # faint context: every road of the network, as polylines
    roads = []
    for cv in objs.by_class.get('CTRoadCurve', []):
        if cv['start_point'] and cv['end_point']:
            pts = curve_points(objs, cv, n=6)
            roads.append([v for p in pts for v in (round(p[0]), round(p[1]))])

    def km(u):
        return round((u - start) * DISTANCE_M_PER_UNIT / 1000, 3)
    events = []
    for e in ev:
        e = dict(e)
        e['km'] = km(e.pop('at'))
        if 'end' in e:
            e['end_km'] = km(e.pop('end'))
        events.append(e)
    dist = km(finish)
    events = [e for e in events if -0.5 <= e['km'] <= dist + 0.5]
    name = text(info.get('name'))
    _finish_events(events, name)
    alts = [s[1] for s in samples]
    gain = sum(max(0.0, b - a) for a, b in zip(alts, alts[1:]))
    return {
        'name': name, 'region': text(info.get('region')),
        'distance_km': dist, 'profile_source': source,
        'max_alt': max(alts) if alts else 0, 'min_alt': min(alts) if alts else 0,
        'gain_m': round(gain), 'samples': samples, 'gradients': gradients(samples),
        'events': events, 'roads': roads, 'geo': to_gps is not None,
    }


def gradients(samples, window_km=0.5):
    """Gradient in % at each sample, over `window_km` centred on it."""
    km = [s[0] for s in samples]
    alt = [s[1] for s in samples]
    n, half, out = len(samples), window_km / 2, []
    for i in range(n):
        a = b = i
        while a > 0 and km[i] - km[a] < half:
            a -= 1
        while b < n - 1 and km[b] - km[i] < half:
            b += 1
        span = km[b] - km[a]
        out.append(round((alt[b] - alt[a]) / (span * 10), 2) if span > 0 else 0.0)  # m per km / 10 = %
    return out


def _finish_events(events, stage_name):
    """Attach each KOM to the climb it tops (marking the KOM `merged`), and
    name an unnamed start or finish after the towns in the stage name."""
    climbs = [e for e in events if e['kind'] == 'climb']
    for k in (e for e in events if e['kind'] == 'kom'):
        c = next((c for c in climbs if 'kom' not in c and abs(c['end_km'] - k['km']) < 1.0), None)
        if c:
            c['kom'] = {'name': k.get('name', ''), 'code': k.get('code'), 'km': k['km']}
            k['merged'] = True
    towns = (stage_name or '').split(' - ')
    for e in events:
        if not e.get('name') and e['kind'] == 'start':
            e['name'] = towns[0]
        if not e.get('name') and e['kind'] == 'finish':
            e['name'] = towns[-1]
