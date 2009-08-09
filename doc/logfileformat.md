## Log file format

If the log to file setting is activated, a log file is saved at
regular intervals to a [SQLite][sqlite] database file.

The log file database contains two tables: _position_ and _metadata_.

A row is inserted in the position table for each object that has a
newer "last updated time" compared to the last time the database was
written to.

To save space, a row will only be inserted in the metadata table for
an object if it is either new since the last database write or if data
in the affected columns has changed.

The position table contains seven columns:

 * time (time for the logged position in ISO 8601 format)
 * MMSI number
 * latitude (ex: N48083447, N 48 degrees, 08.3447 minutes)
 * longitude (ex: W023596527, W 023 degrees, 59.6527 minutes)
 * GEOREF (ex: LKGD 0008)
 * SOG (speed over ground, knots)
 * COG (course over ground, degrees)

The metadata table contains ten columns:

 * time (time for last update on object in ISO 8601 format)
 * MMSI number
 * IMO number
 * name
 * type (AIS type number, two digits)
 * callsign
 * destination
 * ETA (in MMDDHHMM format)
 * length (in meters)
 * width (in meters)

The reason for having time and MMSI for each row in both tables is that
it should be easy to connect metadata with a position and vice versa.

[sqlite]:   http://www.sqlite.org
