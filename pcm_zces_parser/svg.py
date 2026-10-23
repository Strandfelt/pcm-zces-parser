"""Static SVG images of a stage: the elevation profile and the route map.

    view = stage_view(doc, cds)
    profile_svg(view)          # str, standalone SVG document
    map_svg(view)

Both are self-contained (no scripts, fonts fall back to system faces) and
come in a light or dark theme.
"""
import math
from xml.sax.saxutils import escape

THEMES = {
    'light': {
        'bg': '#ffffff', 'ink': '#1d2422', 'muted': '#66706b', 'rule': '#d9ddd8', 'grid': '#e6e9e5',
        'route': '#1f5f8b', 'g': ['#cfe0c3', '#f1d98a', '#ee9f4f', '#d65a3a', '#8f1f2c'],
        'kom': '#c8102e', 'sprint': '#1f8a4c', 'pave': '#7a6a55', 'gravel': '#b9925a', 'climb': '#d65a3a',
    },
    'dark': {
        'bg': '#1c2321', 'ink': '#e5ebe7', 'muted': '#95a19b', 'rule': '#2e3835', 'grid': '#26302d',
        'route': '#6fb4e3', 'g': ['#3f5a3c', '#8d7a35', '#b26a2c', '#c24d32', '#e07a86'],
        'kom': '#ff5a6e', 'sprint': '#4fc283', 'pave': '#b9a68a', 'gravel': '#d6b37a', 'climb': '#c24d32',
    },
}
GRADIENT_CLASSES = ((3, '< 3 %'), (6, '3–6 %'), (9, '6–9 %'), (12, '9–12 %'), (math.inf, '> 12 %'))
FONT_DISPLAY = "'Barlow Condensed', 'Arial Narrow', 'Roboto Condensed', sans-serif"
FONT_DATA = "'IBM Plex Mono', ui-monospace, Consolas, monospace"


def _gclass(g):
    return next(i for i, (lim, _) in enumerate(GRADIENT_CLASSES) if g < lim)


def _nice_step(v):
    if v <= 0:
        return 1
    p = 10 ** math.floor(math.log10(v))
    f = v / p
    return (1 if f < 1.5 else 2 if f < 3 else 5 if f < 7 else 10) * p


