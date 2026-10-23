"""Container and stream primitives for PCM .zces stage files.

Every class serializer in `classes.py` is written once, as a function that
takes an `IO` object. In read mode the calls pull values from the byte stream
into a dict. In write mode the same calls take the values from the dict and
emit bytes. One description therefore drives both directions, and the reader
and writer cannot drift apart.
"""
import base64
import struct
import zlib

CHUNK_MAGIC = 0x12345678
OBJECT_MAGIC = 0xCEAD
CHUNK_SIZE = 0x500000


class FormatError(ValueError):
    """The data does not match the ZCES format."""


# ---------------------------------------------------------------- container
def unpack_container(data):
    """Return the decompressed archive bytes of a .zces file.

    Layout: u32 0, then zlib chunks, then a u32 0 terminator. Each chunk has
    a 20-byte header: u32 comp_size + 16, u32 raw_size, u32 comp_size, u32 0,
    u32 0x12345678.
    """
    if len(data) < 8 or struct.unpack_from('<I', data, 0)[0] != 0:
        raise FormatError('not a ZCES file (bad container prefix)')
    off, out = 4, []
    while off < len(data):
        if off + 4 == len(data) and struct.unpack_from('<I', data, off)[0] == 0:
            return b''.join(out)
        if off + 20 > len(data):
            break
        total, raw, comp, zero, magic = struct.unpack_from('<5I', data, off)
        if magic != CHUNK_MAGIC or total != comp + 16:
            raise FormatError(f'bad chunk header at {off:#x}')
        chunk = zlib.decompress(data[off + 20:off + 20 + comp])
        if len(chunk) != raw:
            raise FormatError(f'chunk at {off:#x}: expected {raw} bytes, got {len(chunk)}')
        out.append(chunk)
        off += 20 + comp
    raise FormatError('missing container terminator')


def pack_container(raw, chunk_size=CHUNK_SIZE, level=1):
    """Compress archive bytes into a .zces container (5 MiB chunks, zlib level 1
    like the game). The compressed bytes can differ from the game's own output,
    because it uses a different zlib build; the decompressed data is identical."""
    out = [b'\0\0\0\0']
    for i in range(0, len(raw), chunk_size):
        piece = raw[i:i + chunk_size]
        comp = zlib.compress(piece, level)
        out.append(struct.pack('<5I', len(comp) + 16, len(piece), len(comp), 0, CHUNK_MAGIC))
        out.append(comp)
    out.append(b'\0\0\0\0')
    return b''.join(out)


# ---------------------------------------------------------------- floats
def _f32_from_bits(b):
    """Finite floats become Python floats. NaN/inf keep their exact bit pattern
    (several files store uninitialised memory in float fields)."""
    if (b >> 23) & 0xff == 0xff:
        return {'f32bits': '%08x' % b}
    return struct.unpack('<f', struct.pack('<I', b))[0]


def _f32_bits(x):
    if isinstance(x, dict):
        return int(x['f32bits'], 16)
    return struct.unpack('<I', struct.pack('<f', x))[0]


