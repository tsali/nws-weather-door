#!/usr/bin/env python3
"""ANSI Weather Door for BBS PCOLA.

Interactive weather display with ANSI graphics for Mystic BBS.
Shows current conditions, forecast, marine conditions, and alerts
for the Pensacola area.

Called from Mystic menu as: /mystic/doors/weather/weather-door.sh
"""

import argparse
import io
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# Force stdout to binary-safe mode (CP437 box-drawing chars must go out as raw bytes)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='latin-1', errors='replace')
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='latin-1', errors='replace')

# NWS API settings
NWS_UA = 'BBS-PCOLA-WeatherDoor/1.0 (spectrumnet@cultofjames.org)'
NWS_HEADERS = {'User-Agent': NWS_UA, 'Accept': 'application/geo+json'}

# Pensacola area locations
LOCATIONS = {
    '1': ('Pensacola',         30.4213, -87.2169),
    '2': ('Gulf Breeze',       30.3571, -87.1672),
    '3': ('Pensacola Beach',   30.3318, -87.1364),
    '4': ('Navarre',           30.4019, -86.8639),
    '5': ('Fort Walton Beach', 30.4058, -86.6187),
}

# ANSI color codes
RST = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'
# Foreground
BLACK = '\033[30m'
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BLUE = '\033[34m'
MAGENTA = '\033[35m'
CYAN = '\033[36m'
WHITE = '\033[37m'
BRIGHT_RED = '\033[1;31m'
BRIGHT_GREEN = '\033[1;32m'
BRIGHT_YELLOW = '\033[1;33m'
BRIGHT_BLUE = '\033[1;34m'
BRIGHT_MAGENTA = '\033[1;35m'
BRIGHT_CYAN = '\033[1;36m'
BRIGHT_WHITE = '\033[1;37m'
# Background
BG_BLUE = '\033[44m'
BG_BLACK = '\033[40m'

# Box drawing characters (CP437 compatible)
TL = '\xda'  # top-left
TR = '\xbf'  # top-right
BL = '\xc0'  # bottom-left
BR = '\xd9'  # bottom-right
HZ = '\xc4'  # horizontal
VT = '\xb3'  # vertical
LT = '\xc3'  # left-T
RT = '\xb4'  # right-T
TT = '\xc2'  # top-T
BT = '\xc1'  # bottom-T
BLK_FULL = '\xdb'  # full block
BLK_HALF = '\xdd'  # half block

WIDTH = 78


def out(text=''):
    """Write text to stdout (user's terminal)."""
    sys.stdout.write(text)
    sys.stdout.flush()


def outln(text=''):
    """Write line to stdout."""
    out(text + '\r\n')