def _f(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def _name(e):
    return e.get('name') or e['kind'].title()


def _labelled(view):
    """Events labelled above the profile, with the km where each sits."""
    out = []
    for e in view['events']:
        if e.get('merged') or e['kind'] not in ('climb', 'kom', 'sprint', 'finish', 'start'):
            continue
        k = e['end_km'] if e['kind'] == 'climb' else max(view['samples'][0][0], e['km'])
        out.append((k, e))
    out.sort(key=lambda t: t[0])
    return out


def _svg_open(w, h, c, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT_DATA}" font-size="11">',
            f'<title>{escape(title)}</title>',
            f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>']


def profile_svg(view, width=1200, plot_height=300, theme='light', title=True, max_label=22):
    """Elevation profile coloured by gradient, with climbs, KOMs, sprints,
    start and finish labelled above it and cobbled/gravel sectors below."""
    c = THEMES[theme]
    s = view['samples']
    km = [r[0] for r in s]
    alt = [r[1] for r in s]
    grad = view.get('gradients') or [0.0] * len(s)
    labels = _labelled(view)
    events = view['events']
    has = {k: any(e['kind'] == k for e in events) for k in ('cobbles', 'gravel')}

    head = 64 if title else 8
    longest = max([4] + [min(len(_name(e)) + (6 if e['kind'] == 'climb' else 0), max_label) for _, e in labels])
    band = round(34 + longest * 6.6)
    strips = 16 * (has['cobbles'] + has['gravel'])
    m_l, m_r = 52, 16
    top = head + band
    base = top + plot_height
    legend_y = base + 30 + strips + 14
    h = legend_y + 18
    w = width

    lo0, hi0 = min(alt), max(alt)
    step = _nice_step((hi0 - lo0) / 4 or 10)
    ylo = max(0.0, math.floor(lo0 / step) * step - (0 if lo0 < step else step))
    yhi = math.ceil(hi0 / step) * step + (step if hi0 - lo0 < 30 else 0)
    x = lambda k: m_l + (k - km[0]) / ((km[-1] - km[0]) or 1) * (w - m_l - m_r)
    y = lambda a: top + (1 - (a - ylo) / ((yhi - ylo) or 1)) * plot_height

    o = _svg_open(w, h, c, f'{view["name"]} – elevation profile')
    o.append('<defs>'
             f'<pattern id="pave" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             f'<rect width="3" height="6" fill="{c["pave"]}"/></pattern>'
             f'<pattern id="grav" width="5" height="5" patternUnits="userSpaceOnUse">'
             f'<circle cx="2.5" cy="2.5" r="1.3" fill="{c["gravel"]}"/></pattern></defs>')
    if title:
        stats = [f'{view["distance_km"]:.1f} km', f'{view["gain_m"]:,} m climbing',
                 f'{round(view["max_alt"])} m highest point']
        o.append(f'<text x="{m_l}" y="34" font-family="{FONT_DISPLAY}" font-size="28" font-weight="700" '
                 f'fill="{c["ink"]}">{escape((view["name"] or "Stage").upper())}</text>')
        o.append(f'<text x="{m_l}" y="54" fill="{c["muted"]}" font-size="12">'
                 f'{escape(" · ".join(filter(None, [view.get("region")] + stats)))}</text>')

    # grid and axes
    a = ylo
    while a <= yhi + 1e-6:
        o.append(f'<line x1="{m_l}" x2="{w - m_r}" y1="{y(a):.1f}" y2="{y(a):.1f}" stroke="{c["grid"]}"/>')
        o.append(f'<text x="{m_l - 6}" y="{y(a) + 4:.1f}" text-anchor="end" fill="{c["muted"]}">{round(a)}</text>')
        a += step
    o.append(f'<text x="{m_l - 6}" y="{top - 8}" text-anchor="end" fill="{c["muted"]}">m</text>')
    kstep = _nice_step((km[-1] - km[0]) / 10)
    k = math.ceil(km[0] / kstep) * kstep
    while k <= km[-1] + 1e-6:
        o.append(f'<line x1="{x(k):.1f}" x2="{x(k):.1f}" y1="{base}" y2="{base + 4}" stroke="{c["muted"]}"/>')
        o.append(f'<text x="{x(k):.1f}" y="{base + 16}" text-anchor="middle" fill="{c["muted"]}">{round(k)}</text>')
        k += kstep
    o.append(f'<text x="{w - m_r}" y="{base + 16}" text-anchor="end" fill="{c["muted"]}">km</text>')

    # gradient-coloured fill, one polygon per run of samples in the same class
    n = len(s)
    i0 = 0
    for i in range(1, n + 1):
        if i < n and _gclass(grad[i]) == _gclass(grad[i0]):
            continue
        a_, b_ = max(0, i0 - 1), min(n - 1, i)
        pts = ' '.join(f'{x(km[j]):.1f},{y(alt[j]):.1f}' for j in range(a_, b_ + 1))
        o.append(f'<polygon points="{x(km[a_]):.1f},{base} {pts} {x(km[b_]):.1f},{base}" '
                 f'fill="{c["g"][_gclass(grad[i0])]}"/>')
        i0 = i
    line = ' '.join(f'{x(k_):.1f},{y(a_):.1f}' for k_, a_ in zip(km, alt))
    o.append(f'<polyline points="{line}" fill="none" stroke="{c["ink"]}" stroke-width="1.4"/>')
    o.append(f'<line x1="{m_l}" x2="{w - m_r}" y1="{base}" y2="{base}" stroke="{c["muted"]}"/>')

    # sector strips
    sy = base + 26
    for kind, pat, col, label in (('cobbles', 'pave', c['pave'], 'pavé'), ('gravel', 'grav', c['gravel'], 'gravel')):
        if not has[kind]:
            continue
        o.append(f'<text x="{m_l - 6}" y="{sy + 8}" text-anchor="end" fill="{c["muted"]}">{label}</text>')
        for e in events:
            if e['kind'] == kind:
                ww = max(2.5, x(e['end_km']) - x(e['km']))
                o.append(f'<rect x="{x(e["km"]):.1f}" y="{sy}" width="{ww:.1f}" height="10" fill="url(#{pat})" '
                         f'stroke="{col}"><title>{escape(_name(e))}</title></rect>')
        sy += 16

    # labels above the profile, spread so they do not overlap
    gap = 13
    pos, last = [], -1e9
    for k_, e in labels:
        lx = max(x(k_), last + gap)
        pos.append([x(k_), lx, k_, e])
        last = lx
    nxt = w - m_r + gap
    for p in reversed(pos):
        p[1] = min(p[1], nxt - gap)
        nxt = p[1]
    colour = {'kom': c['kom'], 'sprint': c['sprint'], 'climb': c['climb'], 'finish': c['ink'], 'start': c['route']}
    idx = lambda k_: min(range(n), key=lambda j: abs(km[j] - k_))
    for px, lx, k_, e in pos:
        kind = 'kom' if e['kind'] == 'climb' and e.get('kom') else e['kind']
        col = colour[kind]
        py = y(alt[idx(k_)])
        text = _name(e) + (f'  {e["avg"]:.1f}%' if e['kind'] == 'climb' else '')
        if len(text) > max_label:
            text = text[:max_label - 1] + '…'
        o.append(f'<path d="M{px:.1f} {py - 2:.1f}L{px:.1f} {top - 2}L{lx:.1f} {top - 10}" fill="none" '
                 f'stroke="{col}" stroke-dasharray="2 2"/>')
        o.append(f'<circle cx="{lx:.1f}" cy="{top - 14}" r="4.5" fill="{col}"/>')
        o.append(f'<text transform="translate({lx + 4:.1f} {top - 22}) rotate(-90)" font-family="{FONT_DISPLAY}" '
                 f'font-size="12" font-weight="600" fill="{c["ink"]}">{escape(text)}</text>')

    # legend
    lx = m_l
    for i, (_, lab) in enumerate(GRADIENT_CLASSES):
        o.append(f'<rect x="{lx}" y="{legend_y - 9}" width="18" height="9" fill="{c["g"][i]}"/>')
        o.append(f'<text x="{lx + 23}" y="{legend_y}" fill="{c["muted"]}">{escape(lab)}</text>')
        lx += 23 + 7 * len(lab) + 14
    o.append('</svg>')
    return '\n'.join(o) + '\n'


def map_svg(view, size=800, theme='light', roads=True, title=True):
    """Top-down route map (north up) with the stage's other roads, climbs and
    sectors highlighted, race points, a scale bar and, when the stage has a
    real-world location, the coordinates of its corners."""
    c = THEMES[theme]
    s = view['samples']
    xs, ys = [r[2] for r in s], [r[3] for r in s]
    head = 56 if title else 0
    foot = 58 if view.get('geo') else 40
    w, h = size, size + head + foot
    pad = 24
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    scale = (size - 2 * pad) / span
    X = lambda v: pad + (v - cx) * scale + (size - 2 * pad) / 2
    Y = lambda v: head + pad + (size - 2 * pad) / 2 - (v - cy) * scale

    o = _svg_open(w, h, c, f'{view["name"]} – route map')
    if title:
        o.append(f'<text x="{pad}" y="32" font-family="{FONT_DISPLAY}" font-size="24" font-weight="700" '
                 f'fill="{c["ink"]}">{escape((view["name"] or "Stage").upper())}</text>')
        o.append(f'<text x="{pad}" y="48" fill="{c["muted"]}">{escape(view.get("region") or "")} · '
                 f'{view["distance_km"]:.1f} km</text>')
    o.append(f'<clipPath id="frame"><rect x="0" y="{head}" width="{size}" height="{size}"/></clipPath>')
    o.append('<g clip-path="url(#frame)">')
    if roads:
        for r in view.get('roads', []):
            pts = ' '.join(f'{X(r[i]):.1f},{Y(r[i + 1]):.1f}' for i in range(0, len(r), 2))
            o.append(f'<polyline points="{pts}" fill="none" stroke="{c["rule"]}" stroke-width="1.2"/>')
    route = ' '.join(f'{X(a):.1f},{Y(b):.1f}' for a, b in zip(xs, ys))
    o.append(f'<polyline points="{route}" fill="none" stroke="{c["bg"]}" stroke-width="7" stroke-linejoin="round"/>')
    o.append(f'<polyline points="{route}" fill="none" stroke="{c["route"]}" stroke-width="3.5" stroke-linejoin="round"/>')
    kms = [r[0] for r in s]

    def stretch(k0, k1):
        return [r for r in s if k0 <= r[0] <= k1]
    for e in view['events']:
        col = {'climb': c['kom'] if e.get('kom') else c['climb'], 'cobbles': c['pave'], 'gravel': c['gravel']}.get(e['kind'])
        if col and 'end_km' in e:
            seg = stretch(e['km'], e['end_km'])
            if len(seg) >= 2:
                pts = ' '.join(f'{X(r[2]):.1f},{Y(r[3]):.1f}' for r in seg)
                o.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="6" '
                         f'stroke-linecap="round"><title>{escape(_name(e))}</title></polyline>')
    for e in view['events']:
        if e.get('merged') or e['kind'] not in ('start', 'finish', 'kom', 'sprint', 'climb'):
            continue
        k_ = e['end_km'] if e['kind'] == 'climb' else e['km']
        r = s[min(range(len(s)), key=lambda j: abs(kms[j] - k_))]
        col = {'start': c['route'], 'finish': c['ink'], 'kom': c['kom'], 'sprint': c['sprint'],
               'climb': c['kom'] if e.get('kom') else c['climb']}[e['kind']]
        rad = 7 if e['kind'] in ('start', 'finish') else 4.5
        o.append(f'<circle cx="{X(r[2]):.1f}" cy="{Y(r[3]):.1f}" r="{rad}" fill="{col}" stroke="{c["bg"]}" '
                 f'stroke-width="2"><title>{escape(_name(e))}</title></circle>')
        if e['kind'] in ('start', 'finish'):
            right = X(r[2]) > size * 0.7
            o.append(f'<text x="{X(r[2]) + (-10 if right else 10):.1f}" y="{Y(r[3]) + 4:.1f}" '
                     f'text-anchor="{"end" if right else "start"}" font-family="{FONT_DISPLAY}" font-size="13" '
                     f'font-weight="600" fill="{c["ink"]}" stroke="{c["bg"]}" stroke-width="3" paint-order="stroke">'
                     f'{escape(_name(e))}</text>')
    o.append('</g>')

    # north arrow, scale bar (1 game unit = 10 m), corner coordinates
    o.append(f'<g transform="translate({size - pad - 10} {head + pad + 6})" fill="{c["ink"]}">'
             f'<path d="M0 -14L6 4L0 0L-6 4Z"/><text y="18" text-anchor="middle" font-size="11">N</text></g>')
    target_m = span / 4 * 10
    bar_m = _nice_step(target_m)
    bar_px = bar_m / 10 * scale
    by = head + size + 22
    o.append(f'<line x1="{pad}" x2="{pad + bar_px:.1f}" y1="{by}" y2="{by}" stroke="{c["ink"]}" stroke-width="2"/>')
    o.append(f'<text x="{pad + bar_px + 8:.1f}" y="{by + 4}" fill="{c["muted"]}">'
             f'{_f(bar_m / 1000) + " km" if bar_m >= 1000 else str(round(bar_m)) + " m"} (real-world scale)</text>')
    if view.get('geo'):
        lat = [r[4] for r in s]
        lon = [r[5] for r in s]
        hemi = lambda v, pos, neg: f'{abs(v):.4f}° {pos if v >= 0 else neg}'
        o.append(f'<text x="{pad}" y="{by + 24}" fill="{c["muted"]}">route spans '
                 f'{hemi(min(lat), "N", "S")} – {hemi(max(lat), "N", "S")}, '
                 f'{hemi(min(lon), "E", "W")} – {hemi(max(lon), "E", "W")}</text>')
    o.append('</svg>')
    return '\n'.join(o) + '\n'
