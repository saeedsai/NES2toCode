"""CLI for exporting raw NES cartridge content and preliminary reverse-engineering files."""
import argparse
import json
import sys
from pathlib import Path
from .rom import read_rom
from .exporter import export_rom


def main(argv=None):
    p = argparse.ArgumentParser(description='Extract and lift an iNES/NES 2.0 .nes cartridge')
    p.add_argument('rom', type=Path, help='Path to headered .nes file')
    p.add_argument('--out', type=Path, help='Output directory; default <romname>_recovered')
    p.add_argument('--scale', type=int, default=2, choices=(1, 2, 3, 4, 5, 6, 8), help='PNG tile pixel scaling')
    p.add_argument('--individual-tiles', action='store_true', help='Create a PNG for each 8x8 CHR tile')
    args = p.parse_args(argv)
    try:
        rom = read_rom(args.rom)
        output = args.out or Path(args.rom.stem + '_recovered')
        manifest = export_rom(rom, output, scale=args.scale,
                              individual_tiles=args.individual_tiles)
        print(json.dumps(dict(output=str(output), mapper=rom.mapper,
                              instructions=manifest['static_instruction_count'],
                              chr_tiles=manifest['tile_count'],
                              round_trip_exact=manifest['round_trip_exact']), indent=2))
    except (ValueError, OSError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
