# Changelog

All notable changes to this project will be documented in this file.

## [1.0] - 2026-03-08

First stable public release.

### Features
- Area overview table showing all configured locations at a glance
- Detailed current conditions with ASCII weather icons
- 6-hour temperature trend graph with colored horizontal bars
- Extended forecast (8 periods) with paginated display for 25-line terminals
- Active NWS weather alerts with severity-based coloring
- Full ANSI color and CP437 box-drawing character support
- Configurable locations via environment variable or source edit
- Automatic UTC-to-local-time conversion for trend graph
- No external dependencies (Python 3 stdlib only)

### Bug Fixes Since Development

The following issues were encountered and resolved during development
(versions 0.1 through 0.9) before the 1.0 release:

#### v0.1 — Initial Prototype
- Basic NWS API integration with single location
- Plain text output, no ANSI formatting

#### v0.2 — ANSI Formatting
- Added CP437 box drawing and ANSI colors
- **Bug**: CP437 characters (box drawing, block chars) rendered as garbled
  UTF-8 sequences. Python's default stdout encoding is UTF-8, which encodes
  `\xdb` as the 2-byte sequence `\xc3\x9b` instead of the raw byte `\xdb`.
- **Fix**: Wrapped stdout with `io.TextIOWrapper(sys.stdout.buffer, encoding='latin-1')`.
  Latin-1 passes bytes 0x80-0xFF through unchanged, which is exactly what
  CP437 terminals expect.

#### v0.3 — Box Drawing Alignment
- **Bug**: Box lines had inconsistent widths. The right border `|` appeared
  at different columns depending on content length, creating a ragged edge.
  Three separate causes:
  1. `box_line()` padding formula was `width - 2 - len(text)` but should be
     `width - 3 - len(text)` (the leading space after the left `|` wasn't
     counted).
  2. `box_top()` title remaining calculation was off by 1.
  3. Title text containing ANSI color codes inflated the measured string
     length, since `len()` counts escape characters.
- **Fix**: Created `visible_len()` function that strips ANSI escape sequences
  (`\033\[[0-9;]*m`) before measuring. Used it in all box functions. Corrected
  the padding arithmetic.

#### v0.4 — Multi-Location Support
- Added 5 Pensacola area locations
- Area overview table on entry
- 3-column menu layout

#### v0.5 — Forecast Pagination
- **Bug**: The 8-period forecast (26+ lines with box borders) exceeded a
  standard 25-line terminal. Users only saw the bottom portion of the
  forecast, missing the first few days entirely.
- **Fix**: Split forecast into pages of 4 periods each. Added "Press ENTER
  to continue" pause between pages.

#### v0.6 — Content Pacing
- **Bug**: After selecting a location, current conditions + forecast +
  alerts all rendered at once. On a 25-line terminal, content scrolled past
  too fast — users reported missing current conditions entirely because the
  forecast pushed it off screen.
- **Fix**: Added pause between current conditions and forecast sections.
  Added pause after alerts before returning to menu.

#### v0.7 — Temperature Trend (Vertical Bar Graph)
- Added `get_temp_history()` to fetch NWS observation history
- Added vertical bar chart using block characters
- **Bug**: The vertical bar chart was confusing. With a small temperature
  range (e.g., 64-70F) spread across 5 rows, bars appeared as disconnected
  floating blocks rather than a readable trend. A 70F reading showed blocks
  at the top 3 rows; a 66F reading showed blocks at the bottom 2 rows; there
  was no visual connection between them.
- **Fix**: Replaced with horizontal bar layout in v0.8.

#### v0.8 — Temperature Trend (Horizontal Bars)
- Rewrote trend graph as horizontal bars: one row per hour with time label,
  temperature value, and a proportional colored bar. Much clearer at showing
  the actual temperature rise/fall pattern.
- **Bug**: Calling `temp_trend_graph(hourly, width=68)` but the function
  signature was changed to `temp_trend_graph(hourly, bar_max=40)`.
  The mismatched keyword argument caused a `TypeError` crash.
- **Fix**: Updated the call site to use `bar_max=40`.

#### v0.9 — Timezone Fix
- **Bug**: The temperature trend graph showed hours in UTC. The NWS API
  returns ISO 8601 timestamps with UTC times (e.g., `2026-03-08T14:30:00+00:00`).
  The code extracted `ts[11:13]` directly, so a 9am Central observation
  showed as "2p" in the graph.
- **Fix**: Calculate UTC offset from system localtime using
  `datetime.fromtimestamp(now) - datetime.utcfromtimestamp(now)`, which
  automatically handles DST transitions. Apply offset to convert UTC hours
  to local hours.

## [0.1] - 2026-03-07

Initial development version (not released).
