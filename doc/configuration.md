## Configuration

All the settings available in the Settings Window are saved to a
configuration file (default file name: default.ini). The configuration
file can be manually edited, but caution is advised. There are
currently no error-checking done to the configuration file and there
is a possibility that the program will crash on bad input. One can
also specify which configuration file to use as a command line
argument. Starting the program with "-c file" or "--config file" will
force the program to load the given configuration file.

__NOTE:__ When pressing the "Apply" button the in-memory configuration
is updated, but most of the options will have no effect. One has to
press "Save" and restart the program for it to use all new settings.


### Common Tab

_Threshold for greying-out objects_  
A value in seconds for the threshold between last update time and
current time. If an object reaches the threshold it will become grey
in the list views and on the map.

_Threshold for removal of objects_  
A value in seconds for the threshold between last update and current
time. If an object reaches the threshold it will be deleted from
memory, map and list views. Please note that if this value is lower
than the "time between loggings" for the database log file, the last
reported position of an object may not be saved to the log file.

_Time between updating GUI with new data_  
A value in seconds between updating the list views and map with new
data. A lower value puts a greater load on the CPU of the computer. If
the program uses too much CPU time, raise the value.

_Number of updates to an object before displaying_  
A value for how many messages the program must receive from an object
before displaying it in the list views and on the map.

_Enable display of Class B stations_  
If enabled, the program will display both Class A and Class B
transponders. If disabled the program will only display Class A
transponders. Class A transponders are used on large (commercial)
vessels, while Class B transponders is used on small vessels such as
sailing boats.

_Enable display of base stations_  
If enabled, the program will display base stations. Base stations are
fixed transponders, mostly located on land.

_Position display format_  
This selects how the program display latitude and longitude. Available
formats are decimal degrees, degrees with decimal minutes, and degrees
with both minutes and seconds.

_Use position data from source_  
The program can use an external positioning source, such as a GPS
receiver unit, for setting its own location. The own location is used
for calculating bearing and distance to objects. Here one can choose
from which source the program will use GPS NMEA messages.

_Use the supplied position and ignore position messages_  
Checking the box will make the program discard any incoming NMEA data
containing own position from, for example, a GPS receiver. All
calculations of distance and bearing to objects will instead be made
from the position supplied in the position fields.

_Latitude_ and _Longitude_ are set in degrees, minutes and seconds.


### Serial ports Tab

All settings relating to receiving and sending data through serial
ports are located under the tab "serial ports".

The program can handle an arbitrary number of serial ports. One adds
and deletes serial ports in the upper box named _Choose serial port to
configure_. Choose which port to configure in the box. When inserting
a new port, it will be given a symbolic name consisting of "serial\_X"
where X is a letter. This symbolic name is used in the source field
that indicates where a position message arrived from. After selecting
a port in the box, its properties can be edited in the box called
_Serial port settings_.

_Activate reading data from this serial port_  
If enabled, the program will try to open the port and read data from
it.

_Send data to serial server_  
If enabled, any data received on this serial port will be forwarded to
the serial server if it is activated. This means that it is possible
to forward data from several sources to another serial port in the
system.

_Send data to network server_  
If enabled, any data received on this serial port will be forwarded to
the network server if it is activated. This means that it is possible
to forward data from a multitude of ports to client programs
connecting via a network.

_Port_  
A box where the serial port can be selected or entered. Example for
Windows: "Com1". Example for *nix: "/dev/ttyS0".

_Speed_  
A box where the port speed (in baud) can be selected or
entered. Common port speeds are "38400" and "9600" baud.

_Software flow control_  
Activate XON/XOFF software flow control (normally off)

_RTS/CTS flow control_  
Activate RTS/CTS hardware flow control (normally off)

The program can also forward incoming data, both from serial ports and
from incoming data from a network, to a serial port in the
system. This functionality is controlled with the settings in the box
_Settings for acting as a serial server_.

_Activate serial server (relay incoming data)_  
If enabled, the program will act as a serial port server, forwarding
data from the ports that have forwarding to serial port enabled.

_Port_  
A box where the serial port can be selected or entered. Example for
Windows: "Com1". Example for *nix: "/dev/ttyS0".

_Speed_  
A box where the port speed (in baud) can be selected or
entered. Common port speeds are "38400" and "9600" baud.

_Software flow control_  
Activate XON/XOFF software flow control (normally off)

