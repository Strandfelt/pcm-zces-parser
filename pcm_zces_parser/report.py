"""Human-readable summary of a stage: everything the profile page shows.

    report = stage_report(view)        # dict
    text = stage_report_json(view)     # readable JSON text

Distances are km from the start line and heights metres above sea level, both
converted from game units (x10 and x7.5). Coordinates are WGS84 degrees and
only present when the stage has a real-world location.
"""
import bisect

from .jsonio import dumps

REPORT_VERSION = 1


def _at(view, km):
    s = view['samples']
    kms = [r[0] for r in s]
    i = min(max(bisect.bisect_left(kms, km), 0), len(s) - 1)
    return s[i]


def _point(view, km):
    r = _at(view, km)
    p = {'altitude_m': r[1]}
    if view.get('geo'):
        p['lat'], p['lon'] = r[4], r[5]
    return p


def stage_report(view, source_file=None):
    events = view['events']
    s = view['samples']
    stage = {
        'name': view['name'],
        'region': view.get('region') or None,
        'source_file': source_file,
        'distance_km': round(view['distance_km'], 2),
        'climbing_m': view['gain_m'],
        'highest_point_m': round(view['max_alt'], 1),
        'lowest_point_m': round(view['min_alt'], 1),
        'climbs': sum(1 for e in events if e['kind'] == 'climb'),
        'cobbles_km': round(sum(e['end_km'] - e['km'] for e in events if e['kind'] == 'cobbles'), 2),
        'gravel_km': round(sum(e['end_km'] - e['km'] for e in events if e['kind'] == 'gravel'), 2),
        'profile_source': {
            'cds': 'elevation and race points from the .cds file, route matched to it',
            'cds-approx': 'elevation from the .cds file, route positions approximate',
            'zces': 'elevation from the .zces road geometry only',
        }[view['profile_source']],
    }
    if view.get('geo'):
        lat = [r[4] for r in s]
        lon = [r[5] for r in s]
        stage['location'] = {
            'start': {'lat': _at(view, 0.0)[4], 'lon': _at(view, 0.0)[5]},
            'finish': {'lat': _at(view, view['distance_km'])[4], 'lon': _at(view, view['distance_km'])[5]},
            'bounds': {'south': min(lat), 'west': min(lon), 'north': max(lat), 'east': max(lon)},
        }
    else:
        stage['location'] = None

    race_points = []
    for e in events:
        if e['kind'] not in ('start', 'finish', 'sprint', 'kom'):
            continue
        p = {'type': {'kom': 'kom', 'sprint': 'intermediate_sprint'}.get(e['kind'], e['kind']),
             'name': e.get('name') or None, 'km': round(max(0.0, e['km']), 2)}
        if e['kind'] == 'kom':
            p['category_code'] = e.get('code')
        if e['kind'] == 'finish':
            p['summit_finish'] = bool(e.get('summit'))
        p.update(_point(view, e['km']))
        race_points.append(p)

    climbs = []
    for e in events:
        if e['kind'] != 'climb':
            continue
        climbs.append({
            'name': e['name'],
            'start_km': round(e['km'], 2), 'summit_km': round(e['end_km'], 2),
            'length_km': round(e['end_km'] - e['km'], 2),
            'avg_gradient_pct': round(e['avg'], 1), 'max_gradient_pct': round(e['max'], 1),
            'kom_category_code': e['kom']['code'] if e.get('kom') else None,
            'summit': _point(view, e['end_km']),
        })

    sectors = []
    for e in events:
        if e['kind'] not in ('cobbles', 'gravel'):
            continue
        sectors.append({
            'type': e['kind'], 'name': e['name'],
            'start_km': round(e['km'], 2), 'end_km': round(e['end_km'], 2),
            'length_km': round(e['end_km'] - e['km'], 2),
            'difficulty_stars': e['stars'],
            'start': _point(view, e['km']), 'end': _point(view, e['end_km']),
        })

    grad = view.get('gradients') or [0.0] * len(s)
    profile = []
    for r, g in zip(s, grad):
        if not 0 <= r[0] <= view['distance_km'] + 1e-6:
            continue
        p = {'km': round(r[0], 2), 'altitude_m': r[1], 'gradient_pct': round(g, 1)}
        if view.get('geo'):
            p['lat'], p['lon'] = r[4], r[5]
        profile.append(p)

    return {
        'format': 'pcm-zces-stage-report',
        'format_version': REPORT_VERSION,
        'units': {
            'km': 'kilometres from the start line',
            'altitude_m': 'metres above sea level',
            'gradient_pct': 'average gradient over 500 m centred on the point',
            'lat_lon': 'WGS84 degrees (the game world is the real area at 1:10 scale)',
            'category_code': "the game's KOM category code (lower is harder)",
            'difficulty_stars': 'sector difficulty: cobbles 1-5, gravel 1-3',
        },
        'stage': stage,
        'race_points': race_points,
        'climbs': climbs,
        'sectors': sectors,
        'profile': profile,
    }


def stage_report_json(view, source_file=None):
    """Readable JSON: one line per profile point, objects indented."""
    return dumps(stage_report(view, source_file), floats='exact')
