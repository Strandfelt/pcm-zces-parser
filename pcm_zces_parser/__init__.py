"""Read, write and visualise Pro Cycling Manager .zces stage files.

A .zces file is the compiled 3D stage the game loads: terrain, roads,
buildings, vegetation, sprints and so on.

Lossless conversion:

    doc = read_zces("stage.zces")          # dict of every object in the file
    text = to_json(doc)                    # readable JSON
    write_zces(from_json(text), "copy.zces")

Stage data and exports:

    view = load_stage("stage.zces")        # route, profile, climbs, sectors, race points
    profile_svg(view), map_svg(view)       # SVG images
    geojson(view), gpx_text(view)          # real-world route
    stage_report(view)                     # readable summary dict
    profile_html(view)                     # interactive page
    export_stage(view, "out")              # all of the above as files
"""
from collections import Counter
from pathlib import Path

from .archive import FORMAT_NAME, FORMAT_VERSION, read_archive, write_archive
from .jsonio import dumps as _dumps, loads as _loads
from .stream import FormatError, pack_container, unpack_container

__version__ = '0.1.0'


def read_zces_bytes(data):
    """Decode the bytes of a .zces file into a dict."""
    return read_archive(unpack_container(data))


def read_zces(path):
    """Decode a .zces file into a dict."""
    return read_zces_bytes(Path(path).read_bytes())


def zces_bytes(doc):
    """Encode a decoded stage back to .zces bytes."""
    return pack_container(write_archive(doc))


def write_zces(doc, path):
    """Encode a decoded stage and write it to `path`."""
    Path(path).write_bytes(zces_bytes(doc))


def to_json(doc):
    """Readable JSON text for a decoded stage (lossless)."""
    return _dumps(doc)


def from_json(text):
    """Parse JSON text written by to_json back into a decoded stage."""
    doc = _loads(text)
    if not isinstance(doc, dict) or doc.get('format') != FORMAT_NAME:
        raise FormatError('not a pcm-zces JSON document')
    if doc.get('format_version') != FORMAT_VERSION:
        raise FormatError(f'unsupported pcm-zces JSON version {doc.get("format_version")}')
    return doc


def summary(doc):
    """Short overview: stage name, region, versions and object counts."""
    objs = doc['objects']
    info = next((o for o in objs if o['class'] == 'CTStageInfo'), {})

    def text(v):
        if isinstance(v, dict):
            return next(iter(v.values()))
        return v
    return {
        'name': text(info.get('name')),
        'region': text(info.get('region')),
        'archive_version': doc['archive_version'],
        'objects': len(objs),
        'classes': dict(Counter(o['class'] for o in objs).most_common()),
    }


# stage views and exports (imported last: they use the functions above)
from .route import gps_transform, stage_view                       # noqa: E402
from .svg import map_svg, profile_svg                              # noqa: E402
from .geo import geojson, geojson_text, gpx_text                   # noqa: E402
from .report import stage_report, stage_report_json                # noqa: E402
from .profile_page import profile_html                             # noqa: E402
from .stage import FORMATS, export_stage, load_stage, read_cds_file  # noqa: E402

__all__ = [
    # lossless file access
    'FormatError', 'read_zces', 'read_zces_bytes', 'write_zces', 'zces_bytes',
    'to_json', 'from_json', 'summary', 'unpack_container', 'pack_container',
    'read_archive', 'write_archive', 'FORMAT_NAME', 'FORMAT_VERSION',
    # stage views and exports
    'load_stage', 'stage_view', 'gps_transform', 'read_cds_file',
    'profile_svg', 'map_svg', 'geojson', 'geojson_text', 'gpx_text',
    'stage_report', 'stage_report_json', 'profile_html', 'export_stage', 'FORMATS',
]