_RTS/CTS flow control_  
Activate RTS/CTS hardware flow control (normally off)


### Network Tab

All settings relating to receiving and sending data through a network
are located under the tab _Network_.

The program can handle an arbitrary number of connections to servers
sending raw data. One adds and deletes network servers in the upper
box named _Choose network server to configure_. Choose which
connection to configure in the box. The server name/IP address is used
in the source field that indicates where a position message arrived
from. After selecting a server in the box, its properties can be
edited in the box called _Settings for reading from a network server_.

_Activate reading data from this network server_  
If enabled, use the supplied host address and port and try to
establish a TCP connection.

_Send data to serial server_  
If enabled, any data received from this server will be forwarded to
the serial server if it is activated. This means that it is possible
to forward data from network sources to a serial port in the system.

_Send data to network server_  
If enabled, any data received from this sever will be forwarded to the
network server if it is activated. This means that it is possible to
forward data from several network sources to other client programs
connecting via a network.

_Address of streaming host_  
The IP address or hostname of the remote host to read data from.

_Port of streaming host_  
IP port of the remote host to read data from.

The program can also forward incoming data, both from serial ports and
from incoming data from a network, to other clients connection via a
network. This is made possible by the built-in network server. The
functionality is controlled with the settings in the box _Settings for
acting as a network server_.

_Activate network server (relay incoming data)_  
If enabled, the program will act as a simple network TCP server,
forwarding data from the ports that have forwarding to network server
enabled.

_Server address (this server)_  
The IP address of the network interface on which the program should
answer incoming connections. This field needs to be set even if there
only is one network interface in the operating system.

_Server port (this server)_  
The IP port to answer incoming connections on. Please use a port
number higher than 1024 (to avoid collisions with registered
protocols).


### Logging Tab

The program can log data to two files: a database file that logs full
position and ship data, and an identification database (IDDB) file
that logs a ships' MMSI number, IMO number, name and callsign. The
IDDB file is used to display data when static information currently is
missing. For more information about the database log file format,
please see the chapter on log formats.

_Activate logging to database file_  
If enabled, write any new data since last write to the specified file
at the interval given.

_Enable logging of base stations_  
If enabled, treat base stations as a normal object. This means that
the position of base stations is saved with every database write. If
disabled, no base stations will be logged at all in the database.

_Time between loggings_  
A value in seconds between each write to file.

_Log file_  
The file to log to (in SQLite format).

_Activate logging to IDDB file_  
If enabled, overwrite the IDDB with the data currently in memory to
the specified file at the interval given.

_Time between loggings_  
A value in seconds between each write to file.

_Log file_  
The file to log to (in SQLite format).

_Activate exception logging to file (for debugging)_  
If enabled, a filed called "except.log" will be created in the program
directory. All unhandled exceptions and error messages will be written
to this file to aid debugging of the program.


### Alerts/Remarks Tab

_Read alert/remark file at program startup_  
If enabled, read the specified file when the program starts. This
means that all data in the alert/remark file will be used. This file
has to be read at program startup to be able to save any changes to
alerts and remarks.

_Alert/remark file_  
The file containing the alerts and remarks to be read at startup.

_Activate sound alert_  
If enabled, the program will play the specified wave file when a new
object with an associated alert is created.

_Sound alert file_  
The file to play on a new alert (in wave format).

_Activate maximum distance_  
If enabled, objects with alerts will only be alerted (marked with red
color and displayed in the alert list) when they are within the
specified distance.

_Maximum distance to alert object_  
The maximum distance to an alerted objects in kilometers.


### List & Alert View Tabs

These tabs controls the displayed columns and their order in the list
views.

There are two lists shown: _not active columns_ are columns that are
currently not shown in the view. _Active columns_ are columns that are
currently shown in the view.

To add or remove a column from the active columns, select the column
in the list and press the "<--" or the "-->" button. To change the
order of the active columns, select one and press the "Up" or "Down"
button. The topmost column is the column furthest to the left in the
list view.


### Map Tab

The program can plot objects (ships, base stations) on a simple vector
map. There are a few available configuration options for this.

_Map file_  
The file name of a map shape file in the MapGen format. This file is
used for drawing the shore lines on the map.

The map color settings are pretty straight forward. To set a color,
press the color button to the right. A color chooser is shown where
one can choose the desired color and press OK to accept it.


