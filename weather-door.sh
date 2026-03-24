#!/bin/bash
export TERM=pcansi
exec /usr/bin/python3 /mystic/doors/weather/weather-door.py "$@"
