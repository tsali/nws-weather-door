# NWS Weather Door

An ANSI weather door for BBS systems, powered by the National Weather Service API.

Displays current conditions, 6-hour temperature trends, extended forecasts, and active weather alerts with full ANSI color and CP437 box-drawing graphics. Designed for Mystic BBS but works with any BBS software that can execute an external program.

```
  ██  W E A T H E R   S T A T I O N
  ██  Pensacola Area Conditions & Forecast
  ██  Source: National Weather Service (weather.gov)

  ┌── Pensacola Area Overview ──────────────────────────────────────────────┐
  │  Location               Temp    Wind               Conditions          │
  ├────────────────────────────────────────────────────────────────────────┤
  │  Pensacola               70F    8 mph SSW           Partly Cloudy      │
  │  Gulf Breeze             68F    10 mph S            Mostly Cloudy      │
  │  Pensacola Beach         69F    12 mph SSW          Partly Cloudy      │
  │  Navarre                 67F    7 mph SW            Cloudy             │
  │  Fort Walton Beach       66F    9 mph S             Overcast           │
  └────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Area Overview**: Quick summary table of all configured locations on entry
- **Current Conditions**: Detailed view with ASCII weather icon, temperature, humidity, wind, pressure, dewpoint, visibility
- **Temperature Trend**: Horizontal bar graph showing temperature over the last 6 hours, color-coded by temperature range
- **Extended Forecast**: 8-period NWS forecast, paginated to fit 25-line terminals
- **Weather Alerts**: Active NWS alerts with severity coloring (red for severe/extreme, yellow for moderate)
- **ANSI Graphics**: Full color with CP437 box-drawing characters
- **No Dependencies**: Python 3 standard library only (no pip packages)
- **Configurable**: Set your own locations via environment variable or source edit

## Requirements

- Python 3.6 or later
- Internet access to api.weather.gov (no API key needed)
- BBS software that can execute external programs (Mystic BBS, Synchronet, Enigma 1/2, WWIV, etc.)
- Terminal with ANSI color and CP437 character set support (standard for BBS terminals)

## Quick Start

1. Copy `weather-door.py` and `weather-door.sh` to your BBS doors directory:

```bash
mkdir -p /mystic/doors/weather
cp weather-door.py weather-door.sh /mystic/doors/weather/
chmod +x /mystic/doors/weather/weather-door.sh
chmod +x /mystic/doors/weather/weather-door.py
```

2. Edit the locations in `weather-door.py` (or use environment variables — see Configuration below).

3. Configure your BBS menu to run the door (see BBS Setup below).

4. Test it from the command line first:

```bash
python3 /mystic/doors/weather/weather-door.py
```

## Configuration

### Option 1: Edit the Source (Simplest)

Open `weather-door.py` and edit the `DEFAULT_LOCATIONS` dictionary near the top:

```python
DEFAULT_LOCATIONS = {
    '1': ('Pensacola',         30.4213, -87.2169),
    '2': ('Gulf Breeze',       30.3571, -87.1672),
    '3': ('Pensacola Beach',   30.3318, -87.1364),
    '4': ('Navarre',           30.4019, -86.8639),
    '5': ('Fort Walton Beach', 30.4058, -86.6187),
}
```

Each entry is:
```
'key': ('Display Name', latitude, longitude),
```

- **key**: A single character (1-9, A-Z) used for menu selection
- **Display Name**: Shown in menus and headers
- **latitude/longitude**: Decimal degrees — use [Google Maps](https://www.google.com/maps) to find coordinates (right-click any location and copy the coordinates)

Also update:
```python
DEFAULT_AREA_NAME = 'Your Area Name'
DEFAULT_USER_AGENT = 'YourBBS-Weather/1.0 (your-email@example.com)'
```

The NWS API requires a User-Agent string with contact info. They use this to reach out if your application is causing issues. See [NWS API documentation](https://www.weather.gov/documentation/services-web-api).

### Option 2: Environment Variables

Set these in `weather-door.sh` or your BBS door configuration:

```bash
# Locations as JSON: {"key": ["Name", lat, lon], ...}
export WEATHER_LOCATIONS='{
  "1": ["Denver",       39.7392, -104.9903],
  "2": ["Boulder",      40.0150, -105.2705],
  "3": ["Fort Collins", 40.5853, -105.0844]
}'

# Area name for headers
export WEATHER_AREA_NAME="Front Range Colorado"

