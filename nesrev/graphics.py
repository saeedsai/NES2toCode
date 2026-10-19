"""CHR-ROM 2-bitplane tile extraction and PNG output, using standard library only."""
import struct
import zlib

DEFAULT_PALETTE = ((24, 25, 36), (80, 91, 120), (166, 184, 202), (252, 252, 247))


def decode_tile(data: bytes):
    if len(data) != 16:
        raise ValueError('A CHR tile is exactly 16 bytes')
    return [[((data[y] >> (7-x)) & 1) | (((data[8+y] >> (7-x)) & 1) << 1)
             for x in range(8)] for y in range(8)]


def encode_tile(tile):
    """Convert a decoded 8x8 tile back to its EXACT 16-byte CHR 2bpp representation."""
    if len(tile) != 8 or any(len(row) != 8 or any(x not in (0, 1, 2, 3) for x in row) for row in tile):
        raise ValueError('Expected 8x8 integers in range 0..3')
    plane0 = bytearray(8)
    plane1 = bytearray(8)
    for y in range(8):
        for x in range(8):
            plane0[y] |= (tile[y][x] & 1) << (7-x)
            plane1[y] |= ((tile[y][x] >> 1) & 1) << (7-x)
    return bytes(plane0 + plane1)


def iter_tiles(chr_data):
    for offset in range(0, len(chr_data) - len(chr_data) % 16, 16):
        yield decode_tile(chr_data[offset:offset + 16])


def _png_chunk(tag, payload):
    return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff)


def make_png(width, height, rows):
    if len(rows) != height or any(len(row) != width*3 for row in rows):
        raise ValueError('PNG row dimensions mismatch')
    raw = b''.join(b'\x00' + bytes(row) for row in rows)
    return (b'\x89PNG\r\n\x1a\n' + _png_chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 2, 0, 0, 0))
            + _png_chunk(b'IDAT', zlib.compress(raw, level=9)) + _png_chunk(b'IEND', b''))


def tile_png(tile, scale=4, palette=DEFAULT_PALETTE):
    rows = []
    for y in range(8):
        pixels = b''.join(bytes(palette[tile[y][x]]) * scale for x in range(8))
        rows.extend([pixels] * scale)
    return make_png(8*scale, 8*scale, rows)


def sheet_png(tiles, cols=16, scale=2, palette=DEFAULT_PALETTE):
    tiles = list(tiles)
    if not tiles:
        raise ValueError('No tiles in sheet')
    grid_rows = (len(tiles) + cols - 1) // cols
    width, height = cols*8*scale, grid_rows*8*scale
    rows = []
    for tile_y in range(grid_rows):
        for pix_y in range(8):
            rgb_line = bytearray()
            for tile_x in range(cols):
                index = tile_y*cols + tile_x
                tile = tiles[index] if index < len(tiles) else None
                for pix_x in range(8):
                    v = tile[pix_y][pix_x] if tile else 0
                    rgb_line.extend(bytes(palette[v]) * scale)
            rows.extend([bytes(rgb_line)] * scale)
    return make_png(width, height, rows)
