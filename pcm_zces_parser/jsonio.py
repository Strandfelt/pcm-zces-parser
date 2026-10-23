"""Readable JSON output for decoded stages.

json.dumps(indent=...) puts every number of a 4225-sample heightmap on its own
line, so this module writes its own layout:

* objects and lists of objects are indented, one entry per line;
* lists of plain values stay on one line;
* lists of rows (vertices, tables) get one row per line;
* small flat dicts such as {"f32bits": "7fc00000"} stay inline.

Floats are written with the fewest digits that still round-trip to the same
32-bit float, so `1508.0418701171875` is written as `1508.0419`.
"""
import json
import struct

_pack = struct.Struct('<f').pack


def format_f32(x):
    """Shortest decimal text that parses back to the same f32."""
    if x == 0:
        return '-0.0' if str(x).startswith('-') else '0.0'
    target = _pack(x)
    for p in (6, 7, 8, 9):
        s = '%.*g' % (p, x)
        if _pack(float(s)) == target:
            break
    if '.' not in s and 'e' not in s:
        s += '.0'
    return s


_FLOAT = [None]   # set by dumps(): the float formatter in use


def _repr_float(x):
    s = repr(x)
    return s if ('.' in s or 'e' in s or 'n' in s) else s + '.0'


def _scalar(v):
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, float):
        return _FLOAT[0](v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    return None


def _inline_dict(d):
    if len(d) > 6:
        return None
    parts = []
    for k, v in d.items():
        s = _scalar(v)
        if s is None and isinstance(v, list) and len(v) <= 4:
            items = [_scalar(x) for x in v]
            if None not in items:
                s = '[' + ', '.join(items) + ']'
        if s is None:
            return None
        parts.append(json.dumps(k) + ': ' + s)
    out = '{' + ', '.join(parts) + '}'
    return out if len(out) <= 100 else None


def _flat(v):
    """Single-line text for a scalar, a small flat dict or a list of those."""
    s = _scalar(v)
    if s is not None:
        return s
    if isinstance(v, dict):
        return _inline_dict(v)
    if isinstance(v, list):
        items = []
        for x in v:
            t = _scalar(x)
            if t is None and isinstance(x, dict):
                t = _inline_dict(x)
            if t is None:
                return None
            items.append(t)
        return '[' + ', '.join(items) + ']'
    return None


def _write(v, out, ind, depth):
    pad = '  ' * (ind + 1)
    if isinstance(v, dict):
        if not v:
            out.append('{}')
            return
        if depth > 1:
            s = _inline_dict(v)
            if s is not None:
                out.append(s)
                return
        out.append('{\n')
        last = len(v) - 1
        for i, (k, x) in enumerate(v.items()):
            out.append(pad + json.dumps(k) + ': ')
            _write(x, out, ind + 1, depth + 1)
            out.append(',\n' if i < last else '\n')
        out.append('  ' * ind + '}')
        return
    if isinstance(v, list):
        if not v:
            out.append('[]')
            return
        s = _flat(v)
        if s is not None:
            out.append(s)
            return
        out.append('[\n')
        last = len(v) - 1
        for i, x in enumerate(v):
            out.append(pad)
            _write(x, out, ind + 1, depth + 1)
            out.append(',\n' if i < last else '\n')
        out.append('  ' * ind + ']')
        return
    s = _scalar(v)
    if s is None:
        raise TypeError(f'cannot write {type(v).__name__} to JSON')
    out.append(s)


def dumps(doc, floats='f32'):
    """Readable JSON text. floats='f32' writes the shortest text that keeps the
    32-bit value (game data); floats='exact' writes Python's repr (e.g. GPS)."""
    _FLOAT[0] = format_f32 if floats == 'f32' else _repr_float
    out = []
    _write(doc, out, 0, 0)
    out.append('\n')
    return ''.join(out)


def loads(text):
    return json.loads(text)
