#!/usr/bin/env python3
"""Fetch weather radar for Pensacola area, composite onto OSM map tiles.

Supports single-frame (default) or multi-frame animation output.

Usage:
    radar-fetch.py [outpath]                    # single latest frame
    radar-fetch.py --frames N [outdir]          # N most recent frames as separate PNGs
    radar-fetch.py --lat LAT --lon LON [...]    # custom center location
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
    """Fetch and stitch OSM base map tiles (parallel fetch)."""
    from concurrent.futures import ThreadPoolExecutor
    cx, cy = lat_lon_to_tile(center_lat, center_lon, ZOOM)
    tile_size = 256
    half = GRID // 2
    base = Image.new('RGB', (GRID * tile_size, GRID * tile_size), (170, 211, 223))

    base_url = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    tile_jobs = []
    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            tx, ty = cx + dx, cy + dy
            url = base_url.replace('{z}', str(ZOOM)).replace('{x}', str(tx)).replace('{y}', str(ty))
            px = (dx + half) * tile_size
            py = (dy + half) * tile_size
            tile_jobs.append((url, px, py))

    def fetch_and_pos(job):
        url, px, py = job
        tile = fetch_tile(url)
        return (tile, px, py)

    with ThreadPoolExecutor(max_workers=9) as pool:
        results = list(pool.map(fetch_and_pos, tile_jobs))

    for tile, px, py in results:
        if tile:
            tile = tile.convert('RGB')
            base.paste(tile, (px, py))

    return base, cx, cy


def lat_lon_to_pixel(lat, lon, cx, cy):
    """Convert lat/lon to pixel position on the composite image (before resize)."""
    tile_size = 256
    half = GRID // 2
    n = 2 ** ZOOM

    # Exact tile coordinates (floating point)
    x_tile = (lon + 180) / 360 * n
    lat_rad = math.radians(lat)
    y_tile = (1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n

    # Pixel position relative to top-left of composite
    px = (x_tile - (cx - half)) * tile_size
    py = (y_tile - (cy - half)) * tile_size
    return int(px), int(py)


def draw_crosshair(img, target_lat, target_lon, cx, cy):
    """Draw a yellow crosshair at the target location."""
    from PIL import ImageDraw

    # Get pixel position on the pre-resize composite
    composite_w, composite_h = GRID * 256, GRID * 256
    tx, ty = lat_lon_to_pixel(target_lat, target_lon, cx, cy)

    # Scale to output dimensions
    px = int(tx * OUT_W / composite_w)
    py = int(ty * OUT_H / composite_h)

    draw = ImageDraw.Draw(img)
    color = (255, 255, 0)  # bright yellow
    outline = (0, 0, 0)    # black outline for contrast
    size = 40  # arm length
    gap = 10   # gap around center

    # Draw crosshair arms with black outline for visibility
    for c, w in [(outline, 5), (color, 3)]:
        # Horizontal arms
        draw.line([(px - size, py), (px - gap, py)], fill=c, width=w)
        draw.line([(px + gap, py), (px + size, py)], fill=c, width=w)
        # Vertical arms
        draw.line([(px, py - size), (px, py - gap)], fill=c, width=w)
        draw.line([(px, py + gap), (px, py + size)], fill=c, width=w)

    # Center dot with outline
    draw.ellipse([(px - 5, py - 5), (px + 5, py + 5)], fill=outline)
    draw.ellipse([(px - 3, py - 3), (px + 3, py + 3)], fill=color)

    return img


def overlay_radar(base_img, radar_path, cx, cy, target_lat=None, target_lon=None):
    """Overlay radar tiles onto a copy of the base map (parallel fetch)."""
    from concurrent.futures import ThreadPoolExecutor
    composite = base_img.copy()
    tile_size = 256
    half = GRID // 2
    radar_url = 'https://tilecache.rainviewer.com{path}/256/{z}/{x}/{y}/2/1_0.png'

    # Build tile fetch list
    tile_jobs = []
    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            tx, ty = cx + dx, cy + dy
            url = (radar_url
                   .replace('{path}', radar_path)
                   .replace('{z}', str(ZOOM))
                   .replace('{x}', str(tx))
                   .replace('{y}', str(ty)))
            px = (dx + half) * tile_size
            py = (dy + half) * tile_size
            tile_jobs.append((url, px, py))

    # Fetch all tiles in parallel
    def fetch_and_pos(job):
        url, px, py = job
        tile = fetch_tile(url)
        return (tile, px, py)

    with ThreadPoolExecutor(max_workers=9) as pool:
        results = list(pool.map(fetch_and_pos, tile_jobs))

    for tile, px, py in results:
        if tile:
            tile = tile.convert('RGBA')
            composite.paste(tile, (px, py), tile)

    result = composite.resize((OUT_W, OUT_H), Image.LANCZOS)

    if target_lat is not None and target_lon is not None:
        result = draw_crosshair(result, target_lat, target_lon, cx, cy)

    return result


def get_radar_timestamps():
    """Get all available radar timestamps from RainViewer."""
    try:
        api_data = json.loads(urllib.request.urlopen(
            'https://api.rainviewer.com/public/weather-maps.json', timeout=10
        ).read())
        return api_data['radar']['past']
    except Exception:
        return []


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

    timestamps = get_radar_timestamps()
    if not timestamps:
        # No radar data — output bare base map
        result = base.resize((OUT_W, OUT_H), Image.LANCZOS)
        result.save(args.output if args.frames == 0 else os.path.join(args.output, 'frame_00.png'))
        return

    if args.frames > 0:
        # Multi-frame mode: generate N most recent frames
        frames = timestamps[-args.frames:]
        os.makedirs(args.output, exist_ok=True)

        for i, entry in enumerate(frames):
            radar_path = entry['path']
            ts = entry['time']
            composite = overlay_radar(base, radar_path, cx, cy, args.lat, args.lon)
            outfile = os.path.join(args.output, f'frame_{i:02d}.png')
            composite.save(outfile)
            # Write timestamp metadata
            print(f'{i}:{ts}:{outfile}')
    else:
        # Single frame: latest only
        radar_path = timestamps[-1]['path']
        composite = overlay_radar(base, radar_path, cx, cy, args.lat, args.lon)
        composite.save(args.output)


if __name__ == '__main__':
    main()
