"""Generate docs/classes.md: the fields of every class, as seen in real files.

    python tools/make_class_docs.py STAGE_FOLDER [step]

Fields that depend on the archive or class version only show up when a
sampled file has them; pcm_zces_parser/classes.py is the full reference.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pcm_zces_parser import archive, classes                     # noqa: E402
from pcm_zces_parser.stream import IO, unpack_container           # noqa: E402
from pcm_zces_parser.jsonio import format_f32                     # noqa: E402

KINDS = {'u8': 'u8', 'u16': 'u16', 'u32': 'u32', 'i32': 'i32', 'f32': 'f32', 'vec2': 'f32[2]',
         'vec3': 'f32[3]', 'vec4': 'f32[4]', 'ivec2': 'i32[2]', 'ref': 'ref', 'str': 'string'}


class RecIO(IO):
    """Reading IO that records (path, type) for every field."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.path = []
        self.seen = None

    def _rec(self, name, kind):
        if self.seen is not None:
            key = '.'.join(self.path + [name])
            self.seen.setdefault(key, [kind, self.d.get(name) if isinstance(self.d, dict) else None])

    def _wrap(meth, kind):
        def f(self, n, *a, **k):
            r = getattr(IO, meth)(self, n, *a, **k)
            self._rec(n, kind)
            return r
        return f

    for _m, _k in KINDS.items():
        locals()[_m] = _wrap(_m, _k)

    def raw(self, n, size):
        r = IO.raw(self, n, size)
        self._rec(n, f'bytes[{size:#x}] (base64)')
        return r

    def array(self, n, fmt, count):
        r = IO.array(self, n, fmt, count)
        self._rec(n, f'{ {"f": "f32", "I": "u32", "H": "u16"}[fmt] }[n]')
        return r

    def rows(self, n, fmt, ncols, count):
        r = IO.rows(self, n, fmt, ncols, count)
        self._rec(n, f'rows of {ncols} x {"f32" if fmt == "f" else "u32"}')
        return r

    def table(self, n, cols, count):
        r = IO.table(self, n, cols, count)
        self._rec(n, 'rows of [' + ', '.join({'f': 'f32', 'I': 'u32', 'i': 'i32'}[c] for c in cols) + ']')
        return r

    def marker(self, n, value):
        r = IO.marker(self, n, value)
        self._rec(n, f'bool (optional u32 marker {value:#x})')
        return r

    def list(self, n, fn, fmt='I', count=None):
        self._rec(n, 'list' if count is None else f'list[{count}]')
        self.path.append(n + '[]')
        try:
            return IO.list(self, n, fn, fmt, count)
        finally:
            self.path.pop()

    def vlist(self, n, elem, fmt='I', count=None):
        saved, self.seen = self.seen, None
        try:
            r = IO.vlist(self, n, elem, fmt, count)
        finally:
            self.seen = saved
        self._rec(n, f'list of {KINDS.get(elem, elem)}')
        return r

    def sub(self, n, fn):
        self._rec(n, 'struct')
        self.path.append(n)
        try:
            return IO.sub(self, n, fn)
        finally:
            self.path.pop()

    def block(self, tag, fn, name):
        self._rec(name, f'tagged block {tag:#x}')
        self.path.append(name)
        try:
            return IO.block(self, tag, fn, name)
        finally:
            self.path.pop()


def example(v):
    if isinstance(v, float):
        return format_f32(v)
    if isinstance(v, list):
        if len(v) > 4 or not all(isinstance(x, (int, float)) for x in v):
            return None
        return '[' + ', '.join(format_f32(x) if isinstance(x, float) else str(x) for x in v) + ']'
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 60 else None


def main():
    folder = Path(sys.argv[1])
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    fields = collections.defaultdict(dict)
    counts = collections.Counter()
    for path in sorted(folder.glob('*.zces'))[::step]:
        raw = unpack_container(path.read_bytes())
        import struct
        version, flag, n = struct.unpack_from('<3I', raw, 0)
        io = RecIO('r', raw, version, flag)
        io.pos = 12
        names = []
        for _ in range(n):
            ln = io._rd('<I')[0]
            names.append(raw[io.pos:io.pos + ln].decode('latin1'))
            io.pos += ln
        nr = io._rd('<I')[0]
        io._rd(f'<{nr}I')
        per_file = collections.Counter()
        for i, cls in enumerate(names):
            obj = {'id': i + 1, 'class': cls}
            io.d = obj
            per_file[cls] += 1
            io.seen = fields[cls] if per_file[cls] <= 50 else None
            if io.seen is not None and cls not in classes.NO_HEADER:
                io.seen.setdefault('class_version', ['u16', None])
            archive._header(io, cls)
            if io.seen is not None and 'class_version' in obj and io.seen['class_version'][1] is None:
                io.seen['class_version'][1] = obj['class_version']
            classes.CLASSES[cls](io)
        counts.update(per_file)
    out = ['# Class reference', '',
           'Generated by `tools/make_class_docs.py` from real stage files. Every object',
           'also has `id`, `class` and (except where noted) `class_version`. `ref` fields',
           'hold the id of another object, or null. Field order is the order in the file.',
           'Fields that only exist in some archive or class versions are listed when a',
           'sampled file had them; `pcm_zces_parser/classes.py` has the exact conditions.', '']
    for cls in sorted(fields):
        out += [f'## {cls}', '']
        if cls in classes.NO_HEADER:
            out += ['No `class_version` / 0xCEAD header.', '']
        out += ['| Field | Type | Example |', '|---|---|---|']
        for k, (kind, v) in fields[cls].items():
            ex = example(v) if not kind.startswith(('list', 'struct', 'rows', 'tagged', 'bytes')) else None
            out.append(f'| `{k}` | {kind} | {("`" + ex + "`") if ex else ""} |')
        out.append('')
    Path(__file__).resolve().parents[1].joinpath('docs', 'classes.md').write_text('\n'.join(out), encoding='utf-8')
    print(len(fields), 'classes')


if __name__ == '__main__':
    main()