def fetch_json(url):
    """Fetch JSON from URL with NWS headers."""
    req = urllib.request.Request(url, headers=NWS_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def geolocate_ip(ip_addr):
    """Geolocate an IP address to city/lat/lon using ip-api.com (free, no key)."""
    if not ip_addr or ip_addr in ('127.0.0.1', '::1', '0.0.0.0', 'localhost'):
        return None
    try:
        url = f'http://ip-api.com/json/{ip_addr}?fields=status,city,regionName,lat,lon'
        req = urllib.request.Request(url, headers={'User-Agent': NWS_UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data.get('status') == 'success':
            city = data.get('city', '')
            region = data.get('regionName', '')
            name = f'{city}, {region}' if region else city
            return {
                'name': name,
                'lat': data['lat'],
                'lon': data['lon'],
            }
    except Exception:
        pass
    return None


def search_location(query):
    """Search for a location by city name or postal code using NWS + geocoding."""
    # Try as US zip code first (5 digits)
    query = query.strip()
    if query.isdigit() and len(query) == 5:
        try:
            url = f'https://geocoding-api.open-meteo.com/v1/search?name={query}&count=5&language=en&format=json'
            req = urllib.request.Request(url, headers={'User-Agent': NWS_UA})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            results = data.get('results', [])
            if results:
                r = results[0]
                admin = r.get('admin1', '')
                name = f'{r["name"]}, {admin}' if admin else r['name']
                return {'name': name, 'lat': r['latitude'], 'lon': r['longitude']}
        except Exception:
            pass

    # Try as city name via open-meteo geocoding
    try:
        encoded = urllib.request.quote(query)
        url = f'https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=10&language=en&format=json'
        req = urllib.request.Request(url, headers={'User-Agent': NWS_UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        results = data.get('results', [])
        if not results:
            return None
        # Return list for user to pick from
        picks = []
        for r in results:
            admin = r.get('admin1', '')
            country = r.get('country', '')
            name = r['name']
            if admin:
                name += f', {admin}'
            if country and country != 'United States':
                name += f', {country}'
            picks.append({'name': name, 'lat': r['latitude'], 'lon': r['longitude']})
        return picks
    except Exception:
        return None


def get_current_conditions(lat, lon):
    """Get current conditions from NWS observation stations."""
    try:
        points = fetch_json(f'https://api.weather.gov/points/{lat},{lon}')
        stations_url = points['properties']['observationStations']
        stations = fetch_json(stations_url)
        station_id = stations['features'][0]['properties']['stationIdentifier']
        obs = fetch_json(f'https://api.weather.gov/stations/{station_id}/observations/latest')
        props = obs['properties']

        temp_c = props.get('temperature', {}).get('value')
        temp_f = round(temp_c * 9/5 + 32) if temp_c is not None else None

        humidity = props.get('relativeHumidity', {}).get('value')
        humidity = round(humidity) if humidity is not None else None

        wind_speed_ms = props.get('windSpeed', {}).get('value')
        wind_speed_mph = round(wind_speed_ms * 2.237) if wind_speed_ms is not None else None

        wind_dir = props.get('windDirection', {}).get('value')
        wind_dir_str = deg_to_compass(wind_dir) if wind_dir is not None else ''

        gust_ms = props.get('windGust', {}).get('value')
        gust_mph = round(gust_ms * 2.237) if gust_ms is not None else None

        pressure_pa = props.get('barometricPressure', {}).get('value')
        pressure_inhg = round(pressure_pa * 0.00029530, 2) if pressure_pa is not None else None

        dewpoint_c = props.get('dewpoint', {}).get('value')
        dewpoint_f = round(dewpoint_c * 9/5 + 32) if dewpoint_c is not None else None

        visibility_m = props.get('visibility', {}).get('value')
        visibility_mi = round(visibility_m * 0.000621371, 1) if visibility_m is not None else None

        desc = props.get('textDescription', '')

        return {
            'temp_f': temp_f,
            'humidity': humidity,
            'wind_speed': wind_speed_mph,
            'wind_dir': wind_dir_str,
            'wind_gust': gust_mph,
            'pressure': pressure_inhg,
            'dewpoint_f': dewpoint_f,
            'visibility_mi': visibility_mi,
            'description': desc,
            'station': station_id,
        }
    except Exception as e:
        return {'error': str(e)}


def get_forecast(lat, lon):
    """Get forecast periods from NWS."""
    try:
        points = fetch_json(f'https://api.weather.gov/points/{lat},{lon}')
        forecast_url = points['properties']['forecast']
        forecast = fetch_json(forecast_url)
        periods = forecast['properties']['periods'][:8]
        results = []
        for p in periods:
            results.append({
                'name': p['name'],
                'temp': p['temperature'],
                'unit': p['temperatureUnit'],
                'wind': f"{p['windSpeed']} {p['windDirection']}",
                'short': p['shortForecast'],
                'detail': p['detailedForecast'],
                'is_night': not p['isDaytime'],
            })
        return results
    except Exception as e:
        return [{'error': str(e)}]


def get_hourly_forecast(lat, lon, hours=24):
    """Get hourly forecast data from NWS gridpoints API."""
    try:
        points = fetch_json(f'https://api.weather.gov/points/{lat},{lon}')
        hourly_url = points['properties']['forecastHourly']
        hourly = fetch_json(hourly_url)
        periods = hourly['properties']['periods'][:hours]

        # Determine UTC offset for local time display
        now = time.time()
        utc_offset = datetime.fromtimestamp(now) - datetime.utcfromtimestamp(now)
        offset_hours = int(utc_offset.total_seconds() // 3600)

        results = []
        for p in periods:
            # Parse ISO timestamp
            ts = p.get('startTime', '')
            try:
                hour = int(ts[11:13])
            except (ValueError, IndexError):
                hour = 0

            temp = p.get('temperature', 0)
            wind_str = p.get('windSpeed', '0 mph')
            # Extract numeric wind speed
            wind_mph = 0
            for part in wind_str.split():
                try:
                    wind_mph = int(part)
                    break
                except ValueError:
                    continue

            wind_dir = p.get('windDirection', '')
            precip_pct = p.get('probabilityOfPrecipitation', {}).get('value')
            if precip_pct is None:
                precip_pct = 0
            short = p.get('shortForecast', '')

            results.append({
                'hour': hour,
                'temp': temp,
                'wind_mph': wind_mph,
                'wind_dir': wind_dir,
                'precip_pct': precip_pct,
                'short': short,
                'is_night': not p.get('isDaytime', True),
            })
        return results
    except Exception as e:
        return [{'error': str(e)}]


def get_7day_forecast(lat, lon):
    """Get 7-day forecast with high/low temps per day."""
    try:
        points = fetch_json(f'https://api.weather.gov/points/{lat},{lon}')
        forecast_url = points['properties']['forecast']
        forecast = fetch_json(forecast_url)
        periods = forecast['properties']['periods'][:14]  # up to 7 days

        # Group into days (day/night pairs)
        days = []
        i = 0
        while i < len(periods):
            p = periods[i]
            day_entry = {
                'name': p['name'].split()[0] if ' ' in p['name'] else p['name'],
                'short': p['shortForecast'],
                'wind': f"{p['windSpeed']} {p['windDirection']}",
            }
            if p['isDaytime']:
                day_entry['high'] = p['temperature']
                # Check for matching night period
                if i + 1 < len(periods) and not periods[i + 1]['isDaytime']:
                    day_entry['low'] = periods[i + 1]['temperature']
                    day_entry['night_short'] = periods[i + 1]['shortForecast']
                    i += 2
                else:
                    day_entry['low'] = None
                    i += 1
            else:
                day_entry['high'] = None
                day_entry['low'] = p['temperature']
                day_entry['name'] = p['name'].replace(' Night', '')
                i += 1
            days.append(day_entry)
        return days
    except Exception as e:
        return [{'error': str(e)}]


def get_gridpoint_precip(lat, lon):
    """Get quantitative precipitation forecast from NWS gridpoints raw data."""
    try:
        points = fetch_json(f'https://api.weather.gov/points/{lat},{lon}')
        grid_id = points['properties']['gridId']
        grid_x = points['properties']['gridX']
        grid_y = points['properties']['gridY']
        raw = fetch_json(f'https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}')

        # Get quantitative precipitation forecast (QPF) - values in mm
        qpf = raw['properties'].get('quantitativePrecipitation', {}).get('values', [])

        # Aggregate into daily totals for next 7 days
        from datetime import timedelta
        today = datetime.now().date()
        daily = {}
        for entry in qpf:
            try:
                ts = entry['validTime'].split('/')[0]
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                day = dt.date()
                delta = (day - today).days
                if 0 <= delta < 7:
                    val_mm = entry.get('value', 0) or 0
                    val_in = val_mm / 25.4
                    if delta not in daily:
                        daily[delta] = {'total_in': 0, 'day_name': day.strftime('%a')}
                    daily[delta]['total_in'] += val_in
            except (ValueError, KeyError):
                continue

        results = []
        for d in range(7):
            if d in daily:
                results.append(daily[d])
            else:
                day = today + timedelta(days=d)
                results.append({'total_in': 0, 'day_name': day.strftime('%a')})
        return results
    except Exception as e:
        return [{'error': str(e)}]


def get_alerts(lat, lon):
    """Get active weather alerts for the area."""
    try:
        alerts = fetch_json(f'https://api.weather.gov/alerts/active?point={lat},{lon}')
        results = []
        for feature in alerts.get('features', [])[:5]:
            props = feature['properties']
            results.append({
                'event': props.get('event', ''),
                'severity': props.get('severity', ''),
                'headline': props.get('headline', ''),
                'description': props.get('description', ''),
            })
        return results
    except Exception:
        return []


def get_temp_history(station_id):
    """Get hourly temperature history from NWS observations."""
    try:
        obs = fetch_json(f'https://api.weather.gov/stations/{station_id}/observations?limit=100')
        seen = set()
        hourly = []
        # Determine UTC offset for Central time (CDT=-5, CST=-6)
        # Use system localtime to detect DST
        now = time.time()
        utc_offset = datetime.fromtimestamp(now) - datetime.utcfromtimestamp(now)
        offset_hours = int(utc_offset.total_seconds() // 3600)
        for feature in obs['features']:
            p = feature['properties']
            ts = p.get('timestamp', '')[:13]  # YYYY-MM-DDTHH (UTC)
            tc = p.get('temperature', {}).get('value')
            if tc is not None and ts and ts not in seen:
                seen.add(ts)
                tf = round(tc * 9/5 + 32)
                utc_hour = int(ts[11:13])
                local_hour = (utc_hour + offset_hours) % 24
                hourly.append((f'{local_hour:02d}', tf))
        hourly.reverse()  # oldest first
        return hourly[-6:]  # last 6 hours
    except Exception:
        return []


def temp_trend_graph(hourly, bar_max=40):
    """Build a horizontal bar graph of temperature trend over recent hours.

    One row per hour: time label, temp value, horizontal bar.
    Returns list of strings.
    """
    if not hourly:
        return [f'{DIM}(no recent data){RST}']

    temps = [t for _, t in hourly]
    t_min = min(temps)
    t_max = max(temps)
    t_range = t_max - t_min
    if t_range == 0:
        t_range = 1

    lines = []
    for hour, temp in hourly:
        # Convert 24h to 12h label
        h = int(hour)
        suffix = 'a' if h < 12 else 'p'
        h12 = h % 12 or 12
        label = f'{h12}{suffix}'

        # Bar length proportional to temp within range
        # Minimum 1 bar so every hour shows something
        bar_len = max(1, int((temp - t_min) / t_range * bar_max))
        tc = temp_color(temp)
        bar = f'{tc}{BLK_FULL * bar_len}{RST}'

        lines.append(f'{DIM}{label:>4}{RST} {tc}{temp:>3}F{RST} {bar}')

    return lines


def deg_to_compass(deg):
    """Convert degrees to compass direction."""
    if deg is None:
        return ''
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
            'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    idx = round(deg / 22.5) % 16
    return dirs[idx]


def weather_icon(desc):
    """Return simple ASCII weather icon based on description."""
    d = (desc or '').lower().strip()
    if not d:
        # NWS sometimes returns empty description — show neutral/unknown
        return [
            f'{WHITE}     {RST}',
            f'{WHITE}  -- {RST}',
            f'{WHITE} |  |{RST}',
            f'{WHITE}  -- {RST}',
            f'{DIM}  ??  {RST}',
        ]
    if 'thunder' in d or 'storm' in d:
        return [
            f'{BRIGHT_YELLOW}  __{RST}',
            f'{WHITE} (  ){RST}',
            f'{DIM}{WHITE}(____){RST}',
            f'{BRIGHT_YELLOW} / / {RST}',
            f'{BRIGHT_YELLOW}/   /{RST}',
        ]
    elif 'rain' in d or 'shower' in d or 'drizzle' in d:
        return [
            f'{WHITE}  __{RST}',
            f'{WHITE} (  ){RST}',
            f'{WHITE}(____){RST}',
            f'{CYAN} . . {RST}',
            f'{CYAN}. . .{RST}',
        ]
    elif 'snow' in d or 'flurr' in d:
        return [
            f'{WHITE}  __{RST}',
            f'{BRIGHT_WHITE} (  ){RST}',
            f'{BRIGHT_WHITE}(____){RST}',
            f'{BRIGHT_WHITE} * * {RST}',
            f'{BRIGHT_WHITE}* * *{RST}',
        ]
    elif 'cloud' in d or 'overcast' in d:
        return [
            f'{WHITE}     {RST}',
            f'{WHITE}  __{RST}',
            f'{WHITE} (  ){RST}',
            f'{WHITE}(____){RST}',
            f'{DIM}     {RST}',
        ]
    elif 'fog' in d or 'mist' in d or 'haze' in d:
        return [
            f'{DIM}{WHITE}     {RST}',
            f'{DIM}{WHITE}~~~~~{RST}',
            f'{DIM}{WHITE} ~~~ {RST}',
            f'{DIM}{WHITE}~~~~~{RST}',
            f'{DIM}{WHITE} ~~~ {RST}',
        ]
    elif 'clear' in d or 'sunny' in d or 'fair' in d:
        return [
            f'{BRIGHT_YELLOW}  \\|/ {RST}',
            f'{BRIGHT_YELLOW} -- --{RST}',
            f'{BRIGHT_YELLOW}  (O) {RST}',
            f'{BRIGHT_YELLOW} -- --{RST}',
            f'{BRIGHT_YELLOW}  /|\\ {RST}',
        ]
    elif 'partly' in d:
        return [
            f'{BRIGHT_YELLOW}  \\|  {RST}',
            f'{BRIGHT_YELLOW} --{WHITE}__{RST}',
            f'{BRIGHT_YELLOW}  ({WHITE}  ){RST}',
            f'{WHITE} (____){RST}',
            f'{DIM}      {RST}',
        ]
    else:
        # Unknown condition — show generic sky
        return [
            f'{WHITE}     {RST}',
            f'{WHITE} .--. {RST}',
            f'{WHITE}(    ){RST}',
            f'{WHITE} `--\' {RST}',
            f'{DIM}     {RST}',
        ]


def visible_len(text):
    """Return visible length of text after stripping ANSI escape codes."""
    import re
    return len(re.sub(r'\033\[[0-9;]*m', '', text))


def hline(char=HZ, width=WIDTH, color=CYAN):
    """Draw a horizontal line."""
    return f'{color}{char * width}{RST}'


def box_top(title='', width=WIDTH):
    """Draw top of a box with optional title."""
    if title:
        # Layout: TL + HZ + HZ + space + title + space + HZ*remaining + TR
        title_vis = visible_len(title)
        remaining = width - title_vis - 6
        if remaining < 0:
            remaining = 0
        return f'{BRIGHT_CYAN}{TL}{HZ}{HZ} {BRIGHT_WHITE}{title} {BRIGHT_CYAN}{HZ * remaining}{TR}{RST}'
    return f'{BRIGHT_CYAN}{TL}{HZ * (width - 2)}{TR}{RST}'


def box_bottom(width=WIDTH):
    """Draw bottom of a box."""
    return f'{BRIGHT_CYAN}{BL}{HZ * (width - 2)}{BR}{RST}'


def box_line(text, width=WIDTH):
    """Draw a line inside a box."""
    # Layout: VT + space + text + padding + VT = width visible chars
    text_vis = visible_len(text)
    padding = width - 3 - text_vis
    if padding < 0:
        padding = 0
    return f'{BRIGHT_CYAN}{VT}{RST} {text}{" " * padding}{BRIGHT_CYAN}{VT}{RST}'


def box_divider(width=WIDTH):
    """Draw a divider inside a box."""
    return f'{BRIGHT_CYAN}{LT}{HZ * (width - 2)}{RT}{RST}'


def temp_color(temp_f):
    """Return color code based on temperature."""
    if temp_f is None:
        return WHITE
    if temp_f >= 95:
        return BRIGHT_RED
    elif temp_f >= 85:
        return RED
    elif temp_f >= 75:
        return BRIGHT_YELLOW
    elif temp_f >= 65:
        return YELLOW
    elif temp_f >= 55:
        return GREEN
    elif temp_f >= 45:
        return CYAN
    elif temp_f >= 32:
        return BRIGHT_BLUE
    else:
        return BRIGHT_WHITE


def temp_bar(temp_f, max_width=20):
    """Return a colored temperature bar."""
    if temp_f is None:
        return f'{DIM}(n/a){RST}'
    # Scale: 0F = 0 bars, 110F = max_width bars
    bars = max(0, min(max_width, int(temp_f / 110 * max_width)))
    color = temp_color(temp_f)
    return f'{color}{"=" * bars}{DIM}{"." * (max_width - bars)}{RST} {color}{temp_f}F{RST}'


def display_header():
    """Show the weather door header."""
    outln()
    outln(f'{BRIGHT_CYAN}  {BLK_FULL}{BLK_FULL}  {BRIGHT_WHITE}W E A T H E R   S T A T I O N{RST}')
    outln(f'{CYAN}  {BLK_FULL}{BLK_FULL}  {DIM}Pensacola Area Conditions & Forecast{RST}')
    outln(f'{CYAN}  {BLK_FULL}{BLK_FULL}  {DIM}Source: National Weather Service (weather.gov){RST}')
    outln(hline())
    outln()


def display_current(name, conditions):
    """Display current conditions with ANSI art."""
    if 'error' in conditions:
        outln(box_top(f'Current: {name}'))
        outln(box_line(f'{RED}Error fetching conditions: {conditions["error"]}{RST}'))
        outln(box_bottom())
        return

    desc = conditions.get('description', 'Unknown')
    icon = weather_icon(desc)

    outln(box_top(f'Current Conditions: {name}'))
    outln(box_line(f'{DIM}Station: {conditions.get("station", "?")}{RST}'))
    outln(box_divider())

    # Layout: icon on left, data on right
    temp = conditions.get('temp_f')
    tc = temp_color(temp)
    data_lines = [
        f'{BRIGHT_WHITE}{desc}{RST}',
        f'{DIM}Temperature:{RST}  {tc}{temp}F{RST}' if temp else f'{DIM}Temperature:{RST}  n/a',
        f'{DIM}Feels Like:{RST}   {tc}{temp}F{RST}' if temp else '',  # NWS doesn't give heat index in obs
        f'{DIM}Humidity:{RST}     {GREEN}{conditions.get("humidity", "?")}%{RST}',
        f'{DIM}Dewpoint:{RST}     {CYAN}{conditions.get("dewpoint_f", "?")}F{RST}',
    ]

    wind = conditions.get('wind_speed')
    wind_dir = conditions.get('wind_dir', '')
    gust = conditions.get('wind_gust')
    wind_str = f'{wind} mph {wind_dir}' if wind else 'Calm'
    if gust:
        wind_str += f' (gusts {gust} mph)'

    data_lines2 = [
        f'{DIM}Wind:{RST}         {BRIGHT_WHITE}{wind_str}{RST}',
        f'{DIM}Pressure:{RST}     {WHITE}{conditions.get("pressure", "?")} inHg{RST}',
        f'{DIM}Visibility:{RST}   {WHITE}{conditions.get("visibility_mi", "?")} mi{RST}',
    ]

    # Print icon alongside data
    for i in range(max(len(icon), len(data_lines))):
        ic = icon[i] if i < len(icon) else '      '
        dl = data_lines[i] if i < len(data_lines) else ''
        outln(box_line(f'  {ic}    {dl}'))

    for dl in data_lines2:
        outln(box_line(f'           {dl}'))

    # Temperature trend graph
    outln(box_divider())
    station_id = conditions.get('station')
    if station_id:
        hourly = get_temp_history(station_id)
        graph_lines = temp_trend_graph(hourly, bar_max=40)
        outln(box_line(f'  {DIM}Temperature Trend (last {len(hourly) if hourly else 0} hours):{RST}'))
        for gl in graph_lines:
            outln(box_line(f'  {gl}'))
    else:
        outln(box_line(f'  {temp_bar(temp, 40)}'))

    outln(box_bottom())


def display_forecast(forecast, page_size=4):
    """Display forecast periods in pages that fit a 25-line screen."""
    if not forecast or 'error' in forecast[0]:
        outln(box_top('Forecast'))
        outln(box_line(f'{RED}Error fetching forecast{RST}'))
        outln(box_bottom())
        return

    pages = []
    for i in range(0, len(forecast), page_size):
        pages.append(forecast[i:i + page_size])

    for pi, page in enumerate(pages):
        if pi > 0:
            pause()
            outln()

        page_label = f'Forecast ({pi + 1}/{len(pages)})' if len(pages) > 1 else 'Extended Forecast'
        outln(box_top(page_label))

        for i, period in enumerate(page):
            if i > 0:
                outln(box_divider())

            name = period['name']
            temp = period['temp']
            unit = period['unit']
            tc = temp_color(temp)
            is_night = period.get('is_night', False)
            name_color = BRIGHT_BLUE if is_night else BRIGHT_YELLOW

            outln(box_line(f'  {name_color}{name:<20}{RST} {tc}{temp}{unit}{RST}  {DIM}{period["wind"]}{RST}'))
            outln(box_line(f'  {WHITE}{period["short"]}{RST}'))

        outln(box_bottom())


def display_alerts(alerts):
    """Display active weather alerts."""
    if not alerts:
        return

    outln()
    for alert in alerts:
        severity = alert.get('severity', '').upper()
        if severity in ('EXTREME', 'SEVERE'):
            color = BRIGHT_RED
        elif severity == 'MODERATE':
            color = BRIGHT_YELLOW
        else:
            color = YELLOW

        outln(box_top(f'{color}ALERT: {alert["event"]}{RST}'))
        headline = alert.get('headline', '')
        # Word wrap headline
        words = headline.split()
        line = ''
        for w in words:
            if len(line) + len(w) + 1 > WIDTH - 6:
                outln(box_line(f'  {color}{line}{RST}'))
                line = w
            else:
                line = f'{line} {w}'.strip()
        if line:
            outln(box_line(f'  {color}{line}{RST}'))
        outln(box_bottom())


def display_temp_trend(hourly_data):
    """Display 24-hour temperature trend, sampled to fit a BBS screen."""
    if not hourly_data or 'error' in hourly_data[0]:
        outln(box_top('Temperature Trend'))
        outln(box_line(f'{RED}Error fetching hourly data{RST}'))
        outln(box_bottom())
        return

    # Sample every 2 hours to fit ~12 rows on screen
    sampled = hourly_data[::2]

    outln(box_top('24-Hour Temperature Trend'))
    outln(box_line(f'  {DIM}Time  Temp {"":<38} Conditions{RST}'))
    outln(box_divider())

    temps = [h['temp'] for h in sampled]
    t_min = min(temps)
    t_max = max(temps)
    t_range = t_max - t_min if t_max != t_min else 1
    bar_max = 38

    for h in sampled:
        hour = h['hour']
        temp = h['temp']
        short = h['short'][:14]

        suffix = 'a' if hour < 12 else 'p'
        h12 = hour % 12 or 12
        label = f'{h12:>2}{suffix}'

        bar_len = max(1, int((temp - t_min) / t_range * bar_max))
        tc = temp_color(temp)

        bar = f'{tc}{BLK_FULL * bar_len}{RST}{DIM}{"." * (bar_max - bar_len)}{RST}'
        outln(box_line(f'  {label} {tc}{temp:>3}F{RST} {bar} {DIM}{short}{RST}'))

    outln(box_divider())
    all_temps = [h['temp'] for h in hourly_data]
    avg_temp = sum(all_temps) // len(all_temps)
    lo = min(all_temps)
    hi = max(all_temps)
    outln(box_line(f'  {DIM}Lo:{RST} {temp_color(lo)}{lo}F{RST}  '
                   f'{DIM}Hi:{RST} {temp_color(hi)}{hi}F{RST}  '
                   f'{DIM}Avg:{RST} {temp_color(avg_temp)}{avg_temp}F{RST}  '
                   f'{DIM}Range:{RST} {WHITE}{hi - lo}F{RST}'))
    outln(box_bottom())


def display_precip_forecast(hourly_data, daily_precip):
    """Display precipitation probability + daily accumulation, compact layout."""
    outln(box_top('Precipitation Forecast'))

    # --- Hourly probability (sampled every 3h to fit on one screen with daily) ---
    if hourly_data and 'error' not in hourly_data[0]:
        outln(box_line(f'  {BRIGHT_WHITE}Rain Chance (next 24h){RST}'))
        outln(box_divider())

        sampled = hourly_data[::3]  # every 3 hours = 8 rows
        bar_max = 42

        for h in sampled:
            hour = h['hour']
            pct = h['precip_pct']

            suffix = 'a' if hour < 12 else 'p'
            h12 = hour % 12 or 12
            label = f'{h12:>2}{suffix}'

            bar_len = max(0, int(pct / 100 * bar_max))

            if pct >= 70:
                pc = BRIGHT_BLUE
            elif pct >= 40:
                pc = CYAN
            elif pct >= 20:
                pc = GREEN
            else:
                pc = DIM

            bar = f'{pc}{BLK_FULL * bar_len}{RST}{DIM}{"." * (bar_max - bar_len)}{RST}'
            outln(box_line(f'  {label} {pc}{pct:>3}%{RST} {bar}'))

    # --- Daily accumulation (7 days, compact) ---
    if daily_precip and (not isinstance(daily_precip[0], dict) or 'error' not in daily_precip[0]):
        outln(box_divider())
        outln(box_line(f'  {BRIGHT_WHITE}Expected Rainfall (7 days){RST}'))

        max_rain = max((d['total_in'] for d in daily_precip if 'total_in' in d), default=0.1)
        if max_rain == 0:
            max_rain = 0.1
        bar_max = 42

        for d in daily_precip:
            if 'error' in d:
                continue
            rain = d.get('total_in', 0)
            name = d.get('day_name', '?')
            bar_len = max(0, int(rain / max_rain * bar_max)) if rain > 0 else 0

            if rain >= 1.0:
                rc = BRIGHT_BLUE
            elif rain >= 0.5:
                rc = CYAN
            elif rain >= 0.1:
                rc = GREEN
            else:
                rc = DIM

            bar = f'{rc}{BLK_FULL * bar_len}{RST}{DIM}{"." * (bar_max - bar_len)}{RST}' if bar_len > 0 else f'{DIM}{"." * bar_max}{RST}'
            rain_str = f'{rain:.2f}"' if rain >= 0.01 else '  -- '
            outln(box_line(f'  {WHITE}{name:<4}{RST}{rc}{rain_str:>6}{RST} {bar}'))

    outln(box_bottom())


def display_wind_trend(hourly_data):
    """Display 24-hour wind speed trend, sampled to fit a BBS screen."""
    if not hourly_data or 'error' in hourly_data[0]:
        outln(box_top('Wind Trend'))
        outln(box_line(f'{RED}Error fetching hourly data{RST}'))
        outln(box_bottom())
        return

    sampled = hourly_data[::2]

    outln(box_top('24-Hour Wind Forecast'))
    outln(box_line(f'  {DIM}Time  Speed Dir {"":<38}{RST}'))
    outln(box_divider())

    winds = [h['wind_mph'] for h in sampled]
    w_max = max(winds) if winds else 1
    if w_max == 0:
        w_max = 1
    bar_max = 38

    for h in sampled:
        hour = h['hour']
        wind = h['wind_mph']
        wind_dir = h['wind_dir']

        suffix = 'a' if hour < 12 else 'p'
        h12 = hour % 12 or 12
        label = f'{h12:>2}{suffix}'

        bar_len = max(0, int(wind / w_max * bar_max))

        if wind >= 30:
            wc = BRIGHT_RED
        elif wind >= 20:
            wc = BRIGHT_YELLOW
        elif wind >= 15:
            wc = YELLOW
        elif wind >= 10:
            wc = GREEN
        else:
            wc = DIM

        bar = f'{wc}{BLK_FULL * bar_len}{RST}{DIM}{"." * (bar_max - bar_len)}{RST}'
        outln(box_line(f'  {label} {wc}{wind:>2}mph{RST} {DIM}{wind_dir:>3}{RST} {bar}'))

    outln(box_divider())
    all_winds = [h['wind_mph'] for h in hourly_data]
    avg_w = sum(all_winds) // len(all_winds) if all_winds else 0
    outln(box_line(f'  {DIM}Lo:{RST} {WHITE}{min(all_winds)}mph{RST}  '
                   f'{DIM}Hi:{RST} {BRIGHT_YELLOW}{max(all_winds)}mph{RST}  '
                   f'{DIM}Avg:{RST} {WHITE}{avg_w}mph{RST}'))
    outln(box_bottom())


def display_7day_visual(days):
    """Display 7-day forecast with temperature range bars."""
    if not days or 'error' in days[0]:
        outln(box_top('7-Day Forecast'))
        outln(box_line(f'{RED}Error fetching forecast{RST}'))
        outln(box_bottom())
        return

    outln(box_top('7-Day Visual Forecast'))
    outln(box_line(f'  {DIM}{"Day":<10} {"Low":>5} {"High":>5}  {"":34}  Outlook{RST}'))
    outln(box_divider())

    # Find overall range for scaling
    all_temps = []
    for d in days:
        if d.get('high') is not None:
            all_temps.append(d['high'])
        if d.get('low') is not None:
            all_temps.append(d['low'])

    if not all_temps:
        outln(box_line(f'{DIM}  No forecast data available{RST}'))
        outln(box_bottom())
        return

    overall_min = min(all_temps)
    overall_max = max(all_temps)
    overall_range = overall_max - overall_min if overall_max != overall_min else 1
    bar_total = 34

    for d in days:
        name = d.get('name', '?')[:9]
        high = d.get('high')
        low = d.get('low')
        short = d.get('short', '')[:16]

        tc_hi = temp_color(high) if high is not None else DIM
        tc_lo = temp_color(low) if low is not None else DIM

        low_str = f'{low}F' if low is not None else ' -- '
        high_str = f'{high}F' if high is not None else ' -- '

        # Build range bar: dots before low, blocks between low-high, dots after
        if high is not None and low is not None:
            lo_pos = int((low - overall_min) / overall_range * bar_total)
            hi_pos = int((high - overall_min) / overall_range * bar_total)
            hi_pos = max(hi_pos, lo_pos + 1)  # at least 1 block

            before = lo_pos
            block = hi_pos - lo_pos
            after = bar_total - hi_pos

            # Gradient the range bar: blue for low end, yellow/red for high end
            bar = (f'{DIM}{"." * before}{RST}'
                   f'{tc_lo}{BLK_FULL * (block // 2)}{RST}'
                   f'{tc_hi}{BLK_FULL * (block - block // 2)}{RST}'
                   f'{DIM}{"." * after}{RST}')
        elif high is not None:
            pos = int((high - overall_min) / overall_range * bar_total)
            bar = f'{DIM}{"." * pos}{RST}{tc_hi}{BLK_FULL}{RST}{DIM}{"." * (bar_total - pos - 1)}{RST}'
        elif low is not None:
            pos = int((low - overall_min) / overall_range * bar_total)
            bar = f'{DIM}{"." * pos}{RST}{tc_lo}{BLK_FULL}{RST}{DIM}{"." * (bar_total - pos - 1)}{RST}'
        else:
            bar = f'{DIM}{"." * bar_total}{RST}'

        outln(box_line(f'  {WHITE}{name:<10}{RST}{tc_lo}{low_str:>5}{RST} {tc_hi}{high_str:>5}{RST}  {bar}  {DIM}{short}{RST}'))

    # Overall summary
    outln(box_divider())
    tc_lo = temp_color(overall_min)
    tc_hi = temp_color(overall_max)
    outln(box_line(f'  {DIM}Week Range:{RST} {tc_lo}{overall_min}F{RST} {DIM}to{RST} {tc_hi}{overall_max}F{RST}'))
    outln(box_bottom())


def display_menu():
    """Show location selection menu in 3 columns."""
    outln()
    # Build items: locations + special options
    items = []
    for key in sorted(LOCATIONS.keys()):
        name = LOCATIONS[key][0]
        items.append((key, name))
    # Pad to multiple of 3
    while len(items) % 3 != 0:
        items.append(('', ''))

    # 3-column layout
    col_w = 24
    for row in range(0, len(items), 3):
        cols = []
        for c in range(3):
            if row + c < len(items) and items[row + c][0]:
                k, n = items[row + c]
                cols.append(f'{BRIGHT_CYAN}{k}{RST} {DIM}-{RST} {WHITE}{n:<{col_w - 6}}{RST}')
            else:
                cols.append(' ' * col_w)
        outln(f'  {"".join(cols)}')
    outln()
    outln(f'  {BRIGHT_CYAN}T{RST} {DIM}-{RST} {WHITE}Temp Trend (24h){RST}   '
          f'{BRIGHT_CYAN}P{RST} {DIM}-{RST} {WHITE}Precipitation{RST}       '
          f'{BRIGHT_CYAN}F{RST} {DIM}-{RST} {WHITE}7-Day Visual{RST}')
    outln(f'  {BRIGHT_CYAN}G{RST} {DIM}-{RST} {WHITE}Wind Trend (24h){RST}   '
          f'{BRIGHT_CYAN}D{RST} {DIM}-{RST} {WHITE}Doppler Radar{RST}       '
          f'{BRIGHT_CYAN}W{RST} {DIM}-{RST} {WHITE}Weather Alerts{RST}')
    outln(f'  {BRIGHT_CYAN}R{RST} {DIM}-{RST} {WHITE}Refresh Overview{RST}   '
          f'{BRIGHT_CYAN}Q{RST} {DIM}-{RST} {WHITE}Return to BBS{RST}')
    outln()


def display_overview():
    """Show quick overview of all locations."""
    # Fetch all locations in parallel to avoid sequential NWS API latency
    from concurrent.futures import ThreadPoolExecutor
    keys = sorted(LOCATIONS.keys())

    def fetch_loc(key):
        name, lat, lon = LOCATIONS[key]
        return (name, get_current_conditions(lat, lon))

    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        results = list(pool.map(fetch_loc, keys))

    outln(box_top('Pensacola Area Overview'))
    outln(box_line(f'  {BRIGHT_WHITE}{"Location":<22} {"Temp":>6}  {"Wind":<18} {"Conditions"}{RST}'))
    outln(box_divider())

    for name, cond in results:
        if 'error' in cond:
            outln(box_line(f'  {WHITE}{name:<22}{RST} {RED}{"error":>6}{RST}'))
        else:
            temp = cond.get('temp_f')
            tc = temp_color(temp)
            wind = cond.get('wind_speed')
            wind_dir = cond.get('wind_dir', '')
            wind_str = f'{wind} mph {wind_dir}' if wind else 'Calm'
            desc = cond.get('description', '?')[:24]
            temp_str = f'{temp}F' if temp else 'n/a'
            outln(box_line(f'  {WHITE}{name:<22}{RST} {tc}{temp_str:>6}{RST}  {DIM}{wind_str:<18}{RST} {WHITE}{desc}{RST}'))

    outln(box_divider())
    outln(box_line(f'{DIM}  Updated: {datetime.now().strftime("%B %d, %Y %I:%M %p")}{RST}'))
    outln(box_bottom())


def display_alerts_view():
    """Show all active alerts for the main Pensacola location."""
    outln()
    outln(f'{BRIGHT_WHITE}  Checking for active alerts...{RST}')
    alerts = get_alerts(30.4213, -87.2169)  # Pensacola
    outln()
    if not alerts:
        outln(box_top('Weather Alerts'))
        outln(box_line(f'  {GREEN}No active weather alerts for the Pensacola area.{RST}'))
        outln(box_bottom())
    else:
        outln(f'{BRIGHT_YELLOW}  {len(alerts)} active alert(s):{RST}')
        outln()
        display_alerts(alerts)


def render_frame_to_ansi(img_path):
    """Render a PNG frame to ANSI bytes via chafa + iconv."""
    import subprocess
    try:
        chafa = subprocess.Popen(
            ['chafa', '--size=80x22', '--colors=256', '-f', 'symbols',
             '--symbols=half+space', '--work=9', img_path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        iconv = subprocess.Popen(
            ['iconv', '-f', 'UTF-8', '-t', 'CP437//TRANSLIT'],
            stdin=chafa.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        chafa.stdout.close()
        output = iconv.communicate(timeout=10)[0]
        return output
    except Exception:
        return None


def display_radar(area_lat=30.4213, area_lon=-87.2169, area_name='Pensacola'):
    """Show animated Doppler radar via chafa rendering of radar-fetch.py frames."""
    import subprocess
    outln()
    outln(f'{DIM}  Fetching Doppler radar frames (this may take a moment)...{RST}')

    frame_dir = '/tmp/bbs-radar-frames'
    num_frames = 4  # ~40 minutes of radar history (10 min intervals)

    # Generate frames
    try:
        result = subprocess.run(
            ['/usr/bin/python3', '/mystic/doors/radar/radar-fetch.py',
             '--frames', str(num_frames),
             '--lat', str(area_lat), '--lon', str(area_lon),
             frame_dir],
            capture_output=True, timeout=90
        )
        if result.returncode != 0:
            err = result.stderr.decode(errors='replace').strip()
            outln(f'{RED}  Error generating radar: {err}{RST}')
            return
    except Exception as e:
        outln(f'{RED}  Error: {e}{RST}')
        return

    # Parse frame metadata from stdout (format: idx:ts:path:row:col)
    frame_info = []
    cross_row, cross_col = 0, 0
    for line in result.stdout.decode().strip().split('\n'):
        if ':' in line:
            parts = line.split(':')
            if len(parts) >= 5:
                idx, ts, path = parts[0], parts[1], parts[2]
                cross_row, cross_col = int(parts[3]), int(parts[4])
                frame_info.append((int(ts), path))

    if not frame_info:
        outln(f'{RED}  No radar frames available.{RST}')
        return

    # Pre-render all frames to ANSI
    outln(f'{DIM}  Rendering {len(frame_info)} frames...{RST}')
    ansi_frames = []
    for ts, path in frame_info:
        frame_data = render_frame_to_ansi(path)
        if frame_data:
            from datetime import datetime
            dt = datetime.fromtimestamp(ts)
            time_str = dt.strftime('%I:%M %p')
            ansi_frames.append((time_str, frame_data))

    if not ansi_frames:
        outln(f'{RED}  Failed to render radar frames.{RST}')
        return

    # ANSI crosshair overlay: draw at character position using cursor movement
    # ESC[row;colH positions cursor (1-based)
    def draw_ansi_crosshair(row, col):
        """Draw a bright yellow crosshair at character position using cursor addressing."""
        yc = '\033[1;33m'  # bright yellow
        rst = '\033[0m'
        arm = 3  # arm length in characters
        buf = b''
        # Horizontal arms
        for dx in range(-arm, arm + 1):
            if dx == 0:
                continue
            c = col + dx
            if 1 <= c <= 80:
                buf += f'\033[{row};{c}H{yc}-{rst}'.encode('latin-1')
        # Vertical arms
        for dy in range(-arm, arm + 1):
            if dy == 0:
                continue
            r = row + dy
            if 1 <= r <= 22:
                buf += f'\033[{r};{col}H{yc}|{rst}'.encode('latin-1')
        # Center marker
        buf += f'\033[{row};{col}H{yc}+{rst}'.encode('latin-1')
        return buf

    crosshair_bytes = draw_ansi_crosshair(cross_row, cross_col) if cross_row > 0 else b''

    # Animate: loop through frames, clear screen between each
    CLEAR = '\033[2J\033[H'  # clear screen + home cursor
    loops = 3

    for loop in range(loops):
        for i, (time_str, frame_data) in enumerate(ansi_frames):
            sys.stdout.flush()
            sys.stdout.buffer.write(CLEAR.encode())
            sys.stdout.buffer.write(frame_data)
            # Overlay crosshair on top of the rendered frame
            if crosshair_bytes:
                sys.stdout.buffer.write(crosshair_bytes)
            sys.stdout.buffer.flush()
            # Status bar on line 23
            sys.stdout.buffer.write(f'\033[23;1H'.encode())
            sys.stdout.buffer.flush()
            outln(f'{BRIGHT_CYAN}  Doppler Radar{RST} {DIM}-{RST} {BRIGHT_WHITE}{area_name}{RST} '
                  f'{DIM}|{RST} {BRIGHT_YELLOW}{time_str}{RST} '
                  f'{DIM}| Frame {i+1}/{len(ansi_frames)} | Loop {loop+1}/{loops}{RST}')
            time.sleep(0.8)

    # Show final frame
    sys.stdout.flush()
    sys.stdout.buffer.write(CLEAR.encode())
    sys.stdout.buffer.write(ansi_frames[-1][1])
    if crosshair_bytes:
        sys.stdout.buffer.write(crosshair_bytes)
    sys.stdout.buffer.write(f'\033[23;1H'.encode())
    sys.stdout.buffer.flush()
    outln(f'{BRIGHT_CYAN}  Doppler Radar{RST} {DIM}-{RST} {BRIGHT_WHITE}{area_name}{RST} '
          f'{DIM}| Latest: {ansi_frames[-1][0]} | Source: RainViewer / OpenStreetMap{RST}')

    # Cleanup frame files
    import shutil
    try:
        shutil.rmtree(frame_dir, ignore_errors=True)
    except Exception:
        pass


def pause():
    """Wait for user to press Enter."""
    out(f'\r\n{DIM}  Press ENTER to continue...{RST}')
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


def location_chooser(user_ip=None):
    """Present location selection: user's IP location, BBS location, or search."""
    ip_loc = None
    if user_ip:
        ip_loc = geolocate_ip(user_ip)

    display_header()

    outln(box_top('Choose Your Location'))
    outln(box_line(''))

    if ip_loc and ip_loc['name'].lower() != 'pensacola':
        outln(box_line(f'  {BRIGHT_CYAN}1{RST} {DIM}-{RST} {BRIGHT_WHITE}{ip_loc["name"]}{RST} {DIM}(your location){RST}'))
    else:
        ip_loc = None  # Same as BBS, no need to show twice

    outln(box_line(f'  {BRIGHT_CYAN}2{RST} {DIM}-{RST} {BRIGHT_WHITE}Pensacola, FL{RST} {DIM}(BBS home){RST}'))
    outln(box_line(f'  {BRIGHT_CYAN}3{RST} {DIM}-{RST} {BRIGHT_WHITE}Search by city or zip code{RST}'))
    outln(box_line(''))
    outln(box_bottom())
    outln()

    out(f'{BRIGHT_GREEN}  Select>{RST} ')
    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        return 'Pensacola', 30.4213, -87.2169

    if choice == '1' and ip_loc:
        return ip_loc['name'], ip_loc['lat'], ip_loc['lon']
    elif choice == '3':
        outln()
        out(f'  {BRIGHT_WHITE}Enter city name or zip code:{RST} ')
        try:
            query = input().strip()
        except (EOFError, KeyboardInterrupt):
            return 'Pensacola', 30.4213, -87.2169

        if not query:
            return 'Pensacola', 30.4213, -87.2169

        outln(f'{DIM}  Searching...{RST}')
        result = search_location(query)
        if result is None:
            outln(f'{RED}  No results found. Using Pensacola.{RST}')
            pause()
            return 'Pensacola', 30.4213, -87.2169

        if isinstance(result, dict):
            return result['name'], result['lat'], result['lon']

        # Multiple results - let user pick
        outln()
        outln(box_top('Search Results'))
        for i, r in enumerate(result[:8], 1):
            outln(box_line(f'  {BRIGHT_CYAN}{i}{RST} {DIM}-{RST} {WHITE}{r["name"]}{RST}'))
        outln(box_bottom())
        outln()
        out(f'{BRIGHT_GREEN}  Pick #>{RST} ')
        try:
            pick = input().strip()
            idx = int(pick) - 1
            if 0 <= idx < len(result):
                r = result[idx]
                return r['name'], r['lat'], r['lon']
        except (EOFError, KeyboardInterrupt, ValueError):
            pass
        # Default to first result
        r = result[0]
        return r['name'], r['lat'], r['lon']

    # Default: Pensacola
    return 'Pensacola', 30.4213, -87.2169


def weather_loop(area_name, area_lat, area_lon):
    """Main interactive weather loop for a chosen location."""
    outln()
    outln(f'{DIM}  Loading {area_name} area conditions...{RST}')
    outln()

    # Try overview if it's Pensacola area, otherwise show current conditions directly
    is_pensacola = abs(area_lat - 30.4213) < 0.5 and abs(area_lon - (-87.2169)) < 0.5
    if is_pensacola:
        display_overview()
    else:
        conditions = get_current_conditions(area_lat, area_lon)
        display_current(area_name, conditions)

    # Show any active alerts
    alerts = get_alerts(area_lat, area_lon)
    display_alerts(alerts)

    while True:
        outln()
        if is_pensacola:
            # Show Pensacola area location sub-menu
            items = []
            for key in sorted(LOCATIONS.keys()):
                name = LOCATIONS[key][0]
                items.append((key, name))
            while len(items) % 3 != 0:
                items.append(('', ''))
            col_w = 24
            for row in range(0, len(items), 3):
                cols = []
                for c in range(3):
                    if row + c < len(items) and items[row + c][0]:
                        k, n = items[row + c]
                        cols.append(f'{BRIGHT_CYAN}{k}{RST} {DIM}-{RST} {WHITE}{n:<{col_w - 6}}{RST}')
                    else:
                        cols.append(' ' * col_w)
                outln(f'  {"".join(cols)}')
            outln()

        outln(f'  {BRIGHT_CYAN}T{RST} {DIM}-{RST} {WHITE}Temp Trend (24h){RST}   '
              f'{BRIGHT_CYAN}P{RST} {DIM}-{RST} {WHITE}Precipitation{RST}       '
              f'{BRIGHT_CYAN}F{RST} {DIM}-{RST} {WHITE}7-Day Visual{RST}')
        outln(f'  {BRIGHT_CYAN}G{RST} {DIM}-{RST} {WHITE}Wind Trend (24h){RST}   '
              f'{BRIGHT_CYAN}D{RST} {DIM}-{RST} {WHITE}Doppler Radar{RST}       '
              f'{BRIGHT_CYAN}W{RST} {DIM}-{RST} {WHITE}Weather Alerts{RST}')
        outln(f'  {BRIGHT_CYAN}R{RST} {DIM}-{RST} {WHITE}Refresh{RST}             '
              f'{BRIGHT_CYAN}L{RST} {DIM}-{RST} {WHITE}Change Location{RST}     '
              f'{BRIGHT_CYAN}Q{RST} {DIM}-{RST} {WHITE}Return to BBS{RST}')
        outln()

        out(f'{BRIGHT_GREEN}  {area_name}>{RST} ')

        try:
            choice = input().strip().upper()
        except (EOFError, KeyboardInterrupt):
            break

        if not choice:
            continue

        if choice == 'Q':
            outln()
            outln(f'{DIM}  Returning to BBS...{RST}')
            outln()
            break

        elif choice == 'L':
            return 'CHANGE_LOCATION'

        elif choice == 'T':
            outln()
            outln(f'{DIM}  Fetching 24-hour temperature trend...{RST}')
            outln()
            hourly = get_hourly_forecast(area_lat, area_lon)
            display_temp_trend(hourly)
            pause()

        elif choice == 'P':
            outln()
            outln(f'{DIM}  Fetching precipitation data...{RST}')
            outln()
            hourly = get_hourly_forecast(area_lat, area_lon)
            daily_precip = get_gridpoint_precip(area_lat, area_lon)
            display_precip_forecast(hourly, daily_precip)
            pause()

        elif choice == 'F':
            outln()
            outln(f'{DIM}  Fetching 7-day forecast...{RST}')
            outln()
            days = get_7day_forecast(area_lat, area_lon)
            display_7day_visual(days)
            pause()

        elif choice == 'G':
            outln()
            outln(f'{DIM}  Fetching wind forecast...{RST}')
            outln()
            hourly = get_hourly_forecast(area_lat, area_lon)
            display_wind_trend(hourly)
            pause()

        elif choice == 'D':
            display_radar(area_lat, area_lon, area_name)
            pause()

        elif choice == 'R':
            outln()
            outln(f'{DIM}  Refreshing...{RST}')
            outln()
            if is_pensacola:
                display_overview()
            else:
                conditions = get_current_conditions(area_lat, area_lon)
                display_current(area_name, conditions)
            alerts = get_alerts(area_lat, area_lon)
            display_alerts(alerts)

        elif choice == 'W':
            outln()
            outln(f'{BRIGHT_WHITE}  Checking for active alerts...{RST}')
            alerts = get_alerts(area_lat, area_lon)
            outln()
            if not alerts:
                outln(box_top('Weather Alerts'))
                outln(box_line(f'  {GREEN}No active weather alerts for {area_name}.{RST}'))
                outln(box_bottom())
            else:
                outln(f'{BRIGHT_YELLOW}  {len(alerts)} active alert(s):{RST}')
                outln()
                display_alerts(alerts)
            pause()

        elif is_pensacola and choice in LOCATIONS:
            name, lat, lon = LOCATIONS[choice]
            outln()
            outln(f'{DIM}  Fetching conditions for {name}...{RST}')
            outln()

            conditions = get_current_conditions(lat, lon)
            display_current(name, conditions)
            pause()

            outln()
            outln(f'{DIM}  Fetching forecast...{RST}')
            outln()

            forecast = get_forecast(lat, lon)
            display_forecast(forecast)

            alerts = get_alerts(lat, lon)
            display_alerts(alerts)

            # Sub-menu for location-specific trends
            while True:
                outln()
                outln(f'  {BRIGHT_WHITE}{name}{RST} {DIM}|{RST} '
                      f'{BRIGHT_CYAN}T{RST}{DIM}-Temp{RST} '
                      f'{BRIGHT_CYAN}P{RST}{DIM}-Precip{RST} '
                      f'{BRIGHT_CYAN}G{RST}{DIM}-Wind{RST} '
                      f'{BRIGHT_CYAN}F{RST}{DIM}-7Day{RST} '
                      f'{BRIGHT_CYAN}B{RST}{DIM}-Back{RST}')
                out(f'{BRIGHT_GREEN}  {name}>{RST} ')
                try:
                    sub = input().strip().upper()
                except (EOFError, KeyboardInterrupt):
                    break
                if sub == 'T':
                    outln()
                    hourly = get_hourly_forecast(lat, lon)
                    display_temp_trend(hourly)
                    pause()
                elif sub == 'P':
                    outln()
                    hourly = get_hourly_forecast(lat, lon)
                    daily_precip = get_gridpoint_precip(lat, lon)
                    display_precip_forecast(hourly, daily_precip)
                    pause()
                elif sub == 'G':
                    outln()
                    hourly = get_hourly_forecast(lat, lon)
                    display_wind_trend(hourly)
                    pause()
                elif sub == 'F':
                    outln()
                    days = get_7day_forecast(lat, lon)
                    display_7day_visual(days)
                    pause()
                else:
                    break

        else:
            outln(f'{RED}  Invalid selection.{RST}')

    return None


def main():
    # Parse command line args
    user_ip = None
    if len(sys.argv) >= 3:
        user_ip = sys.argv[2]  # %4 from Mystic = user's IP
    elif len(sys.argv) >= 2:
        # Could be just node number
        pass

    while True:
        area_name, area_lat, area_lon = location_chooser(user_ip)
        result = weather_loop(area_name, area_lat, area_lon)
        if result == 'CHANGE_LOCATION':
            continue
        break


if __name__ == '__main__':
    main()
