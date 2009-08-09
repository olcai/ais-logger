## Introduction

### Overview

*AIS Logger* is a simple viewer and logger for data received by
AIS-transponders or -receivers.

It can read data from serial ports or via network and features two
list views where the received data are displayed. There is also a
built-in map for displaying positions of all ships. One can set alerts
and associate remarks with particular objects (ships). It can also log
data to database files (using [SQLite][sqlite]) and keep an ID
database for displaying data in the list views.

AIS Logger is free software licensed under a [MIT-like][mitlicense]
license.

[sqlite]:	http://www.sqlite.org
[mitlicense]:   http://www.opensource.org/licenses/mit-license.php


### Features

_Powerful data routing & handling_

 * Decoding of standard NMEA AIVDM messages (including messages from
   Class B transponders)
 * Decoding of NMEA SAAB TransponderTech's PAIS messages
 * Reading raw data from several serial ports simultaneously 
 * Reading data from any network server sending raw data
 * Can act as a network server sending raw data
 * Can act as a serial port server sending raw data
 * User can set a manual position or use position data from a GPS unit

_Robust and flexible logging_

 * Can log data to a SQLite database file at given intervals
 * Can log ID data to SQLite database file at given intervals
 * Can use ID data from file to set IMO nbr, name and callsign

_Open & free - no vendor lock in_

 * Alert-and-remark file is in a simple CSV format for easy external
   editing
 * Can export current view from "Set alerts and remarks" window
 * Uses maps in MapGen format (shorelines)
 * Platform independent (*nix and Windows)

_Simple but customizable_

 * User can set alerts and remarks on objects (based on MMSI)
 * Has variable grey-out and deletion times
 * All columns in the list views are sortable
 * Customizable views and map colors
 
_Additional features_

 * A simple map displaying all objects
 * Can calculate positions in GEOREF
 * Automatic calculation of distance and bearing
 * Can play a wave file for objects with a sound alert set
 

### Installation

Please read the README.md included in the archive. It contains
installation instructions for different systems.
