import os
import struct
import unittest
from pathlib import Path

from pcm_zces_parser import (FormatError, from_json, pack_container, read_archive, read_zces_bytes, to_json,
                      unpack_container, write_archive, zces_bytes)
from pcm_zces_parser.jsonio import format_f32

STAGES = Path(os.environ.get(
    'PCM_ZCES_STAGES',
    r'C:\Program Files (x86)\Steam\steamapps\workshop\content\3936530\3749668860\Stages'))


def tiny_doc():
    """Hand-built archive with a route and its descriptor."""
    return {
        'format': 'pcm-zces', 'format_version': 1, 'archive_version': 131, 'flag': 1, 'roots': [1],
        'objects': [
            {'id': 1, 'class': 'CTRoute', 'class_version': 0, 'route_descriptor': 2,
             'f_0x7a': 1, 'f_0x7c': [0.5, {'f32bits': '7fa00001'}]},
            {'id': 2, 'class': 'CTRouteDescriptor', 'class_version': 0, 'points': [3, None]},
            {'id': 3, 'class': 'CTStageInfo', 'class_version': 3, 'name': 'Bogotá',
             'region': {'cp1252': 'Côte'}, 'region_id': -1, 'f_0x70': -1,
             'f_0x80': 1.0, 'f_0x84': 2.0, 'f_0x8c': 0, 'f_0x88': 0, 'f_0x90': 0,
             'f_0x68': -1, 'f_0x74': -1.0, 'f_0x78': -1, 'f_0x7c': -0.0},
        ],
    }


class SyntheticTests(unittest.TestCase):
    def test_container_round_trip(self):
        raw = bytes(range(256)) * 50000          # > one 5 MiB chunk
        packed = pack_container(raw)
        self.assertEqual(unpack_container(packed), raw)
        self.assertEqual(struct.unpack_from('<I', packed, 4 + 16)[0], 0x12345678)

    def test_archive_round_trip(self):
        doc = tiny_doc()
        raw = write_archive(doc)
        back = read_archive(raw)
        self.assertEqual(write_archive(back), raw)
        self.assertEqual(back['objects'][1]['points'], [3, None])
        self.assertEqual(back['objects'][2]['region'], {'cp1252': 'Côte'})
        self.assertEqual(back['objects'][0]['f_0x7c'][1], {'f32bits': '7fa00001'})

    def test_json_round_trip(self):
        data = zces_bytes(tiny_doc())
        doc = read_zces_bytes(data)
        self.assertEqual(write_archive(from_json(to_json(doc))), unpack_container(data))

    def test_float_text(self):
        for bits in (0x3f800000, 0x44bc0157, 0x00000001, 0x80000000, 0x7f7fffff, 0x3dcccccd):
            x = struct.unpack('<f', struct.pack('<I', bits))[0]
            s = format_f32(x)
            self.assertEqual(struct.unpack('<I', struct.pack('<f', float(s)))[0], bits, s)
        self.assertEqual(format_f32(1508.0418701171875), '1508.0419')

    def test_rejects_garbage(self):
        with self.assertRaises(FormatError):
            read_zces_bytes(b'\x01\x02\x03\x04' * 8)
        raw = bytearray(write_archive(tiny_doc()))
        raw += b'\0'
        with self.assertRaises(FormatError):
            read_archive(bytes(raw))


@unittest.skipUnless(STAGES.is_dir(), 'stage folder not found (set PCM_ZCES_STAGES)')
class GameFileTests(unittest.TestCase):
    def files(self, step):
        return sorted(STAGES.glob('*.zces'))[::step]

    def test_round_trip_sample(self):
        for path in self.files(int(os.environ.get('PCM_ZCES_STEP', '200'))):
            with self.subTest(path.name):
                raw = unpack_container(path.read_bytes())
                doc = read_archive(raw)
                self.assertEqual(write_archive(from_json(to_json(doc))), raw)
                self.assertEqual(doc['objects'][0]['class'], 'CTStage')


