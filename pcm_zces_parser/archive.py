"""Object archive: the decompressed payload of a .zces file.

    u32 version            archive version (0x70..0x86 in PCM 26 files)
    u32 flag               1 in game files
    u32 object_count
    object_count x str     class name of each object; ids are 1..object_count
    u32 root_count
    root_count x u32       root object ids ([1], the CTStage)
    object data, in id order

Every object starts with a u16 class version and the u16 magic 0xCEAD,
except the classes in NO_HEADER, whose loader skips the base header.
"""
import struct

from .classes import CLASSES, NO_HEADER
from .stream import IO, OBJECT_MAGIC, FormatError

FORMAT_NAME = 'pcm-zces'
FORMAT_VERSION = 1


def _header(io, cls):
    if cls in NO_HEADER:
        io.ver = 0
        return
    if io.reading:
        ver, magic = io._rd('<HH')
        if magic != OBJECT_MAGIC:
            raise FormatError(f'bad object magic {magic:#06x} at {io.pos - 4:#x}')
        io.d['class_version'] = ver
    else:
        io._wr('<HH', io.d['class_version'], OBJECT_MAGIC)
    io.ver = io.d['class_version']


def read_archive(raw, strict=True):
    """Parse decompressed archive bytes into a JSON-ready dict."""
    if len(raw) < 12:
        raise FormatError('archive too short')
    version, flag, n = struct.unpack_from('<3I', raw, 0)
    io = IO('r', raw, version, flag)
    io.pos = 12
    names = []
    for _ in range(n):
        ln = io._rd('<I')[0]
        io._need(ln, 'class name')
        names.append(raw[io.pos:io.pos + ln].decode('latin1'))
        io.pos += ln
    nr = io._rd('<I')[0]
    roots = list(io._rd(f'<{nr}I')) if nr else []
    objects = []
    for i, cls in enumerate(names):
        fn = CLASSES.get(cls)
        if fn is None:
            raise FormatError(f'unsupported class {cls} (object {i + 1})')
        start = io.pos
        obj = {'id': i + 1, 'class': cls}
        io.d = obj
        _header(io, cls)
        fn(io)
        io.d = obj
        if strict and i + 1 < n and names[i + 1] not in NO_HEADER \
                and raw[io.pos + 2:io.pos + 4] != b'\xad\xce':
            raise FormatError(f'object {i + 1} ({cls}, class version {io.ver}) does not end on '
                              f'an object boundary (start {start:#x}, end {io.pos:#x})')
        objects.append(obj)
    if io.pos != len(raw):
        raise FormatError(f'{len(raw) - io.pos} trailing bytes after the last object')
    return {'format': FORMAT_NAME, 'format_version': FORMAT_VERSION,
            'archive_version': version, 'flag': flag, 'roots': roots, 'objects': objects}


def write_archive(doc):
    """Serialize a dict from read_archive back to archive bytes."""
    if doc.get('format') != FORMAT_NAME:
        raise FormatError('not a pcm-zces document')
    objs = doc['objects']
    io = IO('w', version=doc['archive_version'], flag=doc.get('flag', 1))
    io._wr('<3I', doc['archive_version'], doc.get('flag', 1), len(objs))
    for o in objs:
        b = o['class'].encode('latin1')
        io._wr('<I', len(b))
        io.buf += b
    io._wr('<I', len(doc['roots']))
    for r in doc['roots']:
        io._wr('<I', r)
    for i, o in enumerate(objs):
        if o['id'] != i + 1:
            raise FormatError(f'object ids must be 1..n in order (found {o["id"]} at position {i + 1})')
        fn = CLASSES.get(o['class'])
        if fn is None:
            raise FormatError(f'unsupported class {o["class"]}')
        io.d = o
        _header(io, o['class'])
        try:
            fn(io)
        except KeyError as e:
            raise FormatError(f'object {o["id"]} ({o["class"]}): missing field {e}') from None
    return bytes(io.buf)
