"""Command line: convert .zces stage files to JSON and back.

    pcm-zces to-json STAGE.zces [more.zces ...] [-o OUT_DIR]
    pcm-zces from-json STAGE.json [more.json ...] [-o OUT_DIR]
    pcm-zces info STAGE.zces
    pcm-zces export STAGE.zces [more.zces ...] [-o OUT_DIR] [--only html,profile-svg,...]
    pcm-zces profile STAGE.zces ...      (export --only html)
    pcm-zces gpx STAGE.zces ... [--format gpx|geojson]
"""
import argparse
import json
import sys
from pathlib import Path

from . import (FormatError, from_json, read_zces, read_zces_bytes, summary, to_json,
               zces_bytes)


def _out_path(src, out_dir, suffix):
    base = Path(out_dir) if out_dir else src.parent
    return base / (src.stem + suffix)


def _to_json(args):
    for src in map(Path, args.files):
        doc = read_zces(src)
        dst = _out_path(src, args.out_dir, '.json')
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(to_json(doc), encoding='utf-8')
        print(f'{src} -> {dst} ({len(doc["objects"])} objects)')


def _from_json(args):
    for src in map(Path, args.files):
        doc = from_json(src.read_text(encoding='utf-8'))
        dst = _out_path(src, args.out_dir, '.zces')
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = zces_bytes(doc)
        if not args.no_verify:
            read_zces_bytes(data)   # make sure the result parses again
        dst.write_bytes(data)
        print(f'{src} -> {dst}')


def _info(args):
    for src in map(Path, args.files):
        print(json.dumps({'file': str(src), **summary(read_zces(src))}, indent=2, ensure_ascii=False))


def _views(args):
    from .stage import load_stage
    for src in map(Path, args.files):
        if args.no_cds:
            cds = None
        elif args.cds:
            cds = args.cds
        else:
            cds = 'auto'
            if src.with_suffix('.cds').exists() and _cds_missing():
                print('note: pcm-cds-profile is not installed; using the .zces geometry for the profile',
                      file=sys.stderr)
        yield src, load_stage(src, cds)


def _cds_missing():
    try:
        import pcm_cds_profile  # noqa: F401
        return False
    except ImportError:
        return True


def _write(args, formats):
    from .stage import export_stage
    for src, view in _views(args):
        out = export_stage(view, args.out_dir or src.parent, src.stem, formats, args.theme)
        skipped = [f for f in formats if f not in out]
        note = f' (no real-world location: skipped {", ".join(skipped)})' if skipped else ''
        print(f'{src}: {view["distance_km"]:.1f} km, profile from {view["profile_source"]}{note}')
        for path in out.values():
            print(f'  {path}')


def _export(args):
    from .stage import FORMATS
    formats = list(FORMATS) if not args.only else [f.strip() for f in args.only.split(',') if f.strip()]
    _write(args, formats)


def _profile(args):
    _write(args, ['html'])


def _gpx(args):
    _write(args, [args.format])


def main(argv=None):
    p = argparse.ArgumentParser(prog='pcm-zces', description='Read, convert and visualise PCM .zces stage files.')
    sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('to-json', help='decode .zces files to JSON')
    a.add_argument('files', nargs='+')
    a.add_argument('-o', '--out-dir', help='output folder (default: next to each input)')
    a.set_defaults(func=_to_json)
    b = sub.add_parser('from-json', help='encode JSON files back to .zces')
    b.add_argument('files', nargs='+')
    b.add_argument('-o', '--out-dir', help='output folder (default: next to each input)')
    b.add_argument('--no-verify', action='store_true', help='skip re-reading the written data')
    b.set_defaults(func=_from_json)
    c = sub.add_parser('info', help='print stage name, versions and object counts')
    c.add_argument('files', nargs='+')
    c.set_defaults(func=_info)
    def stage_args(sp):
        sp.add_argument('files', nargs='+')
        sp.add_argument('-o', '--out-dir', help='output folder (default: next to each input)')
        sp.add_argument('--cds', help='.cds file for elevation and race points (default: STAGE.cds next to the input)')
        sp.add_argument('--no-cds', action='store_true', help='ignore the .cds file and use the .zces geometry only')
        sp.add_argument('--theme', choices=('light', 'dark'), default='light', help='colours of the SVG images')
    from .stage import FORMATS
    x = sub.add_parser('export', help='write the stage as HTML, SVG images, GeoJSON, GPX and a readable JSON summary')
    stage_args(x)
    x.add_argument('--only', help='comma-separated formats: ' + ', '.join(FORMATS))
    x.set_defaults(func=_export)
    d = sub.add_parser('profile', help='write the interactive HTML page (same as export --only html)')
    stage_args(d)
    d.set_defaults(func=_profile)
    e = sub.add_parser('gpx', help='export the route with real-world coordinates (GPX or GeoJSON)')
    stage_args(e)
    e.add_argument('--format', choices=('gpx', 'geojson'), default='gpx')
    e.set_defaults(func=_gpx)
    args = p.parse_args(argv)
    try:
        args.func(args)
    except (FormatError, OSError, ValueError, ImportError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
