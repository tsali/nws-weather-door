# NWS Weather Door

A free, open-source ANSI weather door for BBS systems, powered by the National Weather Service API. No API keys required. No registration. No shareware nags. Just weather.

```
  ██  W E A T H E R   S T A T I O N
  ██  Pensacola Area Conditions & Forecast
  ██  Source: National Weather Service (weather.gov)

  ┌── Choose Your Location ──────────────────────────────────────────────┐
  │                                                                      │
  │  1 - Louisville, Kentucky (your location)                            │
  │  2 - Pensacola, FL (BBS home)                                       │
  │  3 - Search by city or zip code                                     │
  │                                                                      │
  └──────────────────────────────────────────────────────────────────────┘
```

## Features

- **IP Geolocation**: Automatically detects the caller's location from their IP and offers it alongside the BBS home area
- **Location Search**: Search by city name or US zip code (geocoding via open-meteo.com)
- **Area Overview**: Quick summary table of all configured local area locations
- **Current Conditions**: ASCII weather icons, temperature, humidity, wind, pressure, dewpoint, visibility
- **24-Hour Temperature Trend**: Horizontal bar graph of hourly forecast temps, color-coded by range, with day/night shading
- **Precipitation Forecast**: Hourly rain probability bars + 7-day expected rainfall accumulation chart
- **Wind Trend**: 24-hour wind speed forecast with direction, color-coded by intensity
- **7-Day Visual Forecast**: High/low temperature range bars scaled across the week
- **Extended Forecast**: 8-period NWS forecast, paginated to fit 25-line terminals
- **Weather Alerts**: Active NWS alerts with severity coloring
- **Doppler Radar**: Composite radar overlay on OpenStreetMap tiles, rendered as ANSI art via chafa
- **Per-Location Drill-Down**: Select any location, then access all trend views for that specific area
- **Change Location**: Switch between your IP location, the BBS area, or search for anywhere — without restarting
- **ANSI Graphics**: Full 16-color with CP437 box-drawing characters
- **No Dependencies**: Python 3 standard library only (no pip packages required)
- **No API Keys**: Uses the free NWS API (US coverage) and open-meteo geocoding
- **No Registration**: Fully functional. No nag screens. No paywalled features.

## Requirements

- Python 3.6 or later
- Internet access to api.weather.gov (no API key needed)
- BBS software that can execute external programs (Mystic BBS, Synchronet, Enigma 1/2, WWIV, etc.)
- Terminal with ANSI color and CP437 character set support (standard for BBS terminals)
- Optional: `chafa` and `iconv` for Doppler radar display; `pillow` (PIL) for radar-fetch.py

## Quick Start

1. Copy files to your BBS doors directory:

```bash
mkdir -p /your/bbs/doors/weather
cp weather-door.py weather-door.sh /your/bbs/doors/weather/
cp radar-fetch.py /your/bbs/doors/weather/   # optional, for Doppler radar
chmod +x /your/bbs/doors/weather/weather-door.sh
```

2. Edit the default BBS-area locations in `weather-door.py` (the `LOCATIONS` dict near the top).

3. Configure your BBS menu to run the door. Pass the user's IP address as the second argument for geolocation.

4. Test from the command line:

```bash
python3 weather-door.py
```

## BBS Setup

### Mystic BBS

Add a menu item:
- **Display Text**: `(W) Weather Station`
- **Hotkey**: `W`
- **Command Type**: `DC`
- **Data**: `/path/to/weather-door.sh %N %4`

`%N` = node number, `%4` = caller's IP address (used for geolocation).

### Synchronet BBS

```ini
[weather]
name=Weather Station
cmd=/path/to/weather-door.sh %n %i
cost=0
settings=NATIVE|STDIO
```

`%n` = node dir, `%i` = caller's IP.

### Enigma 1/2

```hjson
weatherDoor: {
    desc: Weather Station
    module: abracadabra
    config: {
        name: Weather Station
        cmd: /path/to/weather-door.sh
        args: [{node} {clientAddress}]
        io: stdio
    }
}
```

### WWIV BBS

