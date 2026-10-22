# World airport atlas

Public OurAirports snapshots are bundled with the static site. No account or API key is required.

Regenerate using a new empty cache directory to fetch all three source files together:

    python tools/build_airports.py --cache /path/to/new-cache --date YYYY-MM-DD

The build creates gzip and plain JSON plus a source manifest with retrieval date and SHA-256 hashes. Keep both representations: gzip is used in modern browsers, plain JSON is the fallback.

The default view includes large, medium and small airports; heliports, seaplane bases, balloonports and closed records are available through filters. Source names and identifiers are preserved. ICAO codes are kept distinct from GPS/local identifiers. The longest non-closed published runway is shown when available.

Verification (with jsdom installed):

    node --test tests/airports.test.cjs

Data: https://ourairports.com/data/ (Public Domain).