# NWS API User-Agent (required — include your contact email)
export WEATHER_USER_AGENT="MyBBS-Weather/1.0 (sysop@mybbs.com)"
```

### Finding Coordinates

1. Go to [Google Maps](https://www.google.com/maps)
2. Right-click on the location you want
3. Click the coordinates at the top of the menu (this copies them)
4. The format is `latitude, longitude` (e.g., `39.7392, -104.9903`)
5. Use these values in your location configuration

### NWS API Coverage

The NWS API covers the United States (including territories). If a location is outside NWS coverage, the door will show an error for that location. Each location is resolved to the nearest NWS observation station automatically.

## BBS Setup

### Mystic BBS

Add a menu item in the Mystic menu editor:

1. Open the menu you want to add it to (e.g., `main.mnu` for main menu, or `doors.mnu` for a doors submenu)
2. Add a new menu item:
   - **Display Text**: `(W) Weather Station` (or whatever you prefer)
   - **Hotkey**: `W`
   - **Command Type**: `DC` (Door/shell Command)
   - **Data**: `/mystic/doors/weather/weather-door.sh %N`

The `%N` passes the node number to the script (accepted but not currently used).

If you prefer to use the Mystic menu editor from the command line:
```
sudo /mystic/mis -cfg
```
Navigate to: Configuration > Menu Editor > (select menu) > Add Item

### Synchronet BBS

Add to your `ctrl/xtrn.ini` or use SCFG:

```ini
[weather]
name=Weather Station
cmd=/path/to/weather-door.sh %N
cost=0
settings=NATIVE|STDIO
```

### Enigma 1/2

Add to your `menu.hjson`:

```hjson
weatherDoor: {
    desc: Weather Station
    module: abracadabra
    config: {
        name: Weather Station
        cmd: /path/to/weather-door.sh
        nodeNum: {node}
        io: stdio
    }
}
```

### WWIV BBS

Add as a chain in the chain editor:

```
Description : Weather Station
Filename    : /path/to/weather-door.sh %N
SL          : 10
AR          :
ANSI        : Yes
Exec Mode   : STDIO
```

### Other BBS Software

The door reads from stdin and writes to stdout with ANSI escape codes and CR+LF line endings. Any BBS that can:
1. Execute an external program
2. Pipe the user's terminal I/O to the program's stdin/stdout

...will work. No drop file (DOOR.SYS, DORINFO, etc.) is needed.

## How It Works

1. **On entry**: Fetches current conditions for all configured locations from NWS and displays an overview table, plus any active weather alerts.

2. **Location detail**: When the user selects a location, the door fetches:
   - Current conditions from the nearest NWS observation station
   - Last 6 hours of observations for the temperature trend graph
   - 8-period extended forecast
   - Active weather alerts for the area

3. **NWS API**: All data comes from the free NWS API at `api.weather.gov`. No API key is required. The API has rate limits but they are generous for BBS use. The door makes ~3-6 API calls per location view.

4. **Timezone handling**: NWS returns timestamps in UTC. The door converts to local time using the BBS server's system timezone. Make sure your server's timezone is set correctly (`timedatectl` on systemd systems).

## Troubleshooting

### Garbled box-drawing characters

The door outputs CP437 box-drawing characters (bytes 0x80-0xFF). If you see garbled multi-byte sequences like `├` instead of clean box lines, the stdout encoding is wrong. The door forces `latin-1` encoding on stdout to handle this, but if something in your BBS pipeline re-encodes the output, you may see issues.

**Fix**: Ensure nothing between the door and the user's terminal is doing UTF-8 conversion. Most BBS software handles this correctly.

### "Error fetching conditions"

The NWS API may be temporarily unavailable or the location may be outside NWS coverage (US only). Check:
- Internet connectivity from the BBS server: `curl -s https://api.weather.gov/points/30.42,-87.22`
- That your coordinates are within the US

### Times shown in wrong timezone

The door uses the system timezone. Check with:
```bash
timedatectl
# or
date
```

Set timezone if needed:
```bash
sudo timedatectl set-timezone America/Chicago
```

### Door exits immediately / no output

1. Test directly: `python3 /path/to/weather-door.py`
2. Check Python version: `python3 --version` (needs 3.6+)
3. Check the wrapper script has the correct path to `python3`

## File Structure

```
nws-weather-door/
├── weather-door.py   # Main door program
├── weather-door.sh   # BBS wrapper script (sets TERM, launches Python)
├── README.md         # This file
├── CHANGELOG.md      # Version history and bug fix details
└── LICENSE           # MIT License
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Credits

- Weather data: [National Weather Service API](https://www.weather.gov/documentation/services-web-api)
- Created by RAI for [BBS PEPSICOLA](https://bbs.cultofjames.org) (Mystic BBS A45)
- Built with assistance from Claude Code
