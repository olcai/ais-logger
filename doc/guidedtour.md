## Guided Tour

This is a basic guide to the different windows in AIS Logger and what
you can do with them. Please see the later chapters for specific
information.


### Main Window

When you start the program it defaults to displaying two list views of
equal size. The upper one is simply called _the list view_ because it
contains all the received objects. The lower one is called _the alert
view_ and will only display objects with associated alerts. The two
views are otherwise basically the same; all the operations one can do
on an object in the list view one can also perform on an object in the
alert view.

Objects in the list view where the IMO number, the name and callsign
has an apostrophe (') directly behind it has taken that data from the
identification database. When a real static message has been received
containing these values, the apostrophes is removed and the actually
received data is shown.

The columns in each view are fully sortable and customizable. Sorting
is done by clicking on the column label. To reverse the sort order
simply click on the label again. Resizing is done by positioning the
cursor on the right edge of a column label, holding down the left
mouse key and dragging the column to the intended size. To change what
columns are visible and in which order, use the settings dialog.

To change the size ratio between the list and alert view, position the
cursor between the list views' lower scrollbar and the alert views'
column headers.  Hold down the left mouse key and drag to appropriate
size. To hide the alert view, use "View/Show alert view" or press
F8.  To display a hidden alert view, press F8 (or use the menu) again.

Both views are updated at a given interval (every two seconds as
default). 

At the bottom of the Main Window there is a status row. The row
displays the "own position" of the receiver (if set), the total number
of objects tracked and the number of greyed-out objects. The status
row also displays additional information when hovering the mouse over
a menu choice.

When right-clicking on an object a menu will pop up. One can then
choose to display the object in a detail window or zoom to the object
on map. One can also display a detail window by activating an object
by selecting it and pressing enter or by double clicking on it.


### Detail Window

The Detail Window displays all data on a chosen object. To display the
window, just activate an object in a list. Activation is done either via
the keyboard (move with the arrow keys and activate with enter) or by
double-clicking on an object with the mouse.

If the IMO number, the name and callsign has an apostrophe (')
directly behind them, the values are fetched from the identification
database. When a real static message has been received containing
these values, the apostrophes are removed and the actually received
data is shown.

There are a few fields in the window that we'll study in detail:

The _Nation_ field contains data from a file called mid.lst in the
data directory. The first three digits in the MMSI number are actually
called the Maritime Identification Digits (MID). Each nation has a
number of MIDs allocated. There are also entities with MIDs that have
no ISO two-letter code allocated. The field will then display
"[Non-ISO]" instead of the ISO letters.

The _Type_ field displays a two-digit number that is the actual type
number that the object transmits. That number is looked up in a file
called typecode.lst in the data directory, and the typename from
typecode.lst is displayed alongside the two digit code.

The _Navigational Status_ field displays whether an object is under
way, moored, at anchor and so on. This information is set manually by
the crew of the ship, so one cannot trust this information fully.

_Position Accuracy_ has two possible values: "Good / GPS" and "Very
Good / DPGS". The difference is that DGPS is accurate to within a few
meters, whereas GPS can be many meters off the real position.

There are two transponder types in the AIS system: class A and class
B. _Transponder Type_ tells which one the ship is using. Class A is
mainly for large, commercial ships, while class B transponders are
lower-powered transponders for use on small boats such as sailing
ships.

The _Remark_ field displays a remark if a remark is set on the current
object.

There are several alternative to the lat/long way of expressing map
coordinates. One that is supported in AIS Logger is the GEOREF system
where the globe is divided into large tiles using letters and numbers.

The _Course_ field is the direction the vessel is steering.

The _Heading_ field is the direction the vessel is going at a given
point.

The _Updates_ field is the number of messages received from this
object since it was created in the list (also see the _Created_ and
_Updated_ fields.)

Data can come from several sources in AIS Logger. The _Source_ field
displays from which source the latest data comes.


### Map Window

AIS Logger can plot objects (ships, base stations) on a vector map. By
selecting "View/Show map window" or pressing F5 the map will load and
display.

The map window consists of a map (shorelines drawn on a lat/long
grid), a toolbar, a box displaying information about the currently
selected object and a status bar displaying the coordinates of the
mouse pointer.

All objects that is plotted as round dots are mobile transponders,
while filled squares indicate base stations. A line connected to a
dot indicates heading and speed. A shorter line means a slower speed
compared to a longer line. The different colors on objects can be set
in the configuration.

There are four mouse pointer modes in the map window, each with its
own icon on the toolbar:

The first icon is _Pointer mode_. In this mode one selects objects by
clicking on them.

The second icon is _Zoom in mode_. One can zoom in in two ways: by
clicking on the desired cent re point, or by holding down the left
mouse button and drag the mouse to create a zoom box. Right-clicking
will make the map zoom out one level.

The third icon is _Zoom out mode_. Left-clicking in this mode makes
the map zoom out one level. Right-clicking makes the map zoom in one
level.

The fourth icon is _Pan mode_. In this mode one can pan across the map
by clicking and dragging around.

The button _Zoom To Fit_ makes the map zoom to a level where all
objects and shorelines can be shown at the same time.

When an object is selected, one can display a detail window by
pressing the button "Open selected in Detail Window" or by pressing
F2. Any selections made in the map window will also be mirrored by the
list views and vice versa.


### File Menu

The _File/Load raw data_ choice will read raw NMEA data from a file.
The data will be treated as any other incoming data. Data is
timestamped with current time as there are no time information in
single messages.


### Raw Data Window

The _Raw Data Window_ is a simple window displaying the latest 500
received messages. It is automatically updated at a given interval
with new data. One can also pause the data temporarily by pressing the
pause button. When depressing the pause button the window is updated
with the latest data.


### Statistics Window

The Statistics Window display a variety of statistics.

The _Objects_ box displays the current number of tracked objects,
number of greyed-out objects and the number of greyed-out objects with
a calculated distance.

The _Radio Horizon_ box makes calculations from the greyed-out objects
with a calculated distance. All the values refer to the greyed-out
objects only.  The numbers can not be treated as a real measurement,
but they do give some indication of the current radio propagation.

The _Uptime_ box displays the time since the program was started.

The _Inputs_ box contains stats from different input sources.
_Received_ is the number of raw messages that have been received from
a single source. _Parsed_ is the number of raw messages that have been
parsed (decoded) by the program. The _Parsed rate_ field displays a
simple measurement of how many messages that got parsed per second at
the last refresh of the window.


### Set alerts and remarks Window

The _Set alerts and remarks_ Window is the really powerful part of the
program. The list shown is a compilation of data from the current ID
database in memory, alerts set on MMSI numbers, and remarks. The list
is fully sortable and one can filter the information in the list by
checking the boxes or typing in the filter text field.

To edit an object, simply select it with mouse or keyboard. The
selected object will show up in the _Selected object_ box. To update
an object, type in the remark field and/or change the alert state, and
press the _Save object_ button. The changes applies instantly. To make
the changes permanent by saving them to a file, press the _Save
changes_ button. This will save the remarks and alerts to the
alert/remark file set in the settings. If no such file is set, the
program will notify the user.

For a more in-depth explanation of how to set and use alerts and
remarks, please see the chapter about alerts.


### Settings Window

The settings window contains several tabs with options and settings.
Each setting has an equivalent part in the configuration file (default
filename: default.ini)

When pressing the _Apply_ button the in-memory configuration is
updated, but most of the options will have no effect. One has to press
_Save_ and restart the program to use all of the new settings.

For more information about the settings and how to use them, please
see the chapter about configuration.


