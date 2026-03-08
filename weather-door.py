#!/usr/bin/env python3
"""NWS Weather Door — ANSI weather display for BBS systems.

Interactive weather door using National Weather Service (weather.gov) data.
Shows current conditions, 6-hour temperature trend, extended forecast,
and active weather alerts with full ANSI color and CP437 box drawing.

Designed for Mystic BBS but works with any BBS that can launch an
external program and pass I/O through the user's terminal.

Configuration: Set environment variables or edit the LOCATIONS dict below.
See README.md for setup instructions.

Version: 1.0
License: Non-Commercial (see LICENSE file)
"""

import io
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# Force stdout to binary-safe mode (CP437 box-drawing chars must go out as raw bytes)
# This is critical: Python defaults to UTF-8 which mangles CP437 characters like
# \xdb (full block), \xda (box corner), etc. Latin-1 passes bytes through unchanged.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='latin-1', errors='replace')
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='latin-1', errors='replace')

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
# Locations can be set via the WEATHER_LOCATIONS environment variable as JSON:
#   export WEATHER_LOCATIONS='{"1":["Pensacola",30.4213,-87.2169],"2":["Mobile",30.6954,-88.0399]}'
#
# Or edit the DEFAULT_LOCATIONS dict below directly.
#
# Each entry: key -> (display_name, latitude, longitude)
# Latitude/longitude in decimal degrees (use Google Maps to find coordinates).
# Keys should be single characters (1-9, A-Z) for easy menu selection.
# Maximum recommended: 9 locations (for single-key selection).

DEFAULT_LOCATIONS = {
    '1': ('Pensacola',         30.4213, -87.2169),
    '2': ('Gulf Breeze',       30.3571, -87.1672),
    '3': ('Pensacola Beach',   30.3318, -87.1364),
    '4': ('Navarre',           30.4019, -86.8639),
    '5': ('Fort Walton Beach', 30.4058, -86.6187),
}

# Area name shown in header and overview title (set via WEATHER_AREA_NAME env var)
DEFAULT_AREA_NAME = 'Pensacola Area'

# NWS API requires a User-Agent string identifying your application.
# Set via WEATHER_USER_AGENT env var, or edit the default below.
# NWS asks for a contact email in the UA string.
DEFAULT_USER_AGENT = 'NWS-Weather-Door/1.0 (your-email@example.com)'

# Number of hours to show in the temperature trend graph
TREND_HOURS = 6

# ---------------------------------------------------------------------------
# Load configuration from environment
# ---------------------------------------------------------------------------
def load_locations():
    """Load locations from WEATHER_LOCATIONS env var or use defaults."""
    env = os.environ.get('WEATHER_LOCATIONS', '')
    if env:
        try:
            raw = json.loads(env)
            locations = {}
            for key, val in raw.items():
                locations[str(key)] = (val[0], float(val[1]), float(val[2]))
            return locations
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            pass
    return DEFAULT_LOCATIONS


LOCATIONS = load_locations()
AREA_NAME = os.environ.get('WEATHER_AREA_NAME', DEFAULT_AREA_NAME)
NWS_UA = os.environ.get('WEATHER_USER_AGENT', DEFAULT_USER_AGENT)
NWS_HEADERS = {'User-Agent': NWS_UA, 'Accept': 'application/geo+json'}

# ---------------------------------------------------------------------------
# ANSI color codes
# ---------------------------------------------------------------------------
RST = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'
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
BG_BLUE = '\033[44m'
BG_BLACK = '\033[40m'

# ---------------------------------------------------------------------------
# Box drawing characters (CP437 compatible)
# ---------------------------------------------------------------------------
TL = '\xda'       # top-left corner
TR = '\xbf'       # top-right corner
BL = '\xc0'       # bottom-left corner
BR = '\xd9'       # bottom-right corner
HZ = '\xc4'       # horizontal line
VT = '\xb3'       # vertical line
LT = '\xc3'       # left-T junction
RT = '\xb4'       # right-T junction
TT = '\xc2'       # top-T junction
BT = '\xc1'       # bottom-T junction
BLK_FULL = '\xdb'  # full block
BLK_HALF = '\xdd'  # half block

