#!/usr/bin/env python3
"""Fetch weather radar for Pensacola area, composite onto OSM map tiles."""

import json
import math
import sys
import urllib.request
from io import BytesIO
from PIL import Image

# Pensacola area bounding box
# Roughly: Panama City to Mobile, coast to ~50mi inland
CENTER_LAT = 30.45  # Pensacola
CENTER_LON = -86.2  # shifted east — less Louisiana, more FL panhandle
ZOOM = 7  # max supported by RainViewer free tier

# Output size (large source = more detail for chafa to render)
OUT_W = 1280
OUT_H = 800

# How many tiles to fetch (3x3 grid, zoom 8 for more detail)
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


def main():
    outpath = sys.argv[1] if len(sys.argv) > 1 else '/tmp/bbs-radar-composite.png'

    # Get center tile
    cx, cy = lat_lon_to_tile(CENTER_LAT, CENTER_LON, ZOOM)

    # Fetch OpenStreetMap standard tiles (colorful, good contrast for ANSI)
    base_url = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

    # Build base map from tile grid
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

    # Get latest radar timestamp from RainViewer
    try:
        api_data = json.loads(urllib.request.urlopen(
            'https://api.rainviewer.com/public/weather-maps.json', timeout=10
        ).read())
        radar_path = api_data['radar']['past'][-1]['path']
    except Exception:
        # No radar data, just output the base map
        base = base.resize((OUT_W, OUT_H), Image.LANCZOS)
        base.save(outpath)
        return

    # Fetch radar tiles and overlay
    # RainViewer tile URL: https://tilecache.rainviewer.com{path}/256/{z}/{x}/{y}/2/1_0.png
    radar_url = 'https://tilecache.rainviewer.com{path}/256/{z}/{x}/{y}/2/1_0.png'

    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            tx, ty = cx + dx, cy + dy
            url = radar_url.replace('{path}', radar_path).replace('{z}', str(ZOOM)).replace('{x}', str(tx)).replace('{y}', str(ty))
            tile = fetch_tile(url)
            if tile:
                tile = tile.convert('RGBA')
                px = (dx + half) * tile_size
                py = (dy + half) * tile_size
                base.paste(tile, (px, py), tile)  # alpha composite

    # Resize to output dimensions (full view — shows Gulf for hurricane tracking)
    full_w, full_h = base.size
    base = base.resize((OUT_W, OUT_H), Image.LANCZOS)

    base.save(outpath)


if __name__ == '__main__':
    main()