# ---------------------------------------------------------------- stream IO
class IO:
    """Symmetric reader/writer. `d` is the dict currently being filled (read)
    or emitted (write). `av` is the archive version, `ver` the version of the
    object being processed and `flag` the archive flag."""

    def __init__(self, mode, data=b'', version=0, flag=1):
        self.mode = mode
        self.buf = data if mode == 'r' else bytearray()
        self.pos = 0
        self.av = version
        self.flag = flag
        self.ver = 0
        self.d = None

    @property
    def reading(self):
        return self.mode == 'r'

    # -- raw access
    def _rd(self, fmt):
        try:
            v = struct.unpack_from(fmt, self.buf, self.pos)
        except struct.error:
            raise FormatError(f'unexpected end of data at {self.pos:#x}') from None
        self.pos += struct.calcsize(fmt)
        return v

    def _wr(self, fmt, *v):
        self.buf += struct.pack(fmt, *v)

    def _need(self, n, what):
        if n > len(self.buf) - self.pos:
            raise FormatError(f'{what}: {n} bytes needed at {self.pos:#x}')

    # -- scalars and small vectors
    def prim(self, name, fmt, n=1):
        if fmt == 'f':
            return self._floats(name, n)
        if self.reading:
            v = self._rd('<' + (str(n) if n > 1 else '') + fmt)
            v = list(v) if n > 1 else v[0]
            self.d[name] = v
            return v
        v = self.d[name]
        if n > 1:
            self._wr('<' + str(n) + fmt, *v)
        else:
            self._wr('<' + fmt, v)
        return v

    def _floats(self, name, n):
        if self.reading:
            vals = [_f32_from_bits(b) for b in self._rd(f'<{n}I')]
            v = vals if n > 1 else vals[0]
            self.d[name] = v
            return v
        v = self.d[name]
        for x in (v if n > 1 else [v]):
            self._wr('<I', _f32_bits(x))
        return v

    def u8(self, n): return self.prim(n, 'B')
    def u16(self, n): return self.prim(n, 'H')
    def u32(self, n): return self.prim(n, 'I')
    def i32(self, n): return self.prim(n, 'i')
    def f32(self, n): return self.prim(n, 'f')
    def vec2(self, n): return self.prim(n, 'f', 2)
    def vec3(self, n): return self.prim(n, 'f', 3)
    def vec4(self, n): return self.prim(n, 'f', 4)
    def ivec2(self, n): return self.prim(n, 'i', 2)

    def ref(self, n):
        """Object reference: u32 object id, 0 = null (JSON null)."""
        if self.reading:
            v = self._rd('<I')[0]
            self.d[n] = v or None
            return v
        v = self.d[n] or 0
        self._wr('<I', v)
        return v

    def str(self, n):
        """u32 byte length + bytes, no terminator. Valid UTF-8 becomes a plain
        string; other text is kept as {"cp1252": ...} (or {"latin1": ...}) so
        the original bytes are written back unchanged."""
        if self.reading:
            ln = self._rd('<I')[0]
            self._need(ln, f'string {n}')
            s = bytes(self.buf[self.pos:self.pos + ln])
            self.pos += ln
            try:
                v = s.decode('utf-8')
            except UnicodeError:
                try:
                    v = {'cp1252': s.decode('cp1252')}
                except UnicodeError:
                    v = {'latin1': s.decode('latin1')}
            self.d[n] = v
            return v
        v = self.d[n]
        if isinstance(v, dict):
            b = v['cp1252'].encode('cp1252') if 'cp1252' in v else v['latin1'].encode('latin1')
        else:
            b = v.encode('utf-8')
        self._wr('<I', len(b))
        self.buf += b
        return v

    def raw(self, n, size):
        """Opaque bytes, stored as base64."""
        if self.reading:
            self._need(size, n)
            b = bytes(self.buf[self.pos:self.pos + size])
            self.pos += size
            self.d[n] = base64.b64encode(b).decode('ascii')
            return b
        b = base64.b64decode(self.d[n])
        if len(b) != size:
            raise FormatError(f'{n}: expected {size} bytes, got {len(b)}')
        self.buf += b
        return b

    # -- arrays
    def _flat(self, fmt, count):
        if not count:
            return []
        self._need(count * struct.calcsize(fmt), 'array')
        if fmt != 'f':
            return list(self._rd(f'<{count}{fmt}'))
        return [_f32_from_bits(b) for b in self._rd(f'<{count}I')]

    def _wflat(self, fmt, v):
        if not v:
            return
        if fmt == 'f':
            self._wr(f'<{len(v)}I', *[_f32_bits(x) for x in v])
        else:
            self._wr(f'<{len(v)}{fmt}', *v)

    def array(self, n, fmt, count):
        """Fixed-count numeric array (JSON list)."""
        if self.reading:
            self.d[n] = self._flat(fmt, count)
            return self.d[n]
        v = self.d[n]
        if len(v) != count:
            raise FormatError(f'{n}: expected {count} items, got {len(v)}')
        self._wflat(fmt, v)
        return v

    def rows(self, n, fmt, ncols, count):
        """`count` rows of `ncols` numbers of one type (list of lists)."""
        if self.reading:
            flat = self._flat(fmt, count * ncols)
            self.d[n] = [flat[i:i + ncols] for i in range(0, len(flat), ncols)]
            return self.d[n]
        v = self.d[n]
        if len(v) != count or any(len(r) != ncols for r in v):
            raise FormatError(f'{n}: bad row shape')
        self._wflat(fmt, [x for r in v for x in r])
        return v

    def table(self, n, cols, count):
        """`count` rows of 4-byte values with per-column types: 'f' float,
        'I' u32, 'i' i32 (list of lists)."""
        nc = len(cols)
        if self.reading:
            self._need(count * nc * 4, n)
            bits = self._rd(f'<{count * nc}I') if count else ()
            out = []
            for r in range(count):
                row = []
                for j, t in enumerate(cols):
                    b = bits[r * nc + j]
                    if t == 'f':
                        row.append(_f32_from_bits(b))
                    elif t == 'i':
                        row.append(b - (1 << 32) if b & 0x80000000 else b)
                    else:
                        row.append(b)
                out.append(row)
            self.d[n] = out
            return out
        v = self.d[n]
        if len(v) != count or any(len(r) != nc for r in v):
            raise FormatError(f'{n}: bad table shape')
        for row in v:
            for t, x in zip(cols, row):
                if t == 'f':
                    self._wr('<I', _f32_bits(x))
                else:
                    self._wr('<' + t, x)
        return v

    def ctable(self, n, cols, fmt='I'):
        """Table preceded by its row count."""
        return self.table(n, cols, self.count(n, fmt))

    # -- composites
    def count(self, n, fmt='I'):
        """Element count of list field `n` (implied by the list on write)."""
        if self.reading:
            c = self._rd('<' + fmt)[0]
            if c > len(self.buf) - self.pos:
                raise FormatError(f'count for {n} too large ({c}) at {self.pos:#x}')
            return c
        c = len(self.d[n])
        self._wr('<' + fmt, c)
        return c

    def list(self, n, fn, fmt='I', count=None):
        """List of structs; `fn(io)` handles one element."""
        c = self.count(n, fmt) if count is None else count
        parent = self.d
        if self.reading:
            items = []
            for _ in range(c):
                self.d = {}
                fn(self)
                items.append(self.d)
            parent[n] = items
        else:
            if count is not None and len(parent[n]) != count:
                raise FormatError(f'{n}: expected {count} items')
            for it in parent[n]:
                self.d = it
                fn(self)
        self.d = parent
        return c

    def vlist(self, n, elem, fmt='I', count=None):
        """List of single values; `elem` is a method name such as 'ref' or 'u32'."""
        c = self.count(n, fmt) if count is None else count
        parent = self.d
        get = getattr(self, elem)
        if self.reading:
            items = []
            for _ in range(c):
                self.d = {}
                get('v')
                items.append(self.d['v'])
            parent[n] = items
        else:
            for it in parent[n]:
                self.d = {'v': it}
                get('v')
        self.d = parent
        return c

    def sub(self, n, fn):
        """Embedded struct (not an archive object)."""
        parent = self.d
        if self.reading:
            self.d = {}
            fn(self)
            parent[n] = self.d
        else:
            self.d = parent[n]
            fn(self)
        self.d = parent

    def block(self, tag, fn, name):
        """Tagged block: u32 tag, u32 size, body. `size` counts from the size
        field itself; the engine skips to tell_after_tag + size when the tag is
        not the one it expects. The body's fields go into the dict `name`; a
        block with another tag is kept there as {"tag": ..., "raw": base64}."""
        parent = self.d
        if self.reading:
            t = self._rd('<I')[0]
            start = self.pos
            size = self._rd('<I')[0]
            if t != tag:
                if size < 4 or start + size > len(self.buf):
                    raise FormatError(f'bad block {t:#x} (expected {tag:#x}) at {start:#x}')
                parent[name] = {'tag': t, 'raw': base64.b64encode(
                    bytes(self.buf[start + 4:start + size])).decode('ascii')}
                self.pos = start + size
                return False
            self.d = {}
            fn(self)
            parent[name] = self.d
            self.d = parent
            if self.pos - start != size:
                raise FormatError(f'block {tag:#x}: size {size} but read {self.pos - start}')
            return True
        b = parent[name]
        if set(b) == {'tag', 'raw'}:
            body = base64.b64decode(b['raw'])
            self._wr('<II', b['tag'], len(body) + 4)
            self.buf += body
            return False
        self._wr('<I', tag)
        start = len(self.buf)
        self._wr('<I', 0)
        self.d = b
        fn(self)
        self.d = parent
        struct.pack_into('<I', self.buf, start, len(self.buf) - start)
        return True

    def marker(self, n, value):
        """Optional u32 marker, consumed only when it equals `value` (bool field)."""
        if self.reading:
            hit = (self.pos + 4 <= len(self.buf)
                   and struct.unpack_from('<I', self.buf, self.pos)[0] == value)
            if hit:
                self.pos += 4
            self.d[n] = hit
            return hit
        if self.d[n]:
            self._wr('<I', value)
        return self.d[n]