@unittest.skipUnless((STAGES / 'topclas_rondevv_2026.zces').is_file(), 'Ronde van Vlaanderen stage not found')
class ProfileTests(unittest.TestCase):
    def test_profile_page(self):
        from pcm_zces_parser import read_zces
        from pcm_zces_parser.profile_page import profile_html
        from pcm_zces_parser.route import stage_view
        doc = read_zces(STAGES / 'topclas_rondevv_2026.zces')
        try:
            import pcm_cds_profile
            cds = pcm_cds_profile.read_cds(STAGES / 'topclas_rondevv_2026.cds')
        except ImportError:
            cds = None
        view = stage_view(doc, cds)
        self.assertEqual(view['name'], 'Antwerpen - Oudenaarde')
        self.assertAlmostEqual(view['distance_km'], 271.9, delta=0.5 if cds else 6)
        if cds:
            self.assertEqual(view['profile_source'], 'cds')
        names = {e['name'] for e in view['events'] if e['kind'] == 'cobbles'}
        self.assertIn('Paterberg', names)
        self.assertIn('Koppenberg', names)
        page = profile_html(view, 'topclas_rondevv_2026.zces')
        self.assertTrue(page.startswith('<!doctype html>'))
        self.assertIn('"Oude Kwaremont"', page)
        self.assertIn('leaflet.js', page)
        self.assertNotIn('leaflet.js', profile_html(view, standalone=False))

        # real-world position: starts in Antwerp, finishes in Oudenaarde (town centres)
        import json
        from pcm_zces_parser.geo import geojson_text, gpx_text
        self.assertTrue(view['geo'])
        route = json.loads(geojson_text(view))['features'][0]['geometry']['coordinates']

        def km_from(p, lat, lon):
            import math
            return math.hypot((p[1] - lat) * 111.2, (p[0] - lon) * 111.2 * math.cos(math.radians(lat)))
        self.assertLess(km_from(route[0], 51.2194, 4.4025), 2.5)
        self.assertLess(km_from(route[-1], 50.8467, 3.6036), 2.0)
        gpx = gpx_text(view)
        self.assertIn('<trkpt lat="51.2', gpx)
        self.assertIn('Paterberg', gpx)

    def test_placeholder_location(self):
        from pcm_zces_parser import read_zces
        from pcm_zces_parser.route import gps_transform
        path = STAGES / 't1_taihu_01_2018.zces'
        if path.is_file():
            self.assertIsNone(gps_transform(read_zces(path)))

    def test_load_and_export(self):
        import json
        import tempfile
        from pcm_zces_parser import export_stage, load_stage
        view = load_stage(STAGES / 'topclas_rondevv_2026.zces')
        with tempfile.TemporaryDirectory() as tmp:
            out = export_stage(view, tmp)
            self.assertEqual(set(out), {'html', 'profile-svg', 'map-svg', 'json', 'geojson', 'gpx'})
            report = json.loads(out['json'].read_text(encoding='utf-8'))
        self.assertEqual(report['stage']['name'], 'Antwerpen - Oudenaarde')
        self.assertIn('Koppenberg', {s['name'] for s in report['sectors']})


