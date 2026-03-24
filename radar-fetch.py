#!/usr/bin/env python3
"""Fetch weather radar, composite onto OSM map tiles.

Supports single-frame (default) or multi-frame animation output.
"""

import json
import math
import os
import sys
import urllib.request
from io import BytesIO
from PIL import Image

# Defaults — Pensacola area
DEFAULT_LAT = 30.45
DEFAULT_LON = -86.2
ZOOM = 7
OUT_W = 1280
OUT_H = 800
GRID = 3


def lat_lon_to_tile(lat, lon, zoom):
    """Convert lat/lon to tile coordinates."""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    lat_rad = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    return x, y


def fetch_tile(url):
    """Download a tile image."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'BBS-Radar/1.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        return Image.open(BytesIO(resp.read()))
    except Exception:
        return None


def build_base_map(center_lat, center_lon):
    """Fetch and stitch OSM base map tiles."""
    cx, cy = lat_lon_to_tile(center_lat, center_lon, ZOOM)
    base_url = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    tile_size = 256
    half = GRID // 2
    base = Image.new('RGB', (GRID * tile_size, GRID * tile_size), (170, 211, 223))

    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            tx, ty = cx + dx, cy + dy
            url = base_url.replace('{z}', str(ZOOM)).replace('{x}', str(tx)).replace('{y}', str(ty))
            tile = fetch_tile(url)
            if tile:
                tile = tile.convert('RGB')
                px = (dx + half) * tile_size
                py = (dy + half) * tile_size
                base.paste(tile, (px, py))

    return base, cx, cy


def overlay_radar(base_img, radar_path, cx, cy):
    """Overlay radar tiles onto a copy of the base map."""
    composite = base_img.copy()
    tile_size = 256
    half = GRID // 2
    radar_url = 'https://tilecache.rainviewer.com{path}/256/{z}/{x}/{y}/2/1_0.png'

    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            tx, ty = cx + dx, cy + dy
            url = (radar_url
                   .replace('{path}', radar_path)
                   .replace('{z}', str(ZOOM))
                   .replace('{x}', str(tx))
                   .replace('{y}', str(ty)))
            tile = fetch_tile(url)
            if tile:
                tile = tile.convert('RGBA')
                px = (dx + half) * tile_size
                py = (dy + half) * tile_size
                composite.paste(tile, (px, py), tile)  # alpha composite

    return composite.resize((OUT_W, OUT_H), Image.LANCZOS)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fetch weather radar composites')
    parser.add_argument('output', nargs='?', default='/tmp/bbs-radar-composite.png',
                        help='Output path (file for single, directory for --frames)')
    parser.add_argument('--frames', type=int, default=0,
                        help='Number of animation frames to generate (0=single latest)')
    parser.add_argument('--lat', type=float, default=DEFAULT_LAT, help='Center latitude')
    parser.add_argument('--lon', type=float, default=DEFAULT_LON, help='Center longitude')
    args = parser.parse_args()

    # Build base map (fetched once, reused for all frames)
    base, cx, cy = build_base_map(args.lat, args.lon)

    # Get radar timestamps
    try:
        api_data = json.loads(urllib.request.urlopen(
            'https://api.rainviewer.com/public/weather-maps.json', timeout=10
        ).read())
        timestamps = api_data['radar']['past']
    except Exception:
        timestamps = []

    if not timestamps:
        result = base.resize((OUT_W, OUT_H), Image.LANCZOS)
        if args.frames > 0:
            os.makedirs(args.output, exist_ok=True)
            result.save(os.path.join(args.output, 'frame_00.png'))
            print(f'0:0:{os.path.join(args.output, "frame_00.png")}')
        else:
            result.save(args.output)
        return

    if args.frames > 0:
        frames = timestamps[-args.frames:]
        os.makedirs(args.output, exist_ok=True)

        for i, entry in enumerate(frames):
            radar_path = entry['path']
            ts = entry['time']
            composite = overlay_radar(base, radar_path, cx, cy)
            outfile = os.path.join(args.output, f'frame_{i:02d}.png')
            composite.save(outfile)
            print(f'{i}:{ts}:{outfile}')
    else:
        radar_path = timestamps[-1]['path']
        composite = overlay_radar(base, radar_path, cx, cy)
        composite.save(args.output)


if __name__ == '__main__':
    main()