WIDTH = 78

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def out(text=''):
    """Write text to stdout (user's terminal)."""
    sys.stdout.write(text)
    sys.stdout.flush()


def outln(text=''):
    """Write line to stdout with CR+LF (required for BBS terminals)."""
    out(text + '\r\n')


def visible_len(text):
    """Return visible length of text after stripping ANSI escape codes."""
    return len(re.sub(r'\033\[[0-9;]*m', '', text))


def pause():
    """Wait for user to press Enter."""
    out(f'\r\n{DIM}  Press ENTER to continue...{RST}')
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass

# ---------------------------------------------------------------------------
# NWS API functions
# ---------------------------------------------------------------------------
def fetch_json(url):
    """Fetch JSON from URL with NWS headers."""
    req = urllib.request.Request(url, headers=NWS_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


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
    """Get hourly temperature history from NWS observations.

    Fetches recent observations, deduplicates by hour, converts UTC
    timestamps to local time using the system timezone, and returns
    the last TREND_HOURS data points.
    """
    try:
        obs = fetch_json(f'https://api.weather.gov/stations/{station_id}/observations?limit=100')
        seen = set()
        hourly = []
        # Determine UTC offset using system localtime (handles DST automatically)
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
        return hourly[-TREND_HOURS:]
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def deg_to_compass(deg):
    """Convert degrees to compass direction."""
    if deg is None:
        return ''
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
            'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    idx = round(deg / 22.5) % 16
    return dirs[idx]


def temp_color(temp_f):
    """Return ANSI color code based on temperature (Fahrenheit)."""
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
    """Return a colored temperature bar (fallback when no trend data)."""
    if temp_f is None:
        return f'{DIM}(n/a){RST}'
    bars = max(0, min(max_width, int(temp_f / 110 * max_width)))
    color = temp_color(temp_f)
    return f'{color}{"=" * bars}{DIM}{"." * (max_width - bars)}{RST} {color}{temp_f}F{RST}'


def temp_trend_graph(hourly, bar_max=40):
    """Build a horizontal bar graph of temperature trend over recent hours.

    One row per hour: time label, temp value, horizontal bar.
    Bar length is proportional to temp within the observed range.
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
        h = int(hour)
        suffix = 'a' if h < 12 else 'p'
        h12 = h % 12 or 12
        label = f'{h12}{suffix}'

        bar_len = max(1, int((temp - t_min) / t_range * bar_max))
        tc = temp_color(temp)
        bar = f'{tc}{BLK_FULL * bar_len}{RST}'

        lines.append(f'{DIM}{label:>4}{RST} {tc}{temp:>3}F{RST} {bar}')

    return lines


def weather_icon(desc):
    """Return 5-line ASCII art weather icon based on condition description."""
    d = desc.lower()
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
        return [
            f'{CYAN}     {RST}',
            f'{CYAN}  ?  {RST}',
            f'{CYAN}  ?  {RST}',
            f'{CYAN}     {RST}',
            f'{CYAN}     {RST}',
        ]

# ---------------------------------------------------------------------------
# Box drawing
# ---------------------------------------------------------------------------
def hline(char=HZ, width=WIDTH, color=CYAN):
    """Draw a horizontal line."""
    return f'{color}{char * width}{RST}'


def box_top(title='', width=WIDTH):
    """Draw top of a box with optional title."""
    if title:
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
    """Draw a line inside a box with auto-padding."""
    text_vis = visible_len(text)
    padding = width - 3 - text_vis
    if padding < 0:
        padding = 0
    return f'{BRIGHT_CYAN}{VT}{RST} {text}{" " * padding}{BRIGHT_CYAN}{VT}{RST}'


def box_divider(width=WIDTH):
    """Draw a divider inside a box."""
    return f'{BRIGHT_CYAN}{LT}{HZ * (width - 2)}{RT}{RST}'

# ---------------------------------------------------------------------------
# Screen sections
# ---------------------------------------------------------------------------
def display_header():
    """Show the weather door header."""
    outln()
    outln(f'{BRIGHT_CYAN}  {BLK_FULL}{BLK_FULL}  {BRIGHT_WHITE}W E A T H E R   S T A T I O N{RST}')
    outln(f'{CYAN}  {BLK_FULL}{BLK_FULL}  {DIM}{AREA_NAME} Conditions & Forecast{RST}')
    outln(f'{CYAN}  {BLK_FULL}{BLK_FULL}  {DIM}Source: National Weather Service (weather.gov){RST}')
    outln(hline())
    outln()


def display_current(name, conditions):
    """Display current conditions with ANSI art and temperature trend."""
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

    temp = conditions.get('temp_f')
    tc = temp_color(temp)
    data_lines = [
        f'{BRIGHT_WHITE}{desc}{RST}',
        f'{DIM}Temperature:{RST}  {tc}{temp}F{RST}' if temp else f'{DIM}Temperature:{RST}  n/a',
        f'{DIM}Feels Like:{RST}   {tc}{temp}F{RST}' if temp else '',
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


def display_menu():
    """Show location selection menu in 3 columns."""
    outln()
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
    outln(f'  {BRIGHT_CYAN}R{RST} {DIM}-{RST} {WHITE}Refresh Overview{RST}    '
          f'{BRIGHT_CYAN}W{RST} {DIM}-{RST} {WHITE}Weather Alerts{RST}      '
          f'{BRIGHT_CYAN}Q{RST} {DIM}-{RST} {WHITE}Return to BBS{RST}')
    outln()


def display_overview():
    """Show quick overview of all locations."""
    results = []
    for key in sorted(LOCATIONS.keys()):
        name, lat, lon = LOCATIONS[key]
        cond = get_current_conditions(lat, lon)
        results.append((name, cond))

    outln(box_top(f'{AREA_NAME} Overview'))
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
    """Show all active alerts for the first configured location."""
    outln()
    outln(f'{BRIGHT_WHITE}  Checking for active alerts...{RST}')
    first_key = sorted(LOCATIONS.keys())[0]
    _, lat, lon = LOCATIONS[first_key]
    alerts = get_alerts(lat, lon)
    outln()
    if not alerts:
        outln(box_top('Weather Alerts'))
        outln(box_line(f'  {GREEN}No active weather alerts for the {AREA_NAME}.{RST}'))
        outln(box_bottom())
    else:
        outln(f'{BRIGHT_YELLOW}  {len(alerts)} active alert(s):{RST}')
        outln()
        display_alerts(alerts)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    display_header()

    outln(f'{DIM}  Loading {AREA_NAME.lower()} conditions...{RST}')
    outln()
    display_overview()

    # Show any active alerts on entry
    first_key = sorted(LOCATIONS.keys())[0]
    _, lat, lon = LOCATIONS[first_key]
    alerts = get_alerts(lat, lon)
    display_alerts(alerts)

    while True:
        display_menu()
        out(f'{BRIGHT_GREEN}  Weather>{RST} ')

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

        elif choice == 'R':
            outln()
            outln(f'{DIM}  Refreshing...{RST}')
            outln()
            display_overview()
            first_key = sorted(LOCATIONS.keys())[0]
            _, lat, lon = LOCATIONS[first_key]
            alerts = get_alerts(lat, lon)
            display_alerts(alerts)

        elif choice == 'W':
            display_alerts_view()
            pause()

        elif choice in LOCATIONS:
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

            pause()

        else:
            outln(f'{RED}  Invalid selection.{RST}')


if __name__ == '__main__':
    main()