def synthetic_view(geo=True):
    """A small made-up stage: 20 km, one climb with a KOM, one cobbled sector."""
    from pcm_zces_parser.route import _finish_events, gradients
    samples = []
    for i in range(101):
        km = i * 0.2
        alt = 100 + (300 * min(1, max(0, (km - 8) / 4)) if km < 12 else 300 - 25 * (km - 12))
        row = [round(km, 3), round(alt, 1), 1000 + i * 15.0, 2000 + (i % 30) * 6.0]
        if geo:
            row += [round(45.0 + i * 0.001, 6), round(6.0 + i * 0.0015, 6)]
        samples.append(row)
    events = [{'kind': 'start', 'km': 0.0, 'name': 'Alpha', 'code': 0},
              {'kind': 'climb', 'km': 8.0, 'end_km': 12.0, 'name': 'Col Test', 'avg': 7.5, 'max': 10.2},
              {'kind': 'kom', 'km': 12.0, 'name': 'Col Test', 'code': 2},
              {'kind': 'cobbles', 'km': 14.0, 'end_km': 15.2, 'name': 'Secteur <1>', 'stars': 4},
              {'kind': 'sprint', 'km': 16.0, 'name': 'Gamma', 'code': 14},
              {'kind': 'finish', 'km': 20.0, 'name': '', 'code': 7, 'summit': False}]
    _finish_events(events, 'Alpha - Omega')
    alts = [r[1] for r in samples]
    return {'name': 'Alpha - Omega', 'region': 'Testland', 'distance_km': 20.0, 'profile_source': 'zces',
            'max_alt': max(alts), 'min_alt': min(alts), 'gain_m': 300, 'samples': samples,
            'gradients': gradients(samples), 'events': events,
            'roads': [[1000, 2000, 1500, 2100, 2000, 2050]], 'geo': geo, 'source_file': 'test.zces'}


class ExportTests(unittest.TestCase):
    def test_svgs_are_valid_xml(self):
        import xml.etree.ElementTree as ET
        from pcm_zces_parser import map_svg, profile_svg
        for geo in (True, False):
            for theme in ('light', 'dark'):
                view = synthetic_view(geo)
                for svg in (profile_svg(view, theme=theme), map_svg(view, theme=theme)):
                    root = ET.fromstring(svg)
                    self.assertTrue(root.tag.endswith('svg'))
                self.assertIn('Col Test', profile_svg(view))
                self.assertIn('Secteur &lt;1&gt;', profile_svg(view))

    def test_kom_attached_and_finish_named(self):
        view = synthetic_view()
        climb = next(e for e in view['events'] if e['kind'] == 'climb')
        self.assertEqual(climb['kom']['code'], 2)
        self.assertEqual(next(e for e in view['events'] if e['kind'] == 'finish')['name'], 'Omega')
        self.assertGreater(max(view['gradients']), 5)

    def test_report(self):
        import json
        from pcm_zces_parser import stage_report, stage_report_json
        view = synthetic_view()
        rep = json.loads(stage_report_json(view))
        self.assertEqual(rep, json.loads(json.dumps(stage_report(view))))
        self.assertEqual(rep['climbs'][0]['kom_category_code'], 2)
        self.assertEqual(rep['sectors'][0]['difficulty_stars'], 4)
        self.assertEqual(len(rep['profile']), 101)
        self.assertEqual(rep['profile'][-1]['lat'], 45.1)
        self.assertIsNone(stage_report(synthetic_view(geo=False))['stage']['location'])

    def test_geojson_and_gpx(self):
        import xml.etree.ElementTree as ET
        from pcm_zces_parser import geojson, gpx_text
        view = synthetic_view()
        fc = geojson(view)
        kinds = [f['properties']['kind'] for f in fc['features']]
        self.assertEqual(kinds[0], 'route')
        self.assertIn('cobbles', kinds)
        self.assertNotIn('kom', kinds)                 # merged into its climb
        self.assertEqual(fc['features'][0]['geometry']['coordinates'][0], [6.0, 45.0, 100.0])
        ET.fromstring(gpx_text(view))
        with self.assertRaises(ValueError):
            geojson(synthetic_view(geo=False))

    def test_export_skips_geo_formats_without_location(self):
        import tempfile
        from pcm_zces_parser import export_stage
        with tempfile.TemporaryDirectory() as tmp:
            out = export_stage(synthetic_view(geo=False), tmp, 'x')
            self.assertEqual(set(out), {'html', 'profile-svg', 'map-svg', 'json'})
            self.assertTrue(all(p.name.startswith('x.') for p in out.values()))
            with self.assertRaises(ValueError):
                export_stage(synthetic_view(), tmp, 'x', formats=['png'])


if __name__ == '__main__':
    unittest.main()
