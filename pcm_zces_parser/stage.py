"""Load a stage and export it in every format.

    from pcm_zces_parser import load_stage, export_stage
    view = load_stage("topclas_rondevv_2026.zces")
    export_stage(view, "out")                       # all formats
    export_stage(view, "out", formats=["profile-svg", "geojson"])
"""
from pathlib import Path

from . import read_zces
from .geo import geojson_text, gpx_text
from .profile_page import profile_html
from .report import stage_report_json
from .route import stage_view
from .svg import map_svg, profile_svg


def read_cds_file(path):
    """The .cds stage profile via pcm-cds-profile, or None if that package is
    not installed."""
    try:
        import pcm_cds_profile
    except ImportError:
        return None
    return pcm_cds_profile.read_cds(Path(path))


def load_stage(zces_path, cds='auto'):
    """Decode a .zces file into a stage view (route, profile, race points).

    cds: 'auto' uses STAGE.cds next to the .zces when it exists and
    pcm-cds-profile is installed; a path uses that file; None or False uses
    the .zces geometry only.
    """
    zces_path = Path(zces_path)
    data = None
    if cds == 'auto':
        sibling = zces_path.with_suffix('.cds')
        data = read_cds_file(sibling) if sibling.exists() else None
    elif cds:
        data = read_cds_file(cds)
        if data is None:
            raise ImportError('reading a .cds file needs pcm-cds-profile (pip install pcm-zces-parser[cds])')
    view = stage_view(read_zces(zces_path), data)
    view['source_file'] = zces_path.name
    return view


# name -> (file suffix, renderer(view, theme), needs a real-world location)
FORMATS = {
    'html': ('.html', lambda v, t: profile_html(v, v.get('source_file', '')), False),
    'profile-svg': ('.profile.svg', lambda v, t: profile_svg(v, theme=t), False),
    'map-svg': ('.map.svg', lambda v, t: map_svg(v, theme=t), False),
    'json': ('.stage.json', lambda v, t: stage_report_json(v, v.get('source_file')), False),
    'geojson': ('.geojson', lambda v, t: geojson_text(v), True),
    'gpx': ('.gpx', lambda v, t: gpx_text(v), True),
}


def export_stage(view, out_dir, stem=None, formats=None, theme='light'):
    """Write the chosen formats (default: all) to out_dir and return
    {format: path}. GeoJSON and GPX are skipped for stages without a
    real-world location."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or Path(view.get('source_file') or 'stage').stem
    written = {}
    for name in formats or FORMATS:
        if name not in FORMATS:
            raise ValueError(f'unknown format {name!r}; choose from {", ".join(FORMATS)}')
        suffix, render, needs_geo = FORMATS[name]
        if needs_geo and not view.get('geo'):
            continue
        path = out_dir / (stem + suffix)
        path.write_text(render(view, theme), encoding='utf-8')
        written[name] = path
    return written
