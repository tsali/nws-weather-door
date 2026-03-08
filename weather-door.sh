#!/bin/bash
# NWS Weather Door — BBS wrapper script
#
# This script is called by Mystic BBS (or similar) to launch the weather door.
# It sets TERM=xterm to ensure ANSI escape codes work properly, since some
# BBS software sets TERM=dumb which can cause issues.
#
# Mystic BBS menu configuration:
#   Command type: DC (Door/Shell command)
#   Data: /path/to/weather-door.sh %N
#
# The %N parameter (node number) is accepted but not currently used.
# It is included for compatibility with multi-node BBS setups.

export TERM=xterm

# Optional: set configuration via environment variables
# export WEATHER_LOCATIONS='{"1":["CityName",lat,lon],...}'
# export WEATHER_AREA_NAME="My Area"
# export WEATHER_USER_AGENT="MyBBS-Weather/1.0 (admin@example.com)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec /usr/bin/python3 "$SCRIPT_DIR/weather-door.py"
