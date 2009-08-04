AIS Logger
==========

* AIS Logger is a simple viewer and logger for data received by
  AIS-transponders or -receivers
* Capture raw data from a serial port or through a network
* Displays data in list views and maps
* Can log data to a SQLite database
* Platform independent, written in Python and WxPython
* Free software under the [MIT license][mitlicense]
* Homepage: [http://sourceforge.net/projects/aislogger/][homepage]
* Releases:
  [http://sourceforge.net/projects/aislogger/files/][releases]
* Git repository: [http://github.com/olcai/ais-logger/][repo]


Features
--------

* Can capture raw data from several sources at the same time
* Can act as a server for streaming raw data
* Decodes standard NMEA AIS sentences as well as SAAB TransponderTech
  sentences
* Logs data to a SQLite database
* Plots positions on vector maps
* Displays data in two fully sortable list views
* Alerts can be set to notify user of approaching ships
* Remarks can be added to ships


Status
------

The software is quite stable for daily use, but has some rough
edges. The GUI is not as friendly as it could be with regards to
helpful error messages and wizards. There are also a few GUI problems
when running on *nix systems, but it is usable.


Dependencies
------------

AIS Logger has a few, but large, dependencies that needs to be
installed in order to use it. All of these should be readily available
in package repositories on *nix systems. If you plan to use AIS Logger
under Windows, please use a release binary as they are mostly self
contained (see the install instructions below).

These are the run-time dependencies:

* [Python][python] 2.6 (not tested with Python 3)
* [Pysqlite][pysqlite] >= 2.5
* [Pyserial][pyserial] >= 2.3
* [WxPython][wxpython] >=2.8.8
* [Numpy][numpy]


Installing 
----------

* Installing from a binary release archive (Windows):

  Download and extract the archive to a location of your
  choosing. Create a suitable shortcut to aislogger.exe and enjoy.

  **NOTE:** You may have to install a few DLL files for AIS Logger to
  run. You may put them in the winnt\system directory or directly in
  the AIS Logger directory. Common missing files are gdiplus.dll (from
  [GDI+][gdi+]), msvcp90.dll and msvcr90.dll (both from [Visual
  C++][visualc++]).

* Installing from a release tarball (*nix):

  Download and extract the archive to a temporary location and then
  do:
    
        $ python setup.py install   # As root
        $ aislogger                 # As normal user to start program

* Installing from git (*nix):

  To compile the documentation you will need markdown in your
  path. Then clone from [Github][repo], and do:

        $ make all                  # Generates documentation
        $ python setup.py install   # As root
        $ aislogger                 # As normal user to start program


Uninstalling
------------

* A binary release
  
  Simply delete the directory containing AIS Logger.

* A source release installed with setup.py
  
  Find the site-packages directory under your python installation
  directory (typically /usr/lib/pythonX.X/site-packages/ on*nix).
  Delete the aislogger directory and the file
  aislogger-XXXX-pyX.X.egg-info. You also have to delete the script
  aislogger (typically in /usr/bin under *nix). Done.


Configuring
-----------

When running on Windows and saving the configuration file, you can
safely save the configuration file to the program directory.

Under *nix, you cannot save the configuration file directly to the
suggested directory because you don't have permission to write to the
AIS Logger directory. Please save the configuration file in your home
directory and start the program with the -c switch and the config
file:

        $ aislogger -c myconfigfile.ini


Building on Windows
-------------------

To build AIS Logger on Windows, first install all dependencies given
above. You will also need to install [py2exe][py2exe] to build the
distribution (any modern version should do).

Extract the source archive to a directory. Then run the following
command:

        > python setup.py py2exe

You may need to use the full path to your python installation if it's
not in your $PATH. The result of the build is now in the directory
"dist" and is ready to run and distribute.


Known issues
------------

* Color depth needs to be 24 bits.
* The GUI looks bad (wrong positioning of widgets) on *nix systems.


Questions, comments or code
---------------------------

* See the [doc/][docs] directory for current documentation.
* Got questions or bug reports? [Contact me][email].
* Contribute by forking on Github or send patches by [email][email].


Background information on AIS
-----------------------------

Automatic Identification System is a system used to identify and
locate maritime vessels. Transponders automatically broadcast
information via a VHF transceiver, so called “messages”, containing
data such as the vessels current position, heading, speed, name and
radio callsign. To receive these messages you will need either a
full-fledged transponder or a special receiver that communicate with a
computer through a serial interface. In theory, you could use a
standard VHF-scanner and a sound card to intercept AIS messages, but
this is currently not supported in AIS Logger. For this you could try
[GNU AIS][gnuais] instead.


External code in AIS Logger
---------------------------

The following code is used by, and distributed with, AIS Logger but is
externally developed:

* [Geopy](http://www.geopy.org/)
* [ConfigObj](http://www.voidspace.org.uk/python/configobj.html)
* [PyDbLite](http://quentel.pierre.free.fr/PyDbLite/index.html)
* [The icon](http://commons.wikimedia.org/wiki/File:Gfi-set01-lost-ship.png)


[mitlicense]: http://opensource.org/licenses/mit-license.php
[homepage]:   http://sourceforge.net/projects/aislogger/
[releases]:   http://sourceforge.net/projects/aislogger/files/
[repo]:       http://github.com/olcai/ais-logger/
[docs]:       http://github.com/olcai/ais-logger/tree/master/doc/
[email]:      mailto:olcai@users.sourceforge.net
[gdi+]:       http://www.microsoft.com/downloads/details.aspx?familyid=6A63AB9C-DF12-4D41-933C-BE590FEAA05A
[visualc++]:  http://www.microsoft.com/downloads/details.aspx?FamilyID=9b2da534-3e03-4391-8a4d-074b9f2bc1bf
[gnuais]:     http://gnuais.sourceforge.net/
[python]:     http://www.python.org/
[pysqlite]:   http://www.pysqlite.org/
[pyserial]:   http://pyserial.sourceforge.net/
[wxpython]:   http://www.wxpython.org/
[numpy]:      http://numpy.scipy.org/
[py2exe]:     http://www.py2exe.org/
