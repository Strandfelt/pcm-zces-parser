"""Real-world exports of a stage view: GPX and GeoJSON.

    view = route.stage_view(doc, cds)
    gpx_text(view), geojson_text(view)

Coordinates come from route.gps_transform: the stage map is the real area of
CTLandscape.gps_min..gps_max at 1:10 scale. Accuracy is as good as the
stage's own roads; well-made stages land within a few hundred metres.
"""
import bisect
import json
from xml.sax.saxutils import escape

POINT_KINDS = ('start', 'sprint', 'kom', 'finish')
RANGE_KINDS = ('climb', 'cobbles', 'gravel')


def _need_geo(view):
    if not view.get('geo'):
        raise ValueError('this stage has no real-world location (its GPS bounds are a placeholder)')


def _sample_at(view, km):
    s = view['samples']
    kms = [r[0] for r in s]
    i = min(max(bisect.bisect_left(kms, km), 0), len(s) - 1)
    return s[i]


def _slice(view, k0, k1):
    return [r for r in view['samples'] if k0 <= r[0] <= k1]


def _label(e):
    name = e.get('name') or e['kind'].title()
    if e['kind'] == 'climb':
        return f'{name} ({e["avg"]:.1f}% avg, {e["max"]:.1f}% max)'
    if e['kind'] in ('cobbles', 'gravel'):
        return f'{name} ({e["kind"]}, {e["stars"]} stars)'
    if e['kind'] == 'kom':
        return f'KOM {name}'
    if e['kind'] == 'sprint':
        return f'Sprint {name}'
    return f'{e["kind"].title()} {name}'.strip()


def gpx_text(view):
    """GPX 1.1: one track with elevation, waypoints for race points, climb
    tops and sector starts."""
    _need_geo(view)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<gpx version="1.1" creator="pcm-zces" xmlns="http://www.topografix.com/GPX/1/1">',
           f'  <metadata><name>{escape(view["name"] or "Stage")}</name>'
           f'<desc>{escape(view.get("region") or "")}</desc></metadata>']
    for e in view['events']:
        if e['kind'] in POINT_KINDS:
            r = _sample_at(view, e['km'])
        elif e['kind'] == 'climb':
            r = _sample_at(view, e['end_km'])
        elif e['kind'] in RANGE_KINDS:
            r = _sample_at(view, e['km'])
        else:
            continue
        out.append(f'  <wpt lat="{r[4]:.6f}" lon="{r[5]:.6f}"><ele>{r[1]:.1f}</ele>'
                   f'<name>{escape(_label(e))}</name><desc>km {max(0.0, e["km"]):.1f}</desc>'
                   f'<type>{escape(e["kind"])}</type></wpt>')
    out.append(f'  <trk><name>{escape(view["name"] or "Stage")}</name><trkseg>')
    for r in view['samples']:
        if 0 <= r[0] <= view['distance_km']:
            out.append(f'    <trkpt lat="{r[4]:.6f}" lon="{r[5]:.6f}"><ele>{r[1]:.1f}</ele></trkpt>')
    out.append('  </trkseg></trk>')
    out.append('</gpx>')
    return '\n'.join(out) + '\n'


# simplestyle-spec colours, picked up by geojson.io, GitHub and others
STYLE = {'route': '#1f5f8b', 'climb': '#d65a3a', 'kom': '#c8102e', 'cobbles': '#7a6a55', 'gravel': '#b9925a',
         'sprint': '#1f8a4c', 'start': '#1f5f8b', 'finish': '#1d2422'}


def geojson(view):
    """GeoJSON FeatureCollection (dict): the route, climbs and sectors as
    lines and race points as points. Coordinates are [lon, lat, elevation_m]."""
    _need_geo(view)
    dist = view['distance_km']

    def line(rows):
        return {'type': 'LineString', 'coordinates': [[r[5], r[4], r[1]] for r in rows]}
    feats = [{'type': 'Feature', 'geometry': line([r for r in view['samples'] if 0 <= r[0] <= dist]),
              'properties': {'kind': 'route', 'name': view['name'], 'region': view.get('region'),
                             'distance_km': dist, 'climbing_m': view['gain_m'],
                             'stroke': STYLE['route'], 'stroke-width': 4}}]
    for e in view['events']:
        if e.get('merged'):
            continue
        props = {'kind': e['kind'], 'label': _label(e)}
        props.update({k: v for k, v in e.items() if k not in ('kind', 'merged')})
        if e['kind'] in RANGE_KINDS:
            rows = _slice(view, e['km'], e['end_km'])
            if len(rows) >= 2:
                colour = STYLE['kom'] if e.get('kom') else STYLE[e['kind']]
                props.update({'stroke': colour, 'stroke-width': 7})
                feats.append({'type': 'Feature', 'geometry': line(rows), 'properties': props})
        elif e['kind'] in POINT_KINDS:
            r = _sample_at(view, e['km'])
            props.update({'marker-color': STYLE[e['kind']], 'marker-size': 'medium'})
            feats.append({'type': 'Feature', 'properties': props,
                          'geometry': {'type': 'Point', 'coordinates': [r[5], r[4], r[1]]}})
    return {'type': 'FeatureCollection', 'features': feats}


def geojson_text(view):
    return json.dumps(geojson(view), ensure_ascii=False, indent=1) + '\n'
