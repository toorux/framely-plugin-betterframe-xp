#!/usr/bin/env python3
"""Generate the small geometric plugin icon without external dependencies."""
import pathlib
import struct
import zlib

size = 256
pixels = bytearray()
for y in range(size):
    pixels.append(0)
    for x in range(size):
        color = (18, 31, 40, 255)
        # Two lenses, each containing a soft/precise edge comparison.
        for cx in (73, 183):
            dx, dy = x - cx, y - 128
            r = dx * dx + dy * dy
            if r < 49 * 49:
                color = (34, 64, 78, 255)
            if 43 * 43 < r < 49 * 49:
                color = (112, 215, 233, 255)
            if r < 37 * 37 and abs(dy + dx // 2) < (7 if dx < 0 else 3):
                color = (105, 150, 165, 255) if dx < 0 else (221, 250, 255, 255)
        if 122 <= x <= 134 and 123 <= y <= 130:
            color = (112, 215, 233, 255)
        pixels.extend(color)


def chunk(kind, data):
    return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)


raw = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels, 9)) + chunk(b'IEND', b'')
pathlib.Path(__file__).resolve().parents[1].joinpath('icon.png').write_bytes(raw)