```
Description : Weather Station
Filename    : /path/to/weather-door.sh %N %a
SL          : 10
ANSI        : Yes
Exec Mode   : STDIO
```

### Other BBS Software

The door reads stdin and writes stdout with ANSI escape codes and CR+LF line endings. Pass the user's IP as the second command-line argument for geolocation. If no IP is provided, it skips the "your location" option and defaults to the BBS area.

## Configuration

### Default Locations (BBS Area)

Edit the `LOCATIONS` dictionary in `weather-door.py`:

```python
LOCATIONS = {
    '1': ('Pensacola',         30.4213, -87.2169),
    '2': ('Gulf Breeze',       30.3571, -87.1672),
    '3': ('Pensacola Beach',   30.3318, -87.1364),
    '4': ('Navarre',           30.4019, -86.8639),
    '5': ('Fort Walton Beach', 30.4058, -86.6187),
}
```

Use [Google Maps](https://www.google.com/maps) to find coordinates (right-click any location to copy lat/lon).

### TERM Variable

The wrapper script sets `TERM=pcansi`. If your BBS sets a different TERM value that doesn't support ANSI clear-screen, the door's screen may not clear properly between views. `pcansi` works on most Linux systems with standard terminfo installed.

### Doppler Radar (Optional)

Radar requires:
- `radar-fetch.py` in the same directory (or adjust the path in weather-door.py)
- Python `pillow` package: `pip3 install pillow`
- `chafa` for ANSI rendering: `apt install chafa`
- `iconv` for CP437 translation (usually pre-installed)

## Menu Options

| Key | Function |
|-----|----------|
| 1-5 | View conditions + forecast for a specific area location |
| T | 24-hour temperature trend graph |
| P | Precipitation forecast (hourly probability + 7-day accumulation) |
| G | 24-hour wind speed + direction trend |
| F | 7-day visual forecast with temperature range bars |
| D | Doppler radar (ANSI art rendering) |
| W | Active weather alerts |
| R | Refresh current view |
| L | Change location (return to location chooser) |
| Q | Return to BBS |

When viewing a specific location (1-5), a sub-menu offers T/P/G/F for that location's data.

## How It Works

1. **Location chooser**: Geolocates the caller's IP (via ip-api.com), then offers three choices: their detected location, the BBS home area (Pensacola), or search by city/zip.

2. **City/zip search**: Uses the open-meteo.com geocoding API to resolve city names and postal codes to coordinates. Returns up to 8 results for the user to choose from.

3. **Weather data**: All weather data comes from the free NWS API at `api.weather.gov`:
   - Current conditions from the nearest observation station
   - Hourly forecast (temperature, wind, precipitation probability)
   - 7-day forecast periods
   - Gridpoint quantitative precipitation forecast (QPF)
   - Active alerts

4. **No API keys**: The NWS API is free and requires only a User-Agent header with contact info. The geocoding APIs (ip-api.com, open-meteo.com) are also free with no keys.

## Data Sources

| Source | Purpose | Key Required |
|--------|---------|:------------:|
| [NWS API](https://api.weather.gov) | All weather data | No |
| [ip-api.com](http://ip-api.com) | IP geolocation | No |
| [open-meteo.com](https://open-meteo.com) | City/zip geocoding | No |
| [RainViewer](https://www.rainviewer.com) | Radar tile overlay | No |
| [OpenStreetMap](https://www.openstreetmap.org) | Radar base map tiles | No |

## File Structure

```
nws-weather-door/
├── weather-door.py   # Main door program (~1000 lines)
├── weather-door.sh   # BBS wrapper script (sets TERM, launches Python)
├── radar-fetch.py    # Doppler radar tile compositor (optional)
├── README.md         # This file
├── CHANGELOG.md      # Version history
└── LICENSE           # MIT License
```

## License

MIT License. Do whatever you want with it. See [LICENSE](LICENSE).

## Credits

- Weather data: [National Weather Service API](https://www.weather.gov/documentation/services-web-api)
- Created by RAI for [BBS PCOLA](https://bbs.cultofjames.org) (telnet port 2023, TLS 992)
- Built with Claude Code
