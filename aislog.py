#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# aislog.py (part of "AIS Logger")
# Simple AIS logging and display software
#
# Copyright (c) 2006-2008 Erik I.J. Olsson <olcai@users.sourceforge.net>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

version = ''

import sys, os, optparse, logging
import time, datetime
import threading, Queue, collections
import socket, SocketServer
import pickle, codecs
import md5
import decimal

from pysqlite2 import dbapi2 as sqlite
import pydblite
import wx
import wx.lib.mixins.listctrl as listmix
import gettext
from configobj import ConfigObj

import decode
from util import *
if os.name == 'nt': import serialwin32 as serial
elif os.name == 'posix': import serialposix as serial

### Fetch command line arguments
# Define standard config file
configfile = 'config.ini'

# Create optparse object
cmdlineparser = optparse.OptionParser()
# Add an option for supplying a different config file than the default one
cmdlineparser.add_option("-c", "--config", dest="configfile", help="Specify a config file other than the default")
# Parse the arguments
(cmdlineoptions, cmdlineargs) = cmdlineparser.parse_args()
if cmdlineoptions.configfile:
    # Try to open the supplied config file
    try:
        testopen = open(cmdlineoptions.configfile, 'r')
        testopen.close()
        configfile = cmdlineoptions.configfile
    except (IOError, IndexError):
        # Could not read the file, aborting program
        sys.exit("Unable to open config file. Aborting.")

### Gettext call
gettext.install('aislogger', ".", unicode=False)
#self.presLan_en = gettext.translation("aislogger", "./locale", languages=['en'])
#self.presLan_en.install()
#self.locale = wx.Locale(wx.LANGUAGE_ENGLISH)
#locale.setlocale(locale.LC_ALL, 'EN')

### Load or create configuration
# Create a dictionary containing all available columns (for display) as 'dbcolumn': ['description', size-in-pixels]
columnsetup = {'mmsi': [_("MMSI"), 80], 'mid': [_("Nation"), 55], 'imo': [_("IMO"), 80], 'name': [_("Name"), 150], 'type': [_("Type nbr"), 45], 'typename': [_("Type"), 50], 'callsign': [_("CS"), 60], 'latitude': [_("Latitude"), 105], 'longitude': [_("Longitude"), 110], 'georef': [_("GEOREF"), 85], 'creationtime': [_("Created"), 75], 'time': [_("Updated"), 75], 'sog': [_("Speed"), 60], 'cog': [_("Course"), 60], 'heading': [_("Heading"), 70], 'destination': [_("Destination"), 150], 'eta': [_("ETA"), 80], 'length': [_("Length"), 45], 'width': [_("Width"), 45], 'draught': [_("Draught"), 90], 'rateofturn': [_("ROT"), 60], 'navstatus': [_("NavStatus"), 150], 'posacc': [_("PosAcc"), 55], 'bearing': [_("Bearing"), 65], 'distance': [_("Distance"), 70], 'remark': [_("Remark"), 150]}
# Set default keys and values
defaultconfig = {'common': {'refreshlisttimer': 10000, 'listmakegreytime': 600, 'deleteitemtime': 3600, 'listcolumns': 'mmsi, mid, name, typename, callsign, georef, creationtime, time, sog, cog, destination, navstatus, bearing, distance, remark', 'alertlistcolumns': 'mmsi, mid, name, typename, callsign, georef, creationtime, time, sog, cog, destination, navstatus, bearing, distance, remark'},
                 'logging': {'logging_on': False, 'logtime': '600', 'logfile': ''},
                 'iddb_logging': {'logging_on': False, 'logtime': '600', 'logfile': 'testiddb.db'},
                 'alert': {'alertfile_on': False, 'alertfile': '', 'remarkfile_on': False, 'remarkfile': '', 'alertsound_on': False, 'alertsoundfile': ''},
                 'position': {'override_on': False, 'latitude': '0', 'longitude': '0', 'position_format': 'dms'},
                 'serial_a': {'serial_on': False, 'port': '0', 'baudrate': '9600', 'rtscts': False, 'xonxoff': False, 'repr_mode': False},
                 'serial_b': {'serial_on': False, 'port': '1', 'baudrate': '9600', 'rtscts': False, 'xonxoff': False, 'repr_mode': False},
                 'serial_c': {'serial_on': False, 'port': '2', 'baudrate': '9600', 'rtscts': False, 'xonxoff': False, 'repr_mode': False},
                 'network': {'server_on': False, 'server_address': 'localhost', 'server_port': '23000', 'client_on': False, 'client_addresses': ['localhost:23000']}}
# Create a ConfigObj based on dict defaultconfig
config = ConfigObj(defaultconfig, indent_type='')
# Read or create the config file object
userconfig = ConfigObj(configfile)
# Merge the settings in the config file with the defaults
config.merge(userconfig)
# Set the intial comment for the config file
config.initial_comment = ['Autogenerated config file for AIS Logger', "You may edit if you're careful"]
# Set comments for each section and key
config.comments['common'] = ['', 'Common settings for the GUI']
config.comments['logging'] = ['', 'Settings for logging to file']
config.comments['iddb_logging'] = ['', 'Settings for logging the identification database to file']
config.comments['alert'] = ['', 'Settings for alerts and remarks']
config.comments['position'] = ['', 'Set manual position (overrides decoded own position)']
config.comments['serial_a'] = ['', 'Settings for input from serial device A']
config.comments['serial_b'] = ['', 'Settings for input from serial device B']
config.comments['serial_c'] = ['', 'Settings for input from serial device C']
config.comments['network'] = ['', 'Settings for sending/receiving data through a network connection']
config['common'].comments['refreshlisttimer'] = ['Number of ms between refreshing the lists']
config['common'].comments['listmakegreytime'] = ['Number of s between last update and greying out an item']
config['common'].comments['deleteitemtime'] = ['Number of s between last update and removing an item from memory']
config['common'].comments['listcolumns'] = ['Define visible columns in list view using db column names']
config['common'].comments['alertlistcolumns'] = ['Define visible columns in alert list view using db column names']
config['logging'].comments['logging_on'] = ['Enable file logging']
config['logging'].comments['logtime'] = ['Number of s between writes to log file']
config['logging'].comments['logfile'] = ['Filename of log file']
config['iddb_logging'].comments['logging_on'] = ['Enable IDDB file logging']
config['iddb_logging'].comments['logtime'] = ['Number of s between writes to log file']
config['iddb_logging'].comments['logfile'] = ['Filename of log file']
config['alert'].comments['alertfile_on'] = ['Enable loading of alert file at program start']
config['alert'].comments['alertfile'] = ['Filename of alert file']
config['alert'].comments['remarkfile_on'] = ['Enable loading of remark file at program start']
config['alert'].comments['remarkfile'] = ['Filename of remark file']
config['alert'].comments['alertsound_on'] = ['Enable audio alert']
config['alert'].comments['alertsoundfile'] = ['Filename of wave sound file for audio alert']
config['position'].comments['override_on'] = ['Enable manual position override']
config['position'].comments['position_format'] = ['Define the position presentation format in DD, DM or DMS']
config['position'].comments['latitude'] = ['Latitude in decimal degrees (DD)']
config['position'].comments['longitude'] = ['Longitude in decimal degrees (DD)']
config['network'].comments['server_on'] = ['Enable network server']
config['network'].comments['server_address'] = ['Server hostname or IP (server side)']
config['network'].comments['server_port'] = ['Server port (server side)']
config['network'].comments['client_on'] = ['Enable network client']
config['network'].comments['client_addresses'] =['List of server:port to connect and use data from']

# Log exceptions to file
#except_file = open('except.log', 'a')
#logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(levelname)s %(message)s',filename='except.log',filemode='a')
#sys.stderr = except_file
#sys.stderr = sys.stdout()

# Define global variables
mid = {}
midfull = {}
typecode = {}
data = {}
owndata = {}
alertlist = []
alertstring = ''
alertstringsound = ''
remarkdict = {}
# Define collections
rawdata = collections.deque()
networkdata = collections.deque()
# Set start time to start_time
start_time = datetime.datetime.now()


class MainWindow(wx.Frame):
    # Intialize two sets, active_set for the MMSI numers who are active,
    # grey_set for grey-outed MMSI numbers
    active_set = set()
    grey_set = set()

    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, size=(800,500))

        # Create status row
        statusbar = wx.StatusBar(self, -1)
        statusbar.SetFieldsCount(2)
        self.SetStatusBar(statusbar)
        self.SetStatusWidths([-2, -1])
        self.SetStatusText(_("Own position:"),0)
        self.SetStatusText(_("Total nr of objects / old: "),1)

        # Create menu
        menubar = wx.MenuBar()
        file = wx.Menu()

        load_raw = wx.MenuItem(file, 103, _("Load &raw data...\tCtrl+R"), _("Loads a file containing raw (unparsed) messages"))
        file.AppendItem(load_raw)
        file.AppendSeparator()

        quit = wx.MenuItem(file, 104, _("E&xit\tCtrl+X"), _("Exit program"))
        file.AppendItem(quit)

        view = wx.Menu()
        showsplit = wx.MenuItem(view, 201, _("Show &alert view\tF8"), _("Shows or hides the alert view"))
        view.AppendItem(showsplit)
        view.AppendSeparator()

        showrawdata = wx.MenuItem(view, 203, _("Show raw &data window..."), _("Shows a window containing the incoming raw (unparsed) data"))
        view.AppendItem(showrawdata)

        calchorizon = wx.MenuItem(view, 204, _("Show s&tatistics..."), _("Shows a window containing various statistics"))
        view.AppendItem(calchorizon)

        tools = wx.Menu()
        setalerts = wx.MenuItem(tools, 301, _("Set &alerts and remarks...\tCtrl+A"), _("Shows a window where one can set alerts and remarks"))
        tools.AppendItem(setalerts)

        settings = wx.MenuItem(tools, 302, _("&Settings...\tCtrl+S"), ("Opens the settings window"))
        tools.AppendItem(settings)

        help = wx.Menu()
        about = wx.MenuItem(help, 401, _("&About...\tF1"), _("About the software"))
        help.AppendItem(about)

        menubar.Append(file, _("&File"))
        menubar.Append(view, _("&View"))
        menubar.Append(tools, _("&Tools"))
        menubar.Append(help, _("&Help"))

        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.OnLoadRawFile, id=103)
        self.Bind(wx.EVT_MENU, self.Quit, id=104)
        self.Bind(wx.EVT_MENU, self.OnShowSplit, id=201)
        self.Bind(wx.EVT_MENU, self.OnShowRawdata, id=203)
        self.Bind(wx.EVT_MENU, self.OnStatistics, id=204)
        self.Bind(wx.EVT_MENU, self.OnSetAlerts, id=301)
        self.Bind(wx.EVT_MENU, self.OnSettings, id=302)
        self.Bind(wx.EVT_MENU, self.OnAbout, id=401)

        # Read type codes and MID codes from file
        self.readmid()
        self.readtype()
        # Try to read an alert file and a remark file
        self.readalertfile()
        self.readremarkfile()

        # Create and split two windows, a list window and an alert window
        self.split = wx.SplitterWindow(self, -1, style=wx.SP_3D)
        self.splist = ListWindow(self.split, -1)
        self.spalert = AlertWindow(self.split, -1)
        self.split.SetSashGravity(0.5)
        self.splitwindows()

        # Start a timer to get new messages at a fixed interval
        self.timer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.GetMessages, self.timer)
        self.timer.Start(2000)

    def GetMessages(self, event):
        # Get messages from main thread
        messages = MainThread().ReturnOutgoing()
        # See what to do with them
        for message in messages:
            if 'update' in message:
                # "Move" from grey_set to active_set
                self.grey_set.discard(message['update']['mmsi'])
                self.active_set.add(message['update']['mmsi'])
                # Update lists
                self.splist.Update(message)
                self.spalert.Update(message)
            elif 'insert' in message:
                # Insert to active_set
                self.active_set.add(message['insert']['mmsi'])
                # Refresh status row
                self.OnRefreshStatus()
                # Update lists
                self.splist.Update(message)
                self.spalert.Update(message)
            elif 'old' in message:
                # "Move" from active_set to grey_set
                self.active_set.discard(message['old'])
                self.grey_set.add(message['old'])
                # Refresh status row
                self.OnRefreshStatus()
                # Update lists
                self.splist.Update(message)
                self.spalert.Update(message)
            elif 'remove' in message:
                # Remove from grey set (and active_set to be sure)
                self.active_set.discard(message['remove'])
                self.grey_set.discard(message['remove'])
                # Refresh status row
                self.OnRefreshStatus()
                # Update lists
                self.splist.Update(message)
                self.spalert.Update(message)
            elif 'own_position' in message:
                # Refresh status row with own_position
                self.OnRefreshStatus(message['own_position'])
        # Refresh the listctrls (by sorting)
        self.splist.Refresh()
        self.spalert.Refresh()

    def splitwindows(self, window=None):
        if self.split.IsSplit(): self.split.Unsplit(window)
        else: self.split.SplitHorizontally(self.splist, self.spalert, 0)

    def readmid(self):
        # Read a list from MID to nation from file mid.lst
        f = open('mid.lst', 'r')
        for line in f:
            # For each line, strip any whitespace and then split the data using ','
            row = line.strip().split(',')
            # Try to map MID to 2-character ISO
            try: mid[row[0]] = row[1]
            except: continue
            # Try to map MID to full country name
            try: midfull[row[0]] = row[2]
            except: continue
        f.close()

    def readtype(self):
        # Read a list with ship type codes from typecode.lst
        f = open('typecode.lst', 'r')
        for line in f:
            # For each line, strip any whitespace and then split the data using ','
            row = line.strip().split(',')
            typecode[row[0]] = row[1]
        f.close()

    def readalertfile(self):
        # This function will try to read an alert file, if defined in config
        path = config['alert']['alertfile']
        if config['alert'].as_bool('alertfile_on') and len(path) > 0:
            try:
                self.queryitems = []
                file = open(path, 'rb')
                data = pickle.load(file)
                if data[0] == 'Alertdata':
                    del data[0]
                    self.queryitems.extend(data[:])
                file.close()
                # Copy list to alertlist
                global alertlist
                alertlist = self.queryitems[:]
                # Create a joined string from the list
                global alertstring
                if len(alertlist) > 0:
                    alertstring = '(' + ') OR ('.join(zip(*alertlist)[0]) + ')'
                else: alertstring = '()'
                # Create a joined string from the sound alert list
                querysoundlist = []
                global alertstringsound
                # Loop over alertlist and append those with sound alert to alertsoundlist
                for i in alertlist:
                    if i[1] == 1:
                       querysoundlist.append(i)
                # If querysoundlist is not empty, make a query string of it
                if len(querysoundlist) > 0:
                    alertstringsound = '(' + ') OR ('.join(zip(*querysoundlist)[0]) + ')'
                else: alertstringsound = '()'
            except:
                dlg = wx.MessageDialog(self, _("Error, could not load the alertfile!") + "\n\n" + str(sys.exc_info()[0]), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()

    def readremarkfile(self):
        # This function will try to read an alert file, if defined in config
        path = config['alert']['remarkfile']
        if config['alert'].as_bool('remarkfile_on') and len(path) > 0:
            try:
                data = {}
                f = open(path, 'r')
                for line in f:
                    # For each line, strip any whitespace and then split the data using ','
                    row = line.strip().split(',')
                    # Try to read line as ASCII/UTF-8, if error, try cp1252 (workaround for Windows)
                    try:
                        data[int(row[0])] = unicode(row[1])
                    except:
                        data[int(row[0])] = unicode(row[1], 'cp1252')
                f.close()
                global remarkdict
                remarkdict = data.copy()
            except:
                dlg = wx.MessageDialog(self, _("Error, could not load the remark file!") + "\n\n" + str(sys.exc_info()[0]), style=wx.OK|wx.wx.ICON_ERROR)
                dlg.ShowModal()

    def OnRefreshStatus(self, own_pos=False):
        # Update the status row

        # Get total number of items by taking the length of the union
        # between active_set and grey_set
        nbritems = len(self.active_set.union(self.grey_set))
        nbrgreyitems = len(self.grey_set)
        # See if we should update the position row
        if own_pos:
            # Get human-readable position
            pos = PositionConversion(own_pos['ownlatitude'],own_pos['ownlongitude']).default
            # Print own position
            self.SetStatusText(_("Own position: ") + pos[0] + '  ' + pos[1] + '  (' + own_pos['owngeoref'] + ')', 0)
        # Print number of objects-string
        self.SetStatusText(_("Total nbr of objects / old: ") + str(nbritems) + ' / ' + str(nbrgreyitems), 1)

    def OnShowRawdata(self, event):
        dlg = RawDataWindow(None, -1)
        dlg.Show()

    def OnStatistics(self, event):
        dlg = StatsWindow(None, -1)
        dlg.Show()

    def OnLoadRawFile(self, event):
        path = ''
        wcd = _('All files (*)|*|Text files (*.txt)|*.txt')
        dir = os.getcwd()
        open_dlg = wx.FileDialog(self, message=_("Choose a raw data file"), defaultDir=dir, defaultFile='', wildcard=wcd, style=wx.OPEN)
        if open_dlg.ShowModal() == wx.ID_OK:
            path = open_dlg.GetPath()
        if len(path) > 0:
            try:
                self.rawfileloader(path)
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Could not open file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except UnicodeDecodeError, error:
                dlg = wx.MessageDialog(self, _("Could not open file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                open_dlg.Destroy()

    def rawfileloader(self, filename):
        # Load raw data from file and queue it to the CommHubThread

        # Open file
        f=open(filename, 'r')

        # Get total number of lines in file
        num_lines = 0
        for line in f:
            num_lines += 1
        f.seek(0)

        # Create a progress dialog
        progress = wx.ProgressDialog(_("Loading file..."), _("Loading file..."), num_lines)

        # Step through each row in the file
        commt = CommHubThread()
        name = 'File'
        lastupdate_line = 0
        for linenumber, line in enumerate(f):

            # If indata contains raw data, pass it along
            if line[0] == '!' or line[0] == '$':
                # Put it in CommHubThread's queue
                commt.put([name,line])

            # Update the progress dialog for each 100 rows
            if lastupdate_line + 100 < linenumber:
                progress.Update(linenumber)
                lastupdate_line = linenumber

        # Close file
        f.close()
        progress.Destroy()

    def Quit(self, event):
        self.Destroy()

    def OnShowSplit(self, event):
        self.splitwindows(self.spalert)

    def OnAbout(self, event):
        aboutstring = 'AIS Logger ('+version+')\n(C) Erik I.J. Olsson 2006-2008\n\naislog.py\ndecode.py\nutil.py'
        dlg = wx.MessageDialog(self, aboutstring, _("About"), wx.OK|wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def OnSetAlerts(self, event):
        dlg = SetAlertsWindow(None, -1)
        dlg.Show()

    def OnSettings(self, event):
        dlg = SettingsWindow(None, -1)
        dlg.Show()


class PositionConversion(object):
    # Makes position conversions from position in a DD format
    # to human-readable strings in DD, DM or DMS format
    # Input must be of type decimal.Decimal
    def __init__(self, lat, long):
        self.latitude = lat
        self.longitude = long

    @property
    def default(self):
        # Extract the format we should use from configuration, and
        # return the right function
        format = config['position']['position_format'].lower()
        if format == 'dms':
            return self.dms
        elif format == 'dm':
            return self.dm
        elif format == 'dd':
            return self.dd

    @property
    def dd(self):
        # Return a human-readable DD position
        if self.latitude > 0:
            lat = str(abs(self.latitude)) + u'°N'
        elif self.latitude < 0:
            lat = str(abs(self.latitude)) + u'°S'
        if self.longitude > 0:
            long = str(abs(self.longitude)) + u'°E'
        elif self.longitude < 0:
            long = str(abs(self.longitude)) + u'°W'
        return lat, long

    @property
    def dm(self):
        # Return a human-readable DM position
        latdegree = int(self.latitude)
        longdegree = int(self.longitude)
        latmin = ((self.latitude - latdegree) * 60).quantize(decimal.Decimal('0.0001')).normalize()
        longmin = ((self.longitude - longdegree) * 60).quantize(decimal.Decimal('0.0001')).normalize()
        if self.latitude > 0:
            lat = str(abs(latdegree)).zfill(2) + u'°'+ str(abs(latmin)) + "'N"
        elif self.latitude < 0:
            lat = str(abs(latdegree)).zfill(2) + u'°'+ str(abs(latmin)) + "'S"
        if self.longitude > 0:
            long = str(abs(longdegree)).zfill(3) + u'°'+ str(abs(longmin)) + "'E"
        elif self.longitude < 0:
            long = str(abs(longdegree)).zfill(3) + u'°' + str(abs(longmin)) + "'W"
        return lat, long

    @property
    def dms(self):
        # Return a human-readable DMS position
        latdegree = int(self.latitude)
        longdegree = int(self.longitude)
        latmin = (self.latitude - latdegree) * 60
        longmin = (self.longitude - longdegree) * 60
        latsec = ((latmin - int(latmin)) * 60).quantize(decimal.Decimal('0.01')).normalize()
        longsec = ((longmin - int(longmin)) * 60).quantize(decimal.Decimal('0.01')).normalize()
        if self.latitude > 0:
            lat = str(abs(latdegree)).zfill(2) + u'°'+ str(int(abs(latmin))).zfill(2) + "'" + str(abs(latsec)) + "''N"
        elif self.latitude < 0:
            lat = str(abs(latdegree)).zfill(2) + u'°'+ str(int(abs(latmin))).zfill(2) + "'" + str(abs(latsec)) + "''S"
        if self.longitude > 0:
            long = str(abs(longdegree)).zfill(3) + u'°'+ str(int(abs(longmin))).zfill(2) + "'" + str(abs(longsec)) + "''E"
        elif self.longitude < 0:
            long = str(abs(longdegree)).zfill(3) + u'°' + str(int(abs(longmin))).zfill(2) + "'" + str(abs(longsec)) + "''W"
        return lat, long


class ListWindow(wx.Panel):
    def __init__(self, parent, id):
        wx.Panel.__init__(self, parent, id)

        # Read config and extract columns
        # Create a list from the comma-separated string in config (removing all whitespace)
        alertlistcolumns_as_list = config['common']['listcolumns'].replace(' ', '').split(',')
        # A really complicated list comprehension... ;-)
        # For each item in the alertlistcolumns_as_list, extract the corresponding items from columnsetup and create a list
        used_columns = [ [x, columnsetup[x][0], columnsetup[x][1]] for x in alertlistcolumns_as_list ]

        # Create the listctrl
        self.list = VirtualList(self, columns=used_columns)

        # Create a small panel on top
        panel2 = wx.Panel(self, -1, size=(1,1))

        # Set the layout
        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(panel2, 0, wx.EXPAND)
        box.Add(self.list, 1, wx.EXPAND)
        box.InsertSpacer(2, (0,5)) # Add some space between the list and the handle
        self.SetSizer(box)
        self.Layout()

    def Update(self, message):
        # Update the underlying listctrl data with message
        self.list.OnUpdate(message)

    def Refresh(self):
        # Refresh the listctrl by sorting
        self.list.SortListItems()


class AlertWindow(wx.Panel):
    def __init__(self, parent, id):
        wx.Panel.__init__(self, parent, id)

        # Read config and extract columns
        # Create a list from the comma-separated string in config (removing all whitespace)
        alertlistcolumns_as_list = config['common']['alertlistcolumns'].replace(' ', '').split(',')
        # A really complicated list comprehension... ;-)
        # For each item in the alertlistcolumns_as_list, extract the corresponding items from columnsetup and create a list
        used_columns = [ [x, columnsetup[x][0], columnsetup[x][1]] for x in alertlistcolumns_as_list ]

        # Create the listctrl
        self.list = VirtualList(self, columns=used_columns)

        # Create a small panel on top
        panel2 = wx.Panel(self, -1, size=(4,4))

        # Set the layout
        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(panel2, 0, wx.EXPAND)
        box.Add(self.list, 1, wx.EXPAND)
        self.SetSizer(box)
        self.Layout()

    def Update(self, message):
        # See if we should update
        if 'alert' in message and message['alert']:
            # Update the underlying listctrl data with message
            self.list.OnUpdate(message)
        # Sound an alert for selected objects
        if 'soundalert' in message and message['soundalert']:
            self.soundalert()

    def Refresh(self):
        # Refresh the listctrl by sorting
        self.list.SortListItems()

    def soundalert(self):
        # Play sound if config is set
        sound = wx.Sound()
        if config['alert'].as_bool('alertsound_on') and len(config['alert']['alertsoundfile']) > 0 and sound.Create(config['alert']['alertsoundfile']):
            sound.Play(wx.SOUND_ASYNC)


class VirtualList(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin, listmix.ColumnSorterMixin):
    def __init__(self, parent, columns):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT|wx.LC_VIRTUAL|wx.LC_SINGLE_SEL)

        # Define and retreive two arrows, one upwards, the other downwards
        self.imagelist = wx.ImageList(16, 16)
        self.sm_up = self.imagelist.Add(getSmallUpArrowBitmap())
        self.sm_dn = self.imagelist.Add(getSmallDnArrowBitmap())
        self.SetImageList(self.imagelist, wx.IMAGE_LIST_SMALL)

        # Iterate over the given columns and create the specified ones
        self.columnlist = []
        for i, k in enumerate(columns):
            self.InsertColumn(i, k[1]) # Insert the column
            self.SetColumnWidth(i, k[2]) # Set the width
            self.columnlist.append(k[0]) # Append each column name to a list

        # Use the mixins
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        listmix.ColumnSorterMixin.__init__(self, len(self.columnlist))

        # Set object-wide data holders
        self.itemDataMap = {}
        self.itemIndexMap = []
        self.selected = -1
        # Do initial sorting on column 0, ascending order (1)
        self.SortListItems(0, 1)
        # Define one set for alert items and one for grey items
        self.alertitems = set()
        self.greyitems = set()

        # Define events
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected)

    def OnItemActivated(self, event):
        # Get the MMSI number associated with the row activated
        itemmmsi = self.itemIndexMap[event.m_itemIndex]
        # Open the detail window
        dlg = DetailWindow(None, -1, itemmmsi)
        dlg.Show()

    def OnItemSelected(self, event):
        # When an object is selected, extract the MMSI number and
        # put it in self.selected
        self.selected = self.itemIndexMap[event.m_itemIndex]

    def OnItemDeselected(self, event):
        self.selected = -1

    def OnUpdate(self, message):
        # See what message we should work with
        if 'update' in message:
            data = message['update']
            # Remove object from grey item set
            self.greyitems.discard(data['mmsi'])
            # If alert, put it in alert item set
            if 'alert' in message and message['alert']:
                self.alertitems.add(data['mmsi'])
            # Get the data formatted
            self.itemDataMap[data['mmsi']] = self.FormatData(data)
        elif 'insert' in message:
            # Set a new item count in the listctrl
            self.SetItemCount(self.GetItemCount()+1)
            data = message['insert']
            # If alert, put it in alert item set
            if 'alert' in message and message['alert']:
                self.alertitems.add(data['mmsi'])
            # Get the data formatted
            self.itemDataMap[data['mmsi']] = self.FormatData(data)
        elif 'remove' in message:
            # Get the MMSI number
            mmsi = message['remove']
            # Set a new item count in the listctrl
            self.SetItemCount(self.GetItemCount()-1)
            # Remove object from sets
            self.greyitems.discard(mmsi)
            self.alertitems.discard(mmsi)
            # Remove object from list dict
            del self.itemDataMap[message[mmsi]]
        elif 'old' in message:
            # Simply add object to set
            self.greyitems.add(message['old'])

        # Extract the MMSI numbers as keys for the data
        self.itemIndexMap = self.itemDataMap.keys()

    def FormatData(self, data):
        # Create a temporary dict to hold data in the order of
        # self.columnlist so that the virtual listctrl can use it
        new = []
        latpos = None
        longpos = None
        # Loop over the columns we will show
        for i, col in enumerate(self.columnlist):
            # Append the list
            new.append(None)
            # If we have the data, fine!
            if col in data:
                # Set new[position] to the info in data
                # If Nonetype, set an empty string (for sorting reasons)
                if not data[col] == None:
                    new[i] = data[col]
                else:
                    new[i] = u''
                # Some special formatting cases
                if col == 'creationtime':
                    try: new[i] = data[col].isoformat()[11:19]
                    except: new[i] = ''
                if col == 'time':
                    try: new[i] = data[col].isoformat()[11:19]
                    except: new[i] = ''
                if col == 'latitude':
                    latpos = i
                if col == 'longitude':
                    longpos = i
                if col == 'posacc':
                    if data[col] == 0: new[i] = u'Bad'
                    elif data[col] == 1: new[i] = u'DGPS'
                    else: new[i] = ''
        # Get position in a more human-readable format
        if data.get('latitude',False) and data.get('longitude',False):
            pos = PositionConversion(data['latitude'],data['longitude']).default
            if latpos:
                new[latpos] = pos[0]
            if longpos:
                new[longpos] = pos[1]
        return new

    def OnGetItemText(self, item, col):
        # Return the text in item, col
        mmsi = self.itemIndexMap[item]
        string = self.itemDataMap[mmsi][col]
        # If string is a Nonetype, replace with an empty string
        if string == None:
            string = u''
        return string

    def OnGetItemAttr(self, item):
        # Return an attribute
        # Get the mmsi of the item
        mmsi = self.itemIndexMap[item]
        # Create the attribute
        self.attr = wx.ListItemAttr()

        # If item is in alertitems: make background red
        if mmsi in self.alertitems:
            self.attr.SetBackgroundColour("TAN")

        # If item is old enough, make the text grey
        if mmsi in self.greyitems:
            self.attr.SetTextColour("LIGHT GREY")
        return self.attr

    def SortItems(self,sorter=cmp):
        # Do the sort
        items = list(self.itemDataMap.keys())
        items.sort(sorter)
        self.itemIndexMap = items

        # See if the previous selected row exists after the sort
        # If the MMSI number is found, set the new position as
        # selected and ensure that it is visible
        # If not found, deselect all objects
        try:
            if self.selected in self.itemDataMap:
                new_position = self.FindItem(-1, unicode(self.selected))
                self.SetItemState(new_position, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
                self.EnsureVisible(new_position)
            else:
                for i in range(self.GetItemCount()):
                    self.SetItemState(i, 0, wx.LIST_STATE_SELECTED)
                self.selected = -1
        except: pass


    # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
    def GetListCtrl(self):
        return self

    # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
    def GetSortImages(self):
        return (self.sm_dn, self.sm_up)


class DetailWindow(wx.Dialog):
    def __init__(self, parent, id, itemmmsi):
        # Define the dialog
        wx.Dialog.__init__(self, parent, id, title=_("Detail window"))
        # Create panels
        shipdata_panel = wx.Panel(self, -1)
        voyagedata_panel = wx.Panel(self, -1)
        transponderdata_panel = wx.Panel(self, -1)
        objinfo_panel = wx.Panel(self, -1)
        remark_panel = wx.Panel(self, -1)
        # Create static boxes
        wx.StaticBox(shipdata_panel,-1,_(" Ship data "),pos=(3,5),size=(400,205))
        wx.StaticBox(voyagedata_panel,-1,_(" Voyage data "),pos=(3,5),size=(290,205))
        wx.StaticBox(transponderdata_panel,-1,_(" Received transponder data "),pos=(3,5),size=(400,105))
        wx.StaticBox(objinfo_panel,-1,_(" Object information "),pos=(3,5),size=(290,145))
        wx.StaticBox(remark_panel,-1,_(" Remark "), pos=(3,5),size=(400,60))
        # Ship data
        wx.StaticText(shipdata_panel,-1,_("MMSI nbr: "),pos=(12,25),size=(150,16))
        wx.StaticText(shipdata_panel,-1,_("IMO nbr: "),pos=(12,45),size=(150,16))
        wx.StaticText(shipdata_panel,-1,_("Nation: "),pos=(12,65),size=(150,16))
        wx.StaticText(shipdata_panel,-1,_("Name: "),pos=(12,85),size=(150,16))
        wx.StaticText(shipdata_panel,-1,_("Type: "),pos=(12,105),size=(150,16))
        wx.StaticText(shipdata_panel,-1,_("Callsign: "),pos=(12,125),size=(150,16))
        wx.StaticText(shipdata_panel,-1,_("Length: "),pos=(12,145),size=(150,16))
        wx.StaticText(shipdata_panel,-1,_("Width: "),pos=(12,165),size=(150,16))
        wx.StaticText(shipdata_panel,-1,_("Draught: "),pos=(12,185),size=(150,16))
        # Voyage data
        wx.StaticText(voyagedata_panel,-1,_("Destination: "),pos=(12,25),size=(150,16))
        wx.StaticText(voyagedata_panel,-1,_("ETA: "),pos=(12,45),size=(150,16))
        wx.StaticText(voyagedata_panel,-1,_("Latitude: "),pos=(12,65),size=(150,16))
        wx.StaticText(voyagedata_panel,-1,_("Longitude: "),pos=(12,85),size=(150,16))
        wx.StaticText(voyagedata_panel,-1,_("GEOREF: "),pos=(12,105),size=(150,16))
        wx.StaticText(voyagedata_panel,-1,_("Speed: "),pos=(12,125),size=(150,16))
        wx.StaticText(voyagedata_panel,-1,_("Course: "),pos=(12,145),size=(150,16))
        wx.StaticText(voyagedata_panel,-1,_("Heading: "),pos=(12,165),size=(150,16))
        wx.StaticText(voyagedata_panel,-1,_("Rate of turn: "),pos=(12,185),size=(150,16))
        # Transponder data
        wx.StaticText(transponderdata_panel,-1,_("Nav Status: "),pos=(12,65),size=(150,16))
        wx.StaticText(transponderdata_panel,-1,_("Accuracy: "),pos=(12,85),size=(150,16))
        # Object information such as bearing and distance
        wx.StaticText(objinfo_panel,-1,_("Bearing: "),pos=(12,25),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Distance: "),pos=(12,45),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Updates: "),pos=(12,65),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Source: "),pos=(12,85),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Created: "),pos=(12,105),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Updated: "),pos=(12,125),size=(150,16))

        # Set ship data
        self.text_mmsi = wx.StaticText(shipdata_panel,-1,'',pos=(100,25),size=(300,16))
        self.text_imo = wx.StaticText(shipdata_panel,-1,'',pos=(100,45),size=(300,16))
        self.text_country = wx.StaticText(shipdata_panel,-1,'',size=(300,16),pos=(100,65))
        self.text_name = wx.StaticText(shipdata_panel,-1,'',pos=(100,85),size=(300,16))
        self.text_type = wx.StaticText(shipdata_panel,-1,'',pos=(100,105),size=(300,16))
        self.text_callsign = wx.StaticText(shipdata_panel,-1,'',pos=(100,125),size=(300,16))
        self.text_length = wx.StaticText(shipdata_panel,-1,'',pos=(100,145),size=(300,16))
        self.text_width = wx.StaticText(shipdata_panel,-1,'',pos=(100,165),size=(300,16))
        self.text_draught = wx.StaticText(shipdata_panel,-1,'',pos=(100,185),size=(300,16))
        # Set voyage data
        self.text_destination = wx.StaticText(voyagedata_panel,-1,'',pos=(100,25),size=(185,16))
        self.text_etatime = wx.StaticText(voyagedata_panel,-1,'',pos=(100,45),size=(185,16))
        self.text_latitude = wx.StaticText(voyagedata_panel,-1,'',pos=(100,65),size=(185,16))
        self.text_longitude = wx.StaticText(voyagedata_panel,-1,'',pos=(100,85),size=(185,16))
        self.text_georef = wx.StaticText(voyagedata_panel,-1,'',pos=(100,105),size=(185,16))
        self.text_sog = wx.StaticText(voyagedata_panel,-1,'',pos=(100,125),size=(185,16))
        self.text_cog = wx.StaticText(voyagedata_panel,-1,'',pos=(100,145),size=(185,16))
        self.text_heading = wx.StaticText(voyagedata_panel,-1,'',pos=(100,165),size=(185,16))
        self.text_rateofturn = wx.StaticText(voyagedata_panel,-1,'',pos=(100,185),size=(185,16))
        # Set transponderdata
        self.text_navstatus = wx.StaticText(transponderdata_panel,-1,'',pos=(105,65),size=(185,16))
        self.text_posacc = wx.StaticText(transponderdata_panel,-1,'',pos=(105,85),size=(185,16))
        # Set object information
        self.text_bearing = wx.StaticText(objinfo_panel,-1,'',pos=(105,25),size=(185,16))
        self.text_distance = wx.StaticText(objinfo_panel,-1,'',pos=(105,45),size=(185,16))
        self.text_updates = wx.StaticText(objinfo_panel,-1,'',pos=(105,65),size=(185,16))
        self.text_source = wx.StaticText(objinfo_panel,-1,'',pos=(105,85),size=(185,16))
        self.text_creationtime = wx.StaticText(objinfo_panel,-1,'',pos=(105,105),size=(185,16))
        self.text_time = wx.StaticText(objinfo_panel,-1,'',pos=(105,125),size=(185,16))
        # Set remark text
        self.text_remark = wx.StaticText(remark_panel,-1,'',pos=(12,25),size=(370,35),style=wx.ST_NO_AUTORESIZE)

        # Buttons & events
        closebutton = wx.Button(self,1,_("&Close"),pos=(490,438))
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=1)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Sizer setup
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        sizer1 = wx.FlexGridSizer(2,2)
        sizer2 = wx.BoxSizer(wx.VERTICAL)
        sizer_button = wx.BoxSizer(wx.HORIZONTAL)
        # Sizer1 is the sizer positioning the different panels (and static boxes)
        # Sizer2 is an inner sizer for th transponder data panel and remark panel
        sizer1.Add(shipdata_panel, 1, wx.EXPAND, 0)
        sizer1.Add(voyagedata_panel, 0)
        sizer2.Add(transponderdata_panel, 0)
        sizer2.Add(remark_panel, 0)
        sizer1.Add(sizer2)
        sizer1.Add(objinfo_panel, 0)
        mainsizer.Add(sizer1)
        mainsizer.AddSpacer((0,10))
        sizer_button.Add(closebutton, 0)
        mainsizer.Add(sizer_button, flag=wx.ALIGN_RIGHT)
        self.SetSizerAndFit(mainsizer)

        # Set self.itemmmsi to itemmmsi
        self.itemmmsi = itemmmsi

        # Update the initial data
        self.OnUpdate('')

        # Timer for updating the window
        self.timer = wx.Timer(self, -1)
        self.timer.Start(2000)
        wx.EVT_TIMER(self, -1, self.OnUpdate)

    def OnUpdate(self, event):
        # Query based on object's MMSI number
        try: itemdata = execSQL(DbCmd(SqlCmd, [("SELECT * FROM data WHERE mmsi LIKE ?", (self.itemmmsi,))]))[0]
        except: return
        try: iddbdata = execSQL(DbCmd(SqlCmd, [("SELECT * FROM iddb WHERE mmsi LIKE ?", (self.itemmmsi,))]))[0]
        except: pass
        # Set ship data
        self.text_mmsi.SetLabel(str(itemdata[0]))
        try:
            if itemdata[2]: self.text_imo.SetLabel(itemdata[2])
            elif not itemdata[2] and iddbdata[1]: self.text_imo.SetLabel('* '+str(iddbdata[1])+' *')
        except: pass
        if itemdata[1] or not itemdata[1]:
            country = _("[Non ISO]")
            if itemdata[1]: country = itemdata[1]
            if midfull.has_key(str(itemdata[0])[0:3]): country += ' - ' + midfull[str(itemdata[0])[0:3]]
            self.text_country.SetLabel(country)
        try:
            if itemdata[3]: self.text_name.SetLabel(itemdata[3])
            elif not itemdata[3] and iddbdata[2]: self.text_name.SetLabel('* '+str(iddbdata[2])+' *')
        except: pass
        if itemdata[4] and itemdata[5]: self.text_type.SetLabel(itemdata[4]+' - '+itemdata[5])
        try:
            if itemdata[6]: self.text_callsign.SetLabel(itemdata[6])
            elif not itemdata[6] and iddbdata[3]: self.text_callsign.SetLabel('* '+str(iddbdata[3])+' *')
        except: pass
        if itemdata[17]: self.text_length.SetLabel(itemdata[17]+' m')
        if itemdata[18]: self.text_width.SetLabel(itemdata[18]+' m')
        if itemdata[19]: self.text_draught.SetLabel(itemdata[19]+' m')
        # Set voyage data
        if itemdata[15]: self.text_destination.SetLabel(itemdata[15])
        if itemdata[16]:
            try:
                etatime = 0,int(itemdata[16][0:2]),int(itemdata[16][2:4]),int(itemdata[16][4:6]),int(itemdata[16][6:8]),1,1,1,1
                fulletatime = time.strftime(_("%d %B at %H:%M"),etatime)
            except: fulletatime = itemdata[16]
            if fulletatime == '00002460': fulletatime = ''
            self.text_etatime.SetLabel(fulletatime)
        if itemdata[7]:
            latitude = str(itemdata[7])
            try: latitude =  latitude[1:3] + u'° ' + latitude[3:5] + '.' + latitude[5:] + "' " + latitude[0:1]
            except: pass
            self.text_latitude.SetLabel(latitude)
        if itemdata[8]:
            longitude = str(itemdata[8])
            try: longitude = longitude[1:4] + u'° ' + longitude[4:6] + '.' + longitude[6:] + "' " + longitude[0:1]
            except: pass
            self.text_longitude.SetLabel(longitude)
        if itemdata[9]: self.text_georef.SetLabel(itemdata[9])
        if itemdata[12]: self.text_sog.SetLabel(str(itemdata[12])+' kn')
        if itemdata[13]: self.text_cog.SetLabel(str(itemdata[13])+u'°')
        if itemdata[14]: self.text_heading.SetLabel(str(itemdata[14])+u'°')
        if itemdata[20]: self.text_rateofturn.SetLabel(str(itemdata[20])+u' °/m')
        # Set transponder data
        if itemdata[23]:
            self.text_navstatus.SetLabel(itemdata[23])
        if itemdata[24]:
            if itemdata[24] == '0': posacc = _("Good / GPS")
            else: posacc = _("Very good / DGPS")
            self.text_posacc.SetLabel(posacc)
        # Set local info
        if itemdata[25] and itemdata[26]:
            self.text_bearing.SetLabel(str(itemdata[26])+u'°')
            self.text_distance.SetLabel(str(itemdata[25])+' km')
        if itemdata[10]:
            try: creationtime = itemdata[10].replace('T', " "+_("at")+" ")
            except: creationtime = ''
            self.text_creationtime.SetLabel(creationtime)
        if itemdata[11]:
            try: lasttime = itemdata[11].replace('T', " "+_("at")+" ")
            except: lasttime = ''
            self.text_time.SetLabel(lasttime)
        if itemdata[28]:
            self.text_updates.SetLabel(str(itemdata[28]))
        if itemdata[27]:
            self.text_source.SetLabel(str(itemdata[27]))
        # Set remark text
        if remarkdict.has_key(int(itemdata[0])): self.text_remark.SetLabel(unicode(remarkdict[int(itemdata[0])]))

    def OnClose(self, event):
        self.timer.Stop()
        self.Destroy()


class StatsWindow(wx.Dialog):
    def __init__(self, parent, id):
        # Define the dialog
        wx.Dialog.__init__(self, parent, id, title=_("Statistics"))
        # Create panels
        objects_panel = wx.Panel(self, -1)
        objects_panel.SetMinSize((280,-1))
        horizon_panel = wx.Panel(self, -1)
        input_panel = wx.Panel(self, -1)
        input_panel.SetMinSize((250,-1))
        uptime_panel = wx.Panel(self, -1)
        # Create static boxes
        box_objects = wx.StaticBox(objects_panel,-1,_(" Objects "))
        box_horizon = wx.StaticBox(horizon_panel,-1,_(" Radio Horizon (calculated) "))
        box_input = wx.StaticBox(input_panel,-1,_(" Input "))
        box_uptime = wx.StaticBox(uptime_panel,-1,_(" Uptime "))

        # Object panels, texts and sizers
        obj_panel_left = wx.Panel(objects_panel)
        obj_panel_right = wx.Panel(objects_panel)
        wx.StaticText(obj_panel_left,-1,_("Number of objects:"),pos=(-1,0))
        wx.StaticText(obj_panel_left,-1,_("Number of old objects:"),pos=(-1,20))
        wx.StaticText(obj_panel_left,-1,_("Objects with a calculated distance:"),pos=(-1,40))
        self.text_object_nbr = wx.StaticText(obj_panel_right,-1,'',pos=(-1,0))
        self.text_object_grey_nbr = wx.StaticText(obj_panel_right,-1,'',pos=(-1,20))
        self.text_object_distance_nbr = wx.StaticText(obj_panel_right,-1,'',pos=(-1,40))
        obj_sizer = wx.StaticBoxSizer(box_objects, wx.HORIZONTAL)
        obj_sizer.AddSpacer(5)
        obj_sizer.Add(obj_panel_left)
        obj_sizer.AddSpacer(10)
        obj_sizer.Add(obj_panel_right, wx.EXPAND)
        objects_panel.SetSizer(obj_sizer)

        # Horizon panels, texts and sizers
        hor_panel_left = wx.Panel(horizon_panel)
        hor_panel_right = wx.Panel(horizon_panel)
        wx.StaticText(hor_panel_left,-1,_("Minimum:"),pos=(-1,0))
        wx.StaticText(hor_panel_left,-1,_("Maximum:"),pos=(-1,20))
        wx.StaticText(hor_panel_left,-1,_("Mean value:"),pos=(-1,40))
        wx.StaticText(hor_panel_left,-1,_("Median value:"),pos=(-1,60))
        self.text_horizon_min = wx.StaticText(hor_panel_right,-1,'',pos=(-1,0))
        self.text_horizon_max = wx.StaticText(hor_panel_right,-1,'',pos=(-1,20))
        self.text_horizon_mean = wx.StaticText(hor_panel_right,-1,'',pos=(-1,40))
        self.text_horizon_median = wx.StaticText(hor_panel_right,-1,'',pos=(-1,60))
        hor_sizer = wx.StaticBoxSizer(box_horizon, wx.HORIZONTAL)
        hor_sizer.AddSpacer(5)
        hor_sizer.Add(hor_panel_left)
        hor_sizer.AddSpacer(10)
        hor_sizer.Add(hor_panel_right, wx.EXPAND)
        horizon_panel.SetSizer(hor_sizer)

        # Input panels, texts and sizers
        serial_a = self.MakeInputStatSizer(input_panel," "+_("Serial Port A")+" ("+config['serial_a']['port']+") ")
        serial_b = self.MakeInputStatSizer(input_panel," "+_("Serial Port B")+" ("+config['serial_b']['port']+") ")
        serial_c = self.MakeInputStatSizer(input_panel," "+_("Serial Port C")+" ("+config['serial_c']['port']+") ")
        network = self.MakeInputStatSizer(input_panel," "+_("Network client")+" ("+config['network']['client_address']+") ")
        self.text_input_serial_a_received = serial_a[1]
        self.text_input_serial_a_parsed = serial_a[2]
        self.text_input_serial_a_parserate = serial_a[3]
        self.text_input_serial_b_received = serial_b[1]
        self.text_input_serial_b_parsed = serial_b[2]
        self.text_input_serial_b_parserate = serial_b[3]
        self.text_input_serial_c_received = serial_c[1]
        self.text_input_serial_c_parsed = serial_c[2]
        self.text_input_serial_c_parserate = serial_c[3]
        self.text_input_network_received = network[1]
        self.text_input_network_parsed = network[2]
        self.text_input_network_parserate = network[3]
        input_sizer = wx.StaticBoxSizer(box_input, wx.VERTICAL)
        input_sizer.AddSpacer(5)
        input_sizer.Add(serial_a[0], 0, wx.EXPAND)
        input_sizer.AddSpacer(5)
        input_sizer.Add(serial_b[0], 0, wx.EXPAND)
        input_sizer.AddSpacer(5)
        input_sizer.Add(serial_c[0], 0, wx.EXPAND)
        input_sizer.AddSpacer(5)
        input_sizer.Add(network[0], 0, wx.EXPAND)
        input_panel.SetSizer(input_sizer)

        # Uptime panels, texts and sizers
        up_panel_left = wx.Panel(uptime_panel)
        up_panel_right = wx.Panel(uptime_panel)
        wx.StaticText(up_panel_left,-1,_("Uptime:"),pos=(-1,0))
        wx.StaticText(up_panel_left,-1,_("Up since:"),pos=(-1,20))
        self.text_uptime_delta = wx.StaticText(up_panel_right,-1,'',pos=(-1,0))
        self.text_uptime_since = wx.StaticText(up_panel_right,-1,'',pos=(-1,20))
        up_sizer = wx.StaticBoxSizer(box_uptime, wx.HORIZONTAL)
        up_sizer.AddSpacer(5)
        up_sizer.Add(up_panel_left)
        up_sizer.AddSpacer(10)
        up_sizer.Add(up_panel_right, wx.EXPAND)
        uptime_panel.SetSizer(up_sizer)

        # Buttons & events
        closebutton = wx.Button(self,1,_("&Close"),pos=(490,438))
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=1)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Sizer setup
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer2 = wx.BoxSizer(wx.VERTICAL)
        sizer_button = wx.BoxSizer(wx.HORIZONTAL)
        # Sizer1 is the sizer positioning the different panels (and static boxes)
        # Sizer2 is an inner sizer for th transponder data panel and remark panel
        sizer2.Add(objects_panel, 0)
        sizer2.AddSpacer(5)
        sizer2.Add(horizon_panel, 0, wx.EXPAND)
        sizer2.AddSpacer(5)
        sizer2.Add(uptime_panel, 0, wx.EXPAND)
        sizer1.Add(sizer2)
        sizer1.AddSpacer(5)
        sizer1.Add(input_panel, 0, wx.EXPAND)
        mainsizer.Add(sizer1)
        mainsizer.AddSpacer((0,10))
        sizer_button.Add(closebutton, 0)
        mainsizer.Add(sizer_button, flag=wx.ALIGN_RIGHT)
        self.SetSizerAndFit(mainsizer)

        # Update the initial data
        self.LastUpdateTime = 0
        self.OldParseStats = {}
        self.OnUpdate('')

        # Timer for updating the window
        self.timer = wx.Timer(self, -1)
        self.timer.Start(2000)
        wx.EVT_TIMER(self, -1, self.OnUpdate)

    def MakeInputStatSizer(self, panel, boxlabel):
        # Creates a StaticBoxSizer and the StaticText in it
        box = wx.StaticBox(panel, -1, boxlabel)
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)
        panel_left = wx.Panel(panel)
        panel_right = wx.Panel(panel)
        wx.StaticText(panel_left,-1,_("Received:"),pos=(-1,0))
        wx.StaticText(panel_left,-1,_("Parsed:"),pos=(-1,20))
        wx.StaticText(panel_left,-1,_("Parsed rate:"),pos=(-1,40))
        received = wx.StaticText(panel_right,-1,'',pos=(-1,0))
        parsed = wx.StaticText(panel_right,-1,'',pos=(-1,20))
        parsed_rate = wx.StaticText(panel_right,-1,'',pos=(-1,40))
        sizer.AddSpacer(5)
        sizer.Add(panel_left, 0)
        sizer.AddSpacer(10)
        sizer.Add(panel_right, 1, wx.EXPAND)
        return sizer, received, parsed, parsed_rate

    def OnUpdate(self, event):
        # Update data in the window
        horizon = self.CalcHorizon()
        input_stats = GetStats()
        rates = self.CalcParseRate(input_stats)
        # Objects text
        self.text_object_nbr.SetLabel(str(horizon[0]))
        self.text_object_grey_nbr.SetLabel(str(horizon[1]))
        self.text_object_distance_nbr.SetLabel(str(horizon[2]))
        # Horizon text
        self.text_horizon_min.SetLabel(str(round(horizon[3],1)) + " km")
        self.text_horizon_max.SetLabel(str(round(horizon[4],1)) + " km")
        self.text_horizon_mean.SetLabel(str(round(horizon[5],1)) + " km")
        self.text_horizon_median.SetLabel(str(round(horizon[6],1)) + " km")
        # Uptime text
        uptime = datetime.datetime.now() - start_time
        up_since = start_time.isoformat()[:19]
        self.text_uptime_delta.SetLabel(str(uptime).split('.')[0])
        self.text_uptime_since.SetLabel(str(up_since.replace('T', " "+_("at")+" ")))
        # Input text
        if input_stats.has_key('serial_a'):
            self.text_input_serial_a_received.SetLabel(str(input_stats['serial_a']['received'])+_(" msgs"))
            self.text_input_serial_a_parsed.SetLabel(str(input_stats['serial_a']['parsed'])+_(" msgs"))
            if rates.has_key('serial_a'):
                self.text_input_serial_a_parserate.SetLabel(str(rates['serial_a'])+_(" msgs/sec"))
        if input_stats.has_key('serial_b'):
            self.text_input_serial_b_received.SetLabel(str(input_stats['serial_b']['received'])+_(" msgs"))
            self.text_input_serial_b_parsed.SetLabel(str(input_stats['serial_b']['parsed'])+_(" msgs"))
            if rates.has_key('serial_b'):
                self.text_input_serial_b_parserate.SetLabel(str(rates['serial_b'])+_(" msgs/sec"))
        if input_stats.has_key('serial_c'):
            self.text_input_serial_c_received.SetLabel(str(input_stats['serial_c']['received'])+_(" msgs"))
            self.text_input_serial_c_parsed.SetLabel(str(input_stats['serial_c']['parsed'])+_(" msgs"))
            if rates.has_key('serial_c'):
                self.text_input_serial_c_parserate.SetLabel(str(rates['serial_c'])+_(" msgs/sec"))
        if input_stats.has_key('network'):
            self.text_input_network_received.SetLabel(str(input_stats['network']['received'])+_(" msgs"))
            self.text_input_network_parsed.SetLabel(str(input_stats['network']['parsed'])+_(" msgs"))
            if rates.has_key('network'):
                self.text_input_network_parserate.SetLabel(str(rates['network'])+_(" msgs/sec"))

    def CalcParseRate(self, input_stats):
        # Compare data from last run with new data and calculate a parse rate
        data = {}
        # If there are a LastUpdateTime, check for input_stats
        if self.LastUpdateTime:
            # Calculate a timediff (in seconds)
            timediff = time.time() - self.LastUpdateTime
            # Check if input_stats has key, and then check if OldParseStats are available
            if input_stats.has_key('serial_a'):
                if self.OldParseStats.has_key('serial_a'):
                    rate = round(((input_stats['serial_a']['parsed'] - self.OldParseStats['serial_a']) / timediff), 1)
                    data['serial_a'] = rate
                self.OldParseStats['serial_a'] = int(input_stats['serial_a']['parsed'])
            if input_stats.has_key('serial_b'):
                if self.OldParseStats.has_key('serial_b'):
                    rate = round(((input_stats['serial_b']['parsed'] - self.OldParseStats['serial_b']) / timediff), 1)
                    data['serial_b'] = rate
                self.OldParseStats['serial_b'] = int(input_stats['serial_b']['parsed'])
            if input_stats.has_key('serial_c'):
                if self.OldParseStats.has_key('serial_c'):
                    rate = round(((input_stats['serial_c']['parsed'] - self.OldParseStats['serial_c']) / timediff), 1)
                    data['serial_c'] = rate
                self.OldParseStats['serial_c'] = int(input_stats['serial_c']['parsed'])
            if input_stats.has_key('network'):
                if self.OldParseStats.has_key('network'):
                    rate = round(((input_stats['network']['parsed'] - self.OldParseStats['network']) / timediff), 1)
                    data['network'] = rate
                self.OldParseStats['network'] = int(input_stats['network']['parsed'])
        # Set current time to LastUpdateTime
        self.LastUpdateTime = time.time()
        return data

    def CalcHorizon(self):
        # Calculate a "horizon", the distance to greyed out objects
        old = []
        # Fetch the total number of rows in the db
        query1 = execSQL(DbCmd(SqlCmd, [("SELECT mmsi FROM data", ())]))
        nritems = len(query1)
        # Fetch the greyed out rows in the db
        query2 = execSQL(DbCmd(SqlCmd, [("SELECT mmsi, distance FROM data WHERE datetime(time) < datetime('now', 'localtime', '-%s seconds')" % config['common'].as_int('listmakegreytime'), ())]))
        nrgreyitems = len(query2)
        # Set as initial values
        nrhorizonitems = 0
        totaldistance = 0
        distancevalues = []
        # Extract values from the SQL-query
        for v in query2:
            if v[1]:
                totaldistance += float(v[1])
                distancevalues.append(float(v[1]))
                nrhorizonitems += 1
        # Calculate median
        median = 0
        # Calculate meanvalue
        if totaldistance > 0: mean = (totaldistance/nrhorizonitems)
        else: mean = 0
        # Sort the list and take the middle element.
        n = len(distancevalues)
        copy = distancevalues[:] # So that "numbers" keeps its original order
        copy.sort()
        if n > 2:
            if n & 1:         # There is an odd number of elements
                median = copy[n // 2]
            else:
                median = (copy[n // 2 - 1] + copy[n // 2]) / 2
        # Calculate minimum and maximum
        minimum = 0
        maximum = 0
        try:
            minimum = min(distancevalues)
            maximum = max(distancevalues)
        except: pass
        # Return strings
        return nritems, nrgreyitems, nrhorizonitems, minimum, maximum, mean, median

    def OnClose(self, event):
        self.timer.Stop()
        self.Destroy()


class SetAlertsWindow(wx.Dialog):
    def __init__(self, parent, id):
        # Define the dialog
        wx.Dialog.__init__(self, parent, id, title=_("Set alerts and remarks"))
        # Create panels
        filter_panel = wx.Panel(self, -1)
        list_panel = wx.Panel(self, -1)
        object_panel = wx.Panel(self, -1)
        action_panel = wx.Panel(self, -1)
        # Create static boxes
        wx.StaticBox(filter_panel, -1, _(" Filter "), pos=(3,5), size=(700,100))
        list_staticbox = wx.StaticBox(list_panel, -1, _(" List view "), pos=(3,5), size=(700,280))
        wx.StaticBox(object_panel, -1, _(" Selected object "), pos=(3,5), size=(520,160))
        wx.StaticBox(action_panel, -1, _(" Actions "), pos=(3,5), size=(170,160))

        # Create objects on the filter panel
        wx.StaticText(filter_panel, -1, _("Filter using the checkboxes or by typing in the text box"), pos=(20,28))
        self.checkbox_filteralerts = wx.CheckBox(filter_panel, -1, _("Only show objects with alerts"), pos=(10,50))
        self.checkbox_filterremarks = wx.CheckBox(filter_panel, -1, _("Only show objects with remarks"), pos=(10,70))
        self.combobox_filtercolumn = wx.ComboBox(filter_panel, -1, pos=(300,60), size=(100,-1), value="Name", choices=("MMSI", "IMO", "Callsign", "Name"), style=wx.CB_READONLY)
        self.textctrl_filtertext = wx.TextCtrl(filter_panel, -1, pos=(415,60),size=(250,-1))

        # Define class-wide variable containing current filtering
        # If filter_query is empty, no SQL-filter is set
        # If filter_alerts is true, only show rows where alerts are set.
        # If filter_rermarks is true, only show rows where remarks are set.
        self.current_filter = {"filter_query": "", "filter_alerts": False, "filter_remarks": False}

        # Create the list control
        self.lc = self.List(list_panel, self)

        # Create the object information objects
        wx.StaticText(object_panel, -1, _("MMSI nbr:"), pos=(20,25))
        self.statictext_mmsi = wx.StaticText(object_panel, -1, '', pos=(20,45))
        wx.StaticText(object_panel, -1, _("IMO nbr:"), pos=(120,25))
        self.statictext_imo = wx.StaticText(object_panel, -1, '', pos=(120,45))
        wx.StaticText(object_panel, -1, _("Callsign:"), pos=(220,25))
        self.statictext_cs = wx.StaticText(object_panel, -1, '', pos=(220,45))
        wx.StaticText(object_panel, -1, _("Name:"), pos=(320,25))
        self.statictext_name = wx.StaticText(object_panel, -1, '', pos=(320,45))
        statictext_remark = wx.StaticText(object_panel, -1, _("Remark field:"), pos=(25,73))
        statictext_remark.SetFont(wx.Font(10, wx.NORMAL, wx.NORMAL, wx.NORMAL))
        self.textctrl_remark = wx.TextCtrl(object_panel, -1, pos=(20,90), size=(300,60), style=wx.TE_MULTILINE)
        self.radiobox_alert = wx.RadioBox(object_panel, -1, _(" Alert "), pos=(340,70), choices=(_("&No"), _("&Yes"), _("&Sound")))
        update_button = wx.Button(object_panel, 10, _("Save &object"), pos=(350,120))

        # Create buttons
        wx.Button(action_panel, 20, _("&Insert new..."), pos=(20,40))
        wx.Button(action_panel, 21, _("&Advanced..."), pos=(20,80))
        wx.Button(action_panel, 22, _("&Export list..."), pos=(20,120))
        close_button = wx.Button(self, 30, _("&Close"))
        save_button = wx.Button(self, 31, _("&Save changes"))

        # Create sizers
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        mainsizer.Add(filter_panel, 1, wx.EXPAND, 0)
        mainsizer.Add(list_panel, 0)
        lowsizer = wx.BoxSizer(wx.HORIZONTAL)
        lowsizer.Add(object_panel, 1)
        lowsizer.Add(action_panel, 0, wx.EXPAND)
        mainsizer.Add(lowsizer, 0)
        mainsizer.AddSpacer((0,10))
        mainsizer.Add(sizer2, flag=wx.ALIGN_RIGHT)
        sizer2.Add(close_button, 0)
        sizer2.AddSpacer((20,0))
        sizer2.Add(save_button, 0)
        self.SetSizerAndFit(mainsizer)
        mainsizer.Layout()

        # Define events
        self.Bind(wx.EVT_CHECKBOX, self.OnFilter, self.checkbox_filteralerts)
        self.Bind(wx.EVT_CHECKBOX, self.OnFilter, self.checkbox_filterremarks)
        self.Bind(wx.EVT_TEXT, self.OnFilter, self.textctrl_filtertext)
        self.Bind(wx.EVT_BUTTON, self.OnSaveObject, id=10)
        self.Bind(wx.EVT_BUTTON, self.OnInsertNew, id=20)
        self.Bind(wx.EVT_BUTTON, self.OnAdvanced, id=21)
        self.Bind(wx.EVT_BUTTON, self.OnExportList, id=22)
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=30)
        self.Bind(wx.EVT_BUTTON, self.OnSaveChanges, id=31)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def GenerateAlertQuery(self):
        # Create a query string from alertlist
        global alertstring
        if len(alertlist) > 0:
            alertstring = '(' + ') OR ('.join(zip(*alertlist)[0]) + ')'
        else: alertstring = '()'
        # Initiate variabels for alert sound query
        querysoundlist = []
        global alertstringsound
        # Loop over alertlist and append those with sound alert to alertsoundlist
        for i in alertlist:
            if i[1] == 1:
               querysoundlist.append(i)
        # If querysoundlist is not empty, make a query string of it
        if len(querysoundlist) > 0:
            alertstringsound = '(' + ') OR ('.join(zip(*querysoundlist)[0]) + ')'
        else: alertstringsound = '()'

    def PopulateObject(self, objectinfo):
        # Populate the objec_panel with info from the currently selected list row
        self.loaded_objectinfo = objectinfo
        self.statictext_mmsi.SetLabel(unicode(objectinfo[0]))
        self.statictext_imo.SetLabel(unicode(objectinfo[1]))
        self.statictext_cs.SetLabel(unicode(objectinfo[2]))
        self.statictext_name.SetLabel(unicode(objectinfo[3]))
        self.radiobox_alert.SetSelection(int(objectinfo[4]))
        self.textctrl_remark.SetValue(unicode(objectinfo[5]))

    def OnSaveObject(self, event):
        # Check if variable exist, if not, return
        try:
            assert self.loaded_objectinfo
        except: return
        # Read in the object information to be saved
        mmsi = int(self.loaded_objectinfo[0])
        alert_oldstate = self.loaded_objectinfo[4]
        remark_oldstate = self.loaded_objectinfo[5]
        alert_newstate = self.radiobox_alert.GetSelection()
        remark_newstate = unicode(self.textctrl_remark.GetValue())
        # Check if the alert state has changed
        if alert_oldstate != alert_newstate:
            # Create counter variables
            i = 0
            pos = -1
            # Create query from mmsi
            query = "mmsi LIKE '" + str(mmsi) + "'"
            # Loop over alertlist, try to find the query matching the mmsi
            # If found, set its list position in pos
            for v in alertlist:
                if v[0].find(query) != -1:
                    pos = i
                i += 1
            # If alert is off
            if alert_newstate == 0:
                # Delete query if pos is set
                if pos != -1:
                    del alertlist[pos]
            # If alert is on
            elif alert_newstate == 1:
                # Create tuple to insert into list
                query_tuple = (query, 0, 0)
                # If object already in alertlist, set pos to query_tuple, else append to alertlist
                if pos != -1:
                    alertlist[pos] = query_tuple
                else:
                    alertlist.append(query_tuple)
            # If sound alert is set
            elif alert_newstate == 2:
                # Create tuple to insert into list
                query_tuple = (query, 1, 0)
                # If object already in alertlist, set pos to query_tuple, else append to alertlist
                if pos != -1:
                    alertlist[pos] = query_tuple
                else:
                    alertlist.append(query_tuple)
            # Call function to generate the new alert and sound alert queries
            self.GenerateAlertQuery()
        # Remove remark if the remark text ctrl is empty or only contains whitespace
        if len(remark_newstate) == 0 or remark_newstate.isspace():
            try: del remarkdict[mmsi]
            except: pass
        else:
            # Set the new remark
            remarkdict[mmsi] = remark_newstate.replace(",", ";")
        # Update the listctrl
        self.lc.OnUpdate()
        # Update the objectinfo
        self.lc.UpdateActiveItem()

    def OnFilter(self, event):
        # Read values from the filter controls and set appropriate values in self.current_filter
        self.current_filter["filter_alerts"] = self.checkbox_filteralerts.GetValue()
        self.current_filter["filter_remarks"] = self.checkbox_filterremarks.GetValue()
        # If the text control contains text, create a SQL-query from the value in the combobox
        # and the text control. Replace dangerous char (').
        # Else, set the filter query to empty.
        if len(self.textctrl_filtertext.GetValue()) > 0:
            combostring = self.combobox_filtercolumn.GetValue()
            self.current_filter["filter_query"] = combostring + " LIKE '%" + self.textctrl_filtertext.GetValue().replace("'","") + "%'"
        else:
            self.current_filter["filter_query"] = ""
        # Update the listctrl
        self.lc.OnUpdate()

    def OnInsertNew(self, event):
        # Create a dialog with a textctrl, a checkbox and two buttons
        dlg = wx.Dialog(self, -1, _("Insert new MMSI number"), size=(300,225))
        wx.StaticText(dlg, -1, _("Fill in the MMSI number you want to insert and choose the data to associate it with."), pos=(20,10), size=(260,60))
        textbox = wx.TextCtrl(dlg, -1, pos=(20,70), size=(150,-1))
        radiobox = wx.RadioBox(dlg, -1, _(" Associate with "), pos=(20,110), choices=(_("&Alert"), _("&Remark")))
        buttonsizer = dlg.CreateStdDialogButtonSizer(wx.CANCEL|wx.OK)
        buttonsizer.SetDimension(110, 165, 180, 40)
        textbox.SetFocus()
        # If user press OK, check that the textbox only contains digits, check if the number already exists
        # and if not, update either the alertlist or the remarkdict
        if dlg.ShowModal() == wx.ID_OK:
            new_mmsi = textbox.GetValue()
            if not new_mmsi.isdigit() or len(new_mmsi) > 9:
                dlg = wx.MessageDialog(self, _("Only nine digits are allowed in a MMSI number! Insert failed."), _("Error"), wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            elif self.lc.CheckForMmsi(int(new_mmsi)):
                dlg = wx.MessageDialog(self, _("The specified MMSI number already exists! Insert failed."), _("Error"), wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            elif radiobox.GetSelection() == 0:
                query = "mmsi LIKE '" + unicode(new_mmsi) + "'"
                alertlist.append((query, 0, 0))
            elif radiobox.GetSelection() == 1:
                remarkdict[int(new_mmsi)] = "REMARK NOT SET"
            # Update the alert queries
            self.GenerateAlertQuery()
            # Update list ctrl
            self.lc.OnUpdate()
            # Set active item
            self.lc.SetActiveItem(int(new_mmsi))

    def OnAdvanced(self, event):
        # Call the advanced alert editor
        dlg = AdvancedAlertWindow(self, -1)
        dlg.ShowModal()
        # Update list ctrl to display any changes
        self.lc.OnUpdate()

    def OnSaveChanges(self, event):
        # Saves both alerts and remarks to the loaded files.
        alert_file = config['alert']['alertfile']
        remark_file = config['alert']['remarkfile']
        if config['alert'].as_bool('alertfile_on'):
            self.SaveAlertFile(alert_file)
        else:
            dlg = wx.MessageDialog(self, _("Cannot save alert file. No alert file is loaded.") + "\n" + _("Edit the alert file settings and restart the program."), style=wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
        if config['alert'].as_bool('remarkfile_on'):
            self.SaveRemarkFile(remark_file)
        else:
            dlg = wx.MessageDialog(self, _("Cannot save remark file. No remark file is loaded.") + "\n" + _("Edit the remark file settings and restart the program."), style=wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()

    def SaveAlertFile(self, file):
        # Saves alerts to a supplied file
        if len(file) > 0:
            try:
                output = open(file, 'wb')
                outdata = alertlist[:]
                outdata.insert(0, 'Alertdata')
                pickle.dump(outdata,output)
                output.close()
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Cannot save alert file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except UnicodeDecodeError, error:
                dlg = wx.MessageDialog(self, _("Cannot save alert file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()

    def SaveRemarkFile(self, file):
        # Saves remarks to a supplied file
        if len(file) > 0:
            try:
                output = codecs.open(file, 'w', encoding='cp1252')
                for entry in remarkdict.iteritems():
                    # For each entry split the data using ','
                    mmsi = str(entry[0])
                    remark = entry[1]
                    output.write(mmsi + "," + remark + "\r\n")
                output.close()
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Cannot save remark file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except error:
                dlg = wx.MessageDialog(self, _("Cannot save remark file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()

    def OnExportList(self, event):
        # Exports the current list view to the clipboard.
        exportdata = ""
        for v in self.lc.itemDataMap.iteritems():
            row = v[1]
            alert = row[4]
            if alert == 0:
                alert = "No"
            elif alert == 1:
                alert = "Yes"
            elif alert == 2:
                alert = "Yes/Sound"
            exportdata += str(row[0]) + "," + row[1] + "," + row[2] + "," + row[3] + "," + alert + "," + row[5] + "\n"
        # Create file dialog
        file = ''
        wcd = _("CSV files (*.csv)|*.csv|All files (*)|*")
        dir = os.getcwd()
        open_dlg = wx.FileDialog(self, message=_("Choose file to save current list"), defaultDir=dir, defaultFile='list.csv', wildcard=wcd, style=wx.SAVE)
        if open_dlg.ShowModal() == wx.ID_OK:
            file = open_dlg.GetPath()
        if len(file) > 0:
            # Save the data
            try:
                output = codecs.open(file, 'w', encoding='cp1252')
                output.write(exportdata)
                output.close()
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Cannot save file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except error:
                dlg = wx.MessageDialog(self, _("Cannot save file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()


    class List(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin, listmix.ColumnSorterMixin):
        def __init__(self, parent, topparent):
            wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT|wx.LC_VIRTUAL|wx.LC_SINGLE_SEL, size=(650,230), pos=(20,30))

            self.topparent = topparent

            # Define and retreive two arrows, one upwards, the other downwards
            self.imagelist = wx.ImageList(16, 16)
            self.sm_up = self.imagelist.Add(getSmallUpArrowBitmap())
            self.sm_dn = self.imagelist.Add(getSmallDnArrowBitmap())
            self.SetImageList(self.imagelist, wx.IMAGE_LIST_SMALL)

            # Iterate over the given columns and create the specified ones
            self.InsertColumn(0, _("MMSI nbr"))
            self.InsertColumn(1, _("IMO nbr"))
            self.InsertColumn(2, _("CS"))
            self.InsertColumn(3, _("Name"))
            self.InsertColumn(4, _("Alert"))
            self.InsertColumn(5, _("Remark"))
            self.SetColumnWidth(0, 90)
            self.SetColumnWidth(1, 80)
            self.SetColumnWidth(2, 60)
            self.SetColumnWidth(3, 150)
            self.SetColumnWidth(4, 70)
            self.SetColumnWidth(5, 190)

            # Use the mixins
            listmix.ListCtrlAutoWidthMixin.__init__(self)
            listmix.ColumnSorterMixin.__init__(self, 6)

            # Do inital update
            self.OnUpdate()
            # Do initial sorting on column 0, ascending order (1)
            self.SortListItems(0, 1)

            # Define events
            self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)

        def OnUpdate(self):
            # Check if a row is selected, if true, extract the mmsi
            selected_row = self.GetNextItem(-1, -1, wx.LIST_STATE_SELECTED)
            if selected_row != -1:
                selected_mmsi = self.itemIndexMap[selected_row]

            # Check if filter is unactive. If active, filter. Otherwise, return all rows.
            if len(self.topparent.current_filter["filter_query"]) == 0:
                query = "mmsi LIKE '%'"
            else:
                query = self.topparent.current_filter["filter_query"]

            # Run the query against the iddb in memory
            iddb_result = execSQL(DbCmd(SqlCmd, [("SELECT * FROM iddb WHERE %s" % query,())]))

            # Create a dictionary containing the data from the iddb_query.
            # Use mmsi as key with value (imo, name, callsign)
            iddb_dict = {}
            for v in iddb_result:
                iddb_dict[v[0]] = [(v[1], v[2], v[3])]

            # Create a dictionary from the items in alertlist, extracting mmsi numbers from
            # the SQL-queries. Use the mmsi as key and sound alert as value (0: false, 1: true)
            alerts_mmsi_dict = {}
            for v in alertlist:
                query_string = v[0]
                if query_string.find("mmsi") or query_string.find("MMSI"):
                    try:
                        mmsi = int(query_string.strip("msiMSIlikeLIKE '"))
                        alerts_mmsi_dict[mmsi] = v[1]
                    except: pass

            # Create a set and make it contain all mmsi numbers from the dict keys
            all_mmsi = set(iddb_dict.keys())
            all_mmsi.update(alerts_mmsi_dict.keys())
            all_mmsi.update(remarkdict.keys())

            # Iterate over all the mmsi numbers and add the appropriate data
            # from the different dictionaries to list_dict
            list_dict = {}
            for mmsi in all_mmsi:
                # Define variables
                imo = ''; name = ''; callsign = ''; alert = 0; remark = ''
                # Extract data from iddb_dict (and from the inner list associated with the key)
                if iddb_dict.has_key(mmsi):
                    imo = iddb_dict[mmsi][0][0]
                    name = iddb_dict[mmsi][0][1]
                    callsign = iddb_dict[mmsi][0][2]
                # Extract data from alerts_mmsi_dict (when alert is 1: alert active, when 2: alert+sound active)
                if alerts_mmsi_dict.has_key(mmsi):
                    alert = alerts_mmsi_dict[mmsi]
                    if alert == 1:
                        alert = 2
                    elif alert == 0:
                        alert = 1
                # Extract data from remarkdict
                if remarkdict.has_key(mmsi):
                    remark = unicode(remarkdict[mmsi])
                # If there are filters active and the conditions are met, skip adding entry to list_dict
                filter = self.topparent.current_filter.copy()
                filter_query = filter["filter_query"]
                # Make sure that objects with only a mmsi won't show up when you use the filter on imo, name and callsign
                if filter_query and filter_query.find("MMSI") == -1 and len(imo) == 0 and len(name) == 0 and len(callsign) == 0:
                    pass
                # Make also shure that when filtering on mmsi, only show matches
                elif filter_query and filter_query.find("MMSI") != -1 and str(mmsi).find(filter_query.strip("msiMSIlikeLIKE '%")) == -1:
                    pass
                elif filter["filter_alerts"] and alert == 0:
                    pass
                elif filter["filter_remarks"] and remark == '':
                    pass
                else:
                    # For each mmsi in all_mmsi, write to list_dict and map the mmsi as key and add imo, name, callsign, alert and remark to it
                    list_dict[mmsi] = [mmsi, imo, callsign, name, alert, unicode(remark)]

            # Set new ItemCount for the list ctrl if different from the current number
            nrofobjects = len(list_dict)
            if self.GetItemCount() != nrofobjects:
                self.SetItemCount(nrofobjects)

            # Assign to variables for the virtual list ctrl
            self.itemDataMap = list_dict
            self.itemIndexMap = list_dict.keys()

            self.SortListItems()

            # Set the selected row
            try: self.SetActiveItem(selected_mmsi)
            except: pass

        def OnItemSelected(self, event):
            # Get the MMSI number associated with the selected row
            # Try to use event as a proper event, if except, use as a direct integer
            try:
                itemmmsi = self.itemIndexMap[event.m_itemIndex]
            except:
                itemmmsi = self.itemIndexMap[event]
            # Populate the object box
            self.topparent.PopulateObject(self.itemDataMap[itemmmsi])

        def UpdateActiveItem(self):
            # Get the currently selected row and call OnItemSelected
            selected_row = self.GetNextItem(-1, -1, wx.LIST_STATE_SELECTED)
            self.OnItemSelected(selected_row)

        def SetActiveItem(self, mmsi):
            # Set the active row to the specified MMSI number
            # If the mmsi is found, set the new position as selected and visible
            # If not found, deselect all objects
            if self.itemDataMap.has_key(int(mmsi)):
                new_position = self.itemIndexMap.index(int(mmsi))
                self.SetItemState(new_position, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
                self.EnsureVisible(new_position)
                return True
            else:
                for i in range(self.GetItemCount()):
                    self.SetItemState(i, 0, wx.LIST_STATE_SELECTED)
                return False

        def CheckForMmsi(self, mmsi):
            # This function simply checks if the supplied MMSI number is currently in the list ctrl
            if mmsi in self.itemIndexMap:
                return True
            else:
                return False

        def OnGetItemText(self, item, col):
            # Return the text in item, col
            mmsi = self.itemIndexMap[item]
            string = self.itemDataMap[mmsi][col]
            # If column with alerts, map 0, 1 and 2 to text strings
            if col == 4:
                if string == 0: string = _("No")
                elif string == 1: string = _("Yes")
                elif string == 2: string = _("Yes/Sound")
            # If string is an integer, make it to a unicode string
            if type(string) == int:
                string = unicode(string)
            # If string is a Nonetype, replace with an empty string
            elif string == None:
                string = unicode('')
            return string

        def SortItems(self,sorter=cmp):
            items = list(self.itemDataMap.keys())
            items.sort(sorter)
            self.itemIndexMap = items

            # Redraw the list
            self.Refresh()

        # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
        def GetListCtrl(self):
            return self

        # Used by the ColumnSorterMixin, see wx/lib/mixins/listctrl.py
        def GetSortImages(self):
            return (self.sm_dn, self.sm_up)

    def OnClose(self, event):
        self.Destroy()


class SettingsWindow(wx.Dialog):
    def __init__(self, parent, id):
        wx.Dialog.__init__(self, parent, id, title=_("Settings"))
        # Define a notebook
        notebook = wx.Notebook(self, -1)
        # Define panels for each tab in the notebook
        common_panel = wx.Panel(notebook, -1)
        serial_panel = wx.Panel(notebook, -1)
        network_panel = wx.Panel(notebook, -1)
        logging_panel = wx.Panel(notebook, -1)
        alert_panel = wx.Panel(notebook, -1)
        listview_panel = wx.Panel(notebook, -1)
        alertlistview_panel = wx.Panel(notebook, -1)

        # Populate panel for common options
        # Common list settings
        commonlist_panel = wx.Panel(common_panel, -1)
        wx.StaticBox(commonlist_panel, -1, _(" General view settings "), pos=(10,5), size=(450,140))
        wx.StaticText(commonlist_panel, -1, _("Threshold for greying-out objects (s):"), pos=(20,35))
        self.commonlist_greytime = wx.SpinCtrl(commonlist_panel, -1, pos=(250,30), min=10, max=604800)
        wx.StaticText(commonlist_panel, -1, _("Threshold for removal of objects (s):"), pos=(20,72))
        self.commonlist_deletetime = wx.SpinCtrl(commonlist_panel, -1, pos=(250,65), min=10, max=604800)
        wx.StaticText(commonlist_panel, -1, _("Time between view refreshes (ms):"), pos=(20,107))
        self.commonlist_refreshtime = wx.SpinCtrl(commonlist_panel, -1, pos=(250,100), min=1000, max=600000)
        # Manual position config
        manualpos_panel = wx.Panel(common_panel, -1)
        wx.StaticBox(manualpos_panel, -1, _(" Manual position settings "), pos=(10,-1), size=(450,140))
        self.manualpos_overridetoggle = wx.CheckBox(manualpos_panel, -1, _("Use the supplied manual position and ignore position messages"), pos=(20,23))
        wx.StaticText(manualpos_panel, -1, _("Latitude:"), pos=(20,60))
        self.manualpos_latdeg = wx.SpinCtrl(manualpos_panel, -1, pos=(90,54), size=(55,-1), min=0, max=90)
        wx.StaticText(manualpos_panel, -1, _("deg"), pos=(145,60))
        self.manualpos_latmin = wx.SpinCtrl(manualpos_panel, -1, pos=(180,54), size=(55,-1), min=0, max=60)
        wx.StaticText(manualpos_panel, -1, _("min"), pos=(235,60))
        self.manualpos_latdecmin = wx.SpinCtrl(manualpos_panel, -1, pos=(270,54), size=(55,-1), min=0, max=100)
        wx.StaticText(manualpos_panel, -1, _("dec min"), pos=(325,60))
        self.manualpos_latquad = wx.ComboBox(manualpos_panel, -1, pos=(390,54), size=(55,-1), choices=('N', 'S'), style=wx.CB_READONLY)
        wx.StaticText(manualpos_panel, -1, _("Longitude:"), pos=(20,100))
        self.manualpos_longdeg = wx.SpinCtrl(manualpos_panel, -1, pos=(90,94), size=(55,-1), min=0, max=180)
        wx.StaticText(manualpos_panel, -1, _("deg"), pos=(145,100))
        self.manualpos_longmin = wx.SpinCtrl(manualpos_panel, -1, pos=(180,94), size=(55,-1), min=0.0, max=60)
        wx.StaticText(manualpos_panel, -1, _("min"), pos=(235,100))
        self.manualpos_longdecmin = wx.SpinCtrl(manualpos_panel, -1, pos=(270,94), size=(55,-1), min=0, max=100)
        wx.StaticText(manualpos_panel, -1, _("dec min"), pos=(325,100))
        self.manualpos_longquad = wx.ComboBox(manualpos_panel, -1, pos=(390,94), size=(55,-1), choices=('E', 'W'), style=wx.CB_READONLY)
        # Add panels to main sizer
        common_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        common_panel_sizer.Add(commonlist_panel, 0)
        common_panel_sizer.Add(manualpos_panel, 0)
        common_panel.SetSizer(common_panel_sizer)

        # Populate panel for serial input config
        # Port A config
        porta_panel = wx.Panel(serial_panel, -1)
        wx.StaticBox(porta_panel, -1, _(" Settings for a primary serial port "), pos=(10,5), size=(450,125))
        self.porta_serialon = wx.CheckBox(porta_panel, -1, _("Activate reading from the primary serial port"), pos=(20,28))
        wx.StaticText(porta_panel, -1, _("Port: "), pos=(20,60))
        self.porta_port = wx.ComboBox(porta_panel, -1, pos=(110,60), size=(100,-1), choices=('Com1', 'Com2', 'Com3', 'Com4'))
        wx.StaticText(porta_panel, -1, _("Speed: "), pos=(20,95))
        self.porta_speed = wx.ComboBox(porta_panel, -1, pos=(110,90), size=(100,-1), choices=('9600', '38400'))
        self.porta_xonxoff = wx.CheckBox(porta_panel, -1, _("Software flow control:"), pos=(240,60), style=wx.ALIGN_RIGHT)
        self.porta_rtscts = wx.CheckBox(porta_panel, -1, _("RTS/CTS flow control:"), pos=(240,95), style=wx.ALIGN_RIGHT)
        # Port B config
        portb_panel = wx.Panel(serial_panel, -1)
        wx.StaticBox(portb_panel, -1, _(" Settings for a secondary serial port "), pos=(10,-1), size=(450,125))
        self.portb_serialon = wx.CheckBox(portb_panel, -1, _("Activate reading from the secondary serial port"), pos=(20,28))
        wx.StaticText(portb_panel, -1, _("Port: "), pos=(20,60))
        self.portb_port = wx.ComboBox(portb_panel, -1, pos=(110,60), size=(100,-1), choices=('Com1', 'Com2', 'Com3', 'Com4'))
        wx.StaticText(portb_panel, -1, _("Speed: "), pos=(20,95))
        self.portb_speed = wx.ComboBox(portb_panel, -1, pos=(110,90), size=(100,-1), choices=('9600', '38400'))
        self.portb_xonxoff = wx.CheckBox(portb_panel, -1, _("Software flow control:"), pos=(240,60), style=wx.ALIGN_RIGHT)
        self.portb_rtscts = wx.CheckBox(portb_panel, -1, _("RTS/CTS flow control:"), pos=(240,95), style=wx.ALIGN_RIGHT)
        # Port C config
        portc_panel = wx.Panel(serial_panel, -1)
        wx.StaticBox(portc_panel, -1, _(" Settings for a tertiary serial port "), pos=(10,-1), size=(450,125))
        self.portc_serialon = wx.CheckBox(portc_panel, -1, _("Activate reading from the tertiary serial port"), pos=(20,28))
        wx.StaticText(portc_panel, -1, _("Port: "), pos=(20,60))
        self.portc_port = wx.ComboBox(portc_panel, -1, pos=(110,60), size=(100,-1), choices=('Com1', 'Com2', 'Com3', 'Com4'))
        wx.StaticText(portc_panel, -1, _("Speed: "), pos=(20,95))
        self.portc_speed = wx.ComboBox(portc_panel, -1, pos=(110,90), size=(100,-1), choices=('9600', '38400'))
        self.portc_xonxoff = wx.CheckBox(portc_panel, -1, _("Software flow control:"), pos=(240,60), style=wx.ALIGN_RIGHT)
        self.portc_rtscts = wx.CheckBox(portc_panel, -1, _("RTS/CTS flow control:"), pos=(240,95), style=wx.ALIGN_RIGHT)
        # Add panels to main sizer
        serial_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        serial_panel_sizer.Add(porta_panel, 0)
        serial_panel_sizer.Add(portb_panel, 0)
        serial_panel_sizer.Add(portc_panel, 0)
        serial_panel.SetSizer(serial_panel_sizer)

        # Populate panel for network config
        # Network receive config
        netrec_panel = wx.Panel(network_panel, -1)
        wx.StaticBox(netrec_panel, -1, _(" Settings for reading from a network server "), pos=(10,5), size=(450,135))
        self.netrec_clienton = wx.CheckBox(netrec_panel, -1, _("Activate reading from server"), pos=(20,28))
        wx.StaticText(netrec_panel, -1, _("Address of streaming host (IP):"), pos=(20,65))
        self.netrec_clientaddress = wx.TextCtrl(netrec_panel, -1, pos=(230,58), size=(175,-1))
        wx.StaticText(netrec_panel, -1, _("Port of streaming host:"), pos=(20,100))
        self.netrec_clientport = wx.SpinCtrl(netrec_panel, -1, pos=(230,93), min=0, max=65535)
        # Network send config
        netsend_panel = wx.Panel(network_panel, -1)
        wx.StaticBox(netsend_panel, -1, _(" Settings for acting as a network server "), pos=(10,-1), size=(450,140))
        self.netsend_serveron = wx.CheckBox(netsend_panel, -1, _("Activate streaming network server (relay serial port data)"), pos=(20,28))
        wx.StaticText(netsend_panel, -1, _("Server address (this server) (IP):"), pos=(20,65))
        self.netsend_serveraddress = wx.TextCtrl(netsend_panel, -1, pos=(220,58), size=(175,-1))
        wx.StaticText(netsend_panel, -1, _("Server port (this server):"), pos=(20,100))
        self.netsend_serverport = wx.SpinCtrl(netsend_panel, -1, pos=(220,93), min=0, max=65535)
        # Add panels to main sizer
        network_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        network_panel_sizer.Add(netrec_panel, 0)
        network_panel_sizer.Add(netsend_panel, 0)
        network_panel.SetSizer(network_panel_sizer)

        # Populate panel for log config
        # Log config
        filelog_panel = wx.Panel(logging_panel, -1)
        wx.StaticBox(filelog_panel, -1, _(" Logging to file "), pos=(10,5), size=(450,140))
        self.filelog_logtoggle = wx.CheckBox(filelog_panel, -1, _("Activate logging to database file"), pos=(20,28))
        wx.StaticText(filelog_panel, -1, _("Time between loggings (s):"), pos=(20,65))
        self.filelog_logtime = wx.SpinCtrl(filelog_panel, -1, pos=(230,60), min=1, max=604800)
        wx.StaticText(filelog_panel, -1, _("Log file"), pos=(20,105))
        self.filelog_logfile = wx.TextCtrl(filelog_panel, -1, pos=(75,99), size=(275,-1))
        self.filelog_logfileselect = wx.Button(filelog_panel, -1, _("&Browse..."), pos=(365,95))
        self.Bind(wx.EVT_BUTTON, self.OnLogFileDialog, self.filelog_logfileselect)
        # Identification DB config
        iddblog_panel = wx.Panel(logging_panel, -1)
        wx.StaticBox(iddblog_panel, -1, _(" Logging to identification database (IDDB) "), pos=(10,5), size=(450,140))
        self.iddblog_logtoggle = wx.CheckBox(iddblog_panel, -1, _("Activate logging to IDDB file"), pos=(20,28))
        wx.StaticText(iddblog_panel, -1, _("Time between loggings (s):"), pos=(20,65))
        self.iddblog_logtime = wx.SpinCtrl(iddblog_panel, -1, pos=(230,60), min=1, max=604800)
        wx.StaticText(iddblog_panel, -1, _("IDDB file:"), pos=(20,105))
        self.iddblog_logfile = wx.TextCtrl(iddblog_panel, -1, pos=(75,99), size=(275,-1))
        self.iddblog_logfileselect = wx.Button(iddblog_panel, -1, _("&Browse..."), pos=(365,95))
        self.Bind(wx.EVT_BUTTON, self.OnIDDBFileDialog, self.iddblog_logfileselect)
        # Add panels to main sizer
        logging_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        logging_panel_sizer.Add(filelog_panel, 0)
        logging_panel_sizer.Add(iddblog_panel, 0)
        logging_panel.SetSizer(logging_panel_sizer)

        # Populate panel for alert config
        # Alert file config
        alertfile_panel = wx.Panel(alert_panel, -1)
        wx.StaticBox(alertfile_panel, -1, _(" Alert file "), pos=(10,5), size=(450,100))
        self.alertfile_toggle = wx.CheckBox(alertfile_panel, -1, _("Read alert file at program startup"), pos=(20,28))
        wx.StaticText(alertfile_panel, -1, _("Alert file:"), pos=(20,65))
        self.alertfile_file = wx.TextCtrl(alertfile_panel, -1, pos=(105,59), size=(250,-1))
        self.alertfile_fileselect = wx.Button(alertfile_panel, -1, _("&Browse..."), pos=(365,55))
        self.Bind(wx.EVT_BUTTON, self.OnAlertFileDialog, self.alertfile_fileselect)
        # Remark file config
        remarkfile_panel = wx.Panel(alert_panel, -1)
        wx.StaticBox(remarkfile_panel, -1, _(" Remark file "), pos=(10,5), size=(450,100))
        self.remarkfile_toggle = wx.CheckBox(remarkfile_panel, -1, _("Read remark file at program startup"), pos=(20,28))
        wx.StaticText(remarkfile_panel, -1, _("Remark file:"), pos=(20,65))
        self.remarkfile_file = wx.TextCtrl(remarkfile_panel, -1, pos=(105,59), size=(250,-1))
        self.remarkfile_fileselect = wx.Button(remarkfile_panel, -1, _("&Browse..."), pos=(365,55))
        self.Bind(wx.EVT_BUTTON, self.OnRemarkFileDialog, self.remarkfile_fileselect)
        # Alert sound file config
        alertsoundfile_panel = wx.Panel(alert_panel, -1)
        wx.StaticBox(alertsoundfile_panel, -1, _(" Sound alert settings "), pos=(10,-1), size=(450,100))
        self.alertsoundfile_toggle = wx.CheckBox(alertsoundfile_panel, -1, _("Activate sound alert"), pos=(20,23))
        wx.StaticText(alertsoundfile_panel, -1, _("Sound alert file:"), pos=(20,60))
        self.alertsoundfile_file = wx.TextCtrl(alertsoundfile_panel, -1, pos=(105,54), size=(250,-1))
        self.alertsoundfile_fileselect = wx.Button(alertsoundfile_panel, -1, _("&Browse..."), pos=(365,50))
        self.Bind(wx.EVT_BUTTON, self.OnAlertSoundFileDialog, self.alertsoundfile_fileselect)
        # Add panels to main sizer
        alert_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        alert_panel_sizer.Add(alertfile_panel, 0)
        alert_panel_sizer.Add(remarkfile_panel, 0)
        alert_panel_sizer.Add(alertsoundfile_panel, 0)
        alert_panel.SetSizer(alert_panel_sizer)

        # Populate panel for list view column setup
        # List view column config
        listcolumn_panel = wx.Panel(listview_panel, -1)
        wx.StaticBox(listcolumn_panel, -1, _(" Choose active columns in list view "), pos=(10,5), size=(450,280))
        wx.StaticText(listcolumn_panel, -1, _("Not active columns:"), pos=(35,40))
        self.listcolumn_notactive = wx.ListBox(listcolumn_panel, -1, pos=(30,60), size=(130,200), style=wx.LB_SINGLE|wx.LB_SORT)
        wx.Button(listcolumn_panel, 50, '-->', pos=(180,120), size=(50,-1))
        wx.Button(listcolumn_panel, 51, '<--', pos=(180,170), size=(50,-1))
        wx.StaticText(listcolumn_panel, -1, _("Active columns:"), pos=(255,40))
        self.listcolumn_active = wx.ListBox(listcolumn_panel, -1, pos=(250,60), size=(130,200), style=wx.LB_SINGLE)
        wx.Button(listcolumn_panel, 52, _("Up"), pos=(395,120), size=(50,-1))
        wx.Button(listcolumn_panel, 53, _("Down"), pos=(395,170), size=(50,-1))
        # Add panels to main sizer
        listview_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        listview_panel_sizer.Add(listcolumn_panel, 0)
        listview_panel.SetSizer(listview_panel_sizer)

        # Populate panel for alert list view column setup
        # Alert list view column config
        alertlistcolumn_panel = wx.Panel(alertlistview_panel, -1)
        wx.StaticBox(alertlistcolumn_panel, -1, _(" Choose active columns in alert list view "), pos=(10,5), size=(450,280))
        wx.StaticText(alertlistcolumn_panel, -1, _("Not active columns:"), pos=(35,40))
        self.alertlistcolumn_notactive = wx.ListBox(alertlistcolumn_panel, -1, pos=(30,60), size=(130,200), style=wx.LB_SINGLE|wx.LB_SORT)
        wx.Button(alertlistcolumn_panel, 60, '-->', pos=(180,120), size=(50,-1))
        wx.Button(alertlistcolumn_panel, 61, '<--', pos=(180,170), size=(50,-1))
        wx.StaticText(alertlistcolumn_panel, -1, _("Active columns:"), pos=(255,40))
        self.alertlistcolumn_active = wx.ListBox(alertlistcolumn_panel, -1, pos=(250,60), size=(130,200), style=wx.LB_SINGLE)
        wx.Button(alertlistcolumn_panel, 62, _("Up"), pos=(395,120), size=(50,-1))
        wx.Button(alertlistcolumn_panel, 63, _("Down"), pos=(395,170), size=(50,-1))
        # Add panels to main sizer
        alertlistview_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        alertlistview_panel_sizer.Add(alertlistcolumn_panel, 0)
        alertlistview_panel.SetSizer(alertlistview_panel_sizer)

        # Dialog buttons
        but1 = wx.Button(self,1,_("&Save"))
        but2 = wx.Button(self,2,_("&Apply"))
        but3 = wx.Button(self,3,_("&Close"))

        # Sizer and notebook setup
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        notebook.AddPage(common_panel, _("Common"))
        notebook.AddPage(serial_panel, _("Serial ports"))
        notebook.AddPage(network_panel, _("Network"))
        notebook.AddPage(logging_panel, _("Logging"))
        notebook.AddPage(alert_panel, _("Alerts"))
        notebook.AddPage(listview_panel, _("List view"))
        notebook.AddPage(alertlistview_panel, _("Alert view"))
        sizer.Add(notebook, 1, wx.EXPAND, 0)
        sizer.AddSpacer((0,10))
        sizer.Add(sizer2, flag=wx.ALIGN_RIGHT)
        sizer2.Add(but1, 0)
        sizer2.AddSpacer((10,0))
        sizer2.Add(but2, 0)
        sizer2.AddSpacer((50,0))
        sizer2.Add(but3, 0)
        self.SetSizerAndFit(sizer)

        # Events
        self.Bind(wx.EVT_BUTTON, self.OnSave, id=1)
        self.Bind(wx.EVT_BUTTON, self.OnApply, id=2)
        self.Bind(wx.EVT_BUTTON, self.OnAbort, id=3)
        self.Bind(wx.EVT_BUTTON, self.OnColumnChange, id=50)
        self.Bind(wx.EVT_BUTTON, self.OnColumnChange, id=51)
        self.Bind(wx.EVT_BUTTON, self.OnColumnChange, id=52)
        self.Bind(wx.EVT_BUTTON, self.OnColumnChange, id=53)
        self.Bind(wx.EVT_BUTTON, self.OnColumnChange, id=60)
        self.Bind(wx.EVT_BUTTON, self.OnColumnChange, id=61)
        self.Bind(wx.EVT_BUTTON, self.OnColumnChange, id=62)
        self.Bind(wx.EVT_BUTTON, self.OnColumnChange, id=63)
        self.Bind(wx.EVT_CLOSE, self.OnAbort)

        # Get values and update controls
        self.GetConfig()

    def GetConfig(self):
        # Get values from ConfigObj and set corresponding values in the controls
        # Settings for serial port A
        self.porta_serialon.SetValue(config['serial_a'].as_bool('serial_on'))
        self.porta_port.SetValue(config['serial_a']['port'])
        self.porta_speed.SetValue(config['serial_a']['baudrate'])
        self.porta_xonxoff.SetValue(config['serial_a'].as_bool('xonxoff'))
        self.porta_rtscts.SetValue(config['serial_a'].as_bool('rtscts'))
        # Settings for serial port B
        self.portb_serialon.SetValue(config['serial_b'].as_bool('serial_on'))
        self.portb_port.SetValue(config['serial_b']['port'])
        self.portb_speed.SetValue(config['serial_b']['baudrate'])
        self.portb_xonxoff.SetValue(config['serial_b'].as_bool('xonxoff'))
        self.portb_rtscts.SetValue(config['serial_b'].as_bool('rtscts'))
        # Settings for serial port C
        self.portc_serialon.SetValue(config['serial_c'].as_bool('serial_on'))
        self.portc_port.SetValue(config['serial_c']['port'])
        self.portc_speed.SetValue(config['serial_c']['baudrate'])
        self.portc_xonxoff.SetValue(config['serial_c'].as_bool('xonxoff'))
        self.portc_rtscts.SetValue(config['serial_c'].as_bool('rtscts'))
        # Common list settings
        self.commonlist_greytime.SetValue(config['common'].as_int('listmakegreytime'))
        self.commonlist_deletetime.SetValue(config['common'].as_int('deleteitemtime'))
        self.commonlist_refreshtime.SetValue(config['common'].as_int('refreshlisttimer'))
        # Manual position settings
        self.manualpos_overridetoggle.SetValue(config['position'].as_bool('override_on'))
        # Take bits out of a string like '67;23.19;N' and set values
        self.manualpos_latdeg.SetValue(int(config['position']['latitude'].split(';')[0]))
        self.manualpos_latmin.SetValue(int(config['position']['latitude'].split(';')[1].split('.')[0]))
        self.manualpos_latdecmin.SetValue(int(config['position']['latitude'].split(';')[1].split('.')[1]))
        self.manualpos_latquad.SetValue(config['position']['latitude'].split(';')[2])
        self.manualpos_longdeg.SetValue(int(config['position']['longitude'].split(';')[0]))
        self.manualpos_longmin.SetValue(int(config['position']['longitude'].split(';')[1].split('.')[0]))
        self.manualpos_longdecmin.SetValue(int(config['position']['longitude'].split(';')[1].split('.')[1]))
        self.manualpos_longquad.SetValue(config['position']['longitude'].split(';')[2])
        # Log settings
        self.filelog_logtoggle.SetValue(config['logging'].as_bool('logging_on'))
        self.filelog_logtime.SetValue(config['logging'].as_int('logtime'))
        self.filelog_logfile.SetValue(config['logging']['logfile'])
        # IDDB log settings
        self.iddblog_logtoggle.SetValue(config['iddb_logging'].as_bool('logging_on'))
        self.iddblog_logtime.SetValue(config['iddb_logging'].as_int('logtime'))
        self.iddblog_logfile.SetValue(config['iddb_logging']['logfile'])
        # Alert settings
        self.alertfile_toggle.SetValue(config['alert'].as_bool('alertfile_on'))
        self.alertfile_file.SetValue(config['alert']['alertfile'])
        self.remarkfile_toggle.SetValue(config['alert'].as_bool('remarkfile_on'))
        self.remarkfile_file.SetValue(config['alert']['remarkfile'])
        self.alertsoundfile_toggle.SetValue(config['alert'].as_bool('alertsound_on'))
        self.alertsoundfile_file.SetValue(config['alert']['alertsoundfile'])
        # Alert view column settings
        # Extract as list from comma separated list from dict
        self.listcolumns_as_list = config['common']['listcolumns'].replace(' ','').split(',')
        self.alertlistcolumns_as_list = config['common']['alertlistcolumns'].replace(' ', '').split(',')
        self.UpdateListColumns()
        self.UpdateAlertListColumns()
        # Network settings
        self.netrec_clienton.SetValue(config['network'].as_bool('client_on'))
        self.netrec_clientaddress.SetValue(config['network']['client_address'])
        self.netrec_clientport.SetValue(config['network'].as_int('client_port'))
        self.netsend_serveron.SetValue(config['network'].as_bool('server_on'))
        self.netsend_serveraddress.SetValue(config['network']['server_address'])
        self.netsend_serverport.SetValue(config['network'].as_int('server_port'))

    def UpdateListColumns(self):
        # Take all possible columns from columnsetup
        allcolumns = set(columnsetup.keys())
        # Create a list of differences between all possible columns and the active columns
        possible = list(allcolumns.difference(self.listcolumns_as_list))
        # Update list boxes
        self.listcolumn_active.Set(self.listcolumns_as_list)
        self.listcolumn_notactive.Set(possible)

    def UpdateAlertListColumns(self):
        # Take all possible columns from columnsetup
        allcolumns = set(columnsetup.keys())
        # Create a list of differences between all possible columns and the active columns
        possible = list(allcolumns.difference(self.alertlistcolumns_as_list))
        # Update list boxes
        self.alertlistcolumn_active.Set(self.alertlistcolumns_as_list)
        self.alertlistcolumn_notactive.Set(possible)

    def OnColumnChange(self, event):
        # Map objects depending on pressed button
        if wx.Event.GetId(event) >= 50 and wx.Event.GetId(event) < 60:
            listcolumn_list = self.listcolumns_as_list
            notactive = self.listcolumn_notactive
            selection_notactive = notactive.GetStringSelection()
            active = self.listcolumn_active
            selection_active = active.GetStringSelection()
        if wx.Event.GetId(event) >= 60 and wx.Event.GetId(event) < 70:
            listcolumn_list = self.alertlistcolumns_as_list
            notactive = self.alertlistcolumn_notactive
            selection_notactive = notactive.GetStringSelection()
            active = self.alertlistcolumn_active
            selection_active = active.GetStringSelection()
        # Move a column from non-active to active listbox
        if (wx.Event.GetId(event) == 50 or wx.Event.GetId(event) == 60) and len(selection_notactive) > 0:
            listcolumn_list.append(selection_notactive)
        # Move a column from active to non-active listbox
        elif (wx.Event.GetId(event) == 51 or wx.Event.GetId(event) == 61) and len(selection_active) > 0:
            listcolumn_list.remove(selection_active)
        # Move a column upwards in the active listbox
        elif (wx.Event.GetId(event) == 52 or wx.Event.GetId(event) == 62) and len(selection_active) > 0:
            # Get index number in listbox
            original_number = listcolumn_list.index(selection_active)
            # Check that column not is first in listbox
            if original_number > 0:
                # Remove the column
                listcolumn_list.remove(selection_active)
                # Insert the column at the previous position - 1
                listcolumn_list.insert((original_number-1), selection_active)
        # Move a column downwards in the active listbox
        elif (wx.Event.GetId(event) == 53 or wx.Event.GetId(event) == 63) and len(selection_active) > 0:
            # Get index number in listbox
            original_number = listcolumn_list.index(selection_active)
            # Remove the column
            listcolumn_list.remove(selection_active)
            # Insert the column at the previous position + 1
            listcolumn_list.insert((original_number+1), selection_active)
        # Update all columns to reflect eventual changes
        self.UpdateListColumns()
        self.UpdateAlertListColumns()
        # Make sure a moved item in the acive listbox stays selected
        active.SetStringSelection(selection_active)

    def OnLogFileDialog(self, event):
        try: self.filelog_logfile.SetValue(self.FileDialog(_("Choose log file"), _("Log file (*.log)|*.log|All files (*)|*")))
        except: return

    def OnIDDBFileDialog(self, event):
        try: self.iddblog_logfile.SetValue(self.FileDialog(_("Choose IDDB file)"), _("ID database file (*.idb)|*.idb|All files (*)|*")))
        except: return

    def OnAlertFileDialog(self, event):
        try: self.alertfile_file.SetValue(self.FileDialog(_("Choose alert file"), _("Alert file (*.alt)|*.alt|All files (*)|*")))
        except: return

    def OnRemarkFileDialog(self, event):
        try: self.remarkfile_file.SetValue(self.FileDialog(_("Choose remark file"), _("Remark file (*.key)|*.key|All files (*)|*")))
        except: return

    def OnAlertSoundFileDialog(self, event):
        try: self.alertsoundfile_file.SetValue(self.FileDialog(_("Choose sound alert file"), _("Wave file (*.wav)|*.wav|All files (*)|*")))
        except: return

    def FileDialog(self, label, wc):
        # Create a file dialog
        open_dlg = wx.FileDialog(self, label, wildcard=wc)
        # If user pressed open, update text control
        if open_dlg.ShowModal() == wx.ID_OK:
            return(str(open_dlg.GetPath()))

    def UpdateConfig(self):
        # Update the config dictionary with data from the window
        config['serial_a']['serial_on'] = self.porta_serialon.GetValue()
        config['serial_a']['port'] = self.porta_port.GetValue()
        config['serial_a']['baudrate'] = self.porta_speed.GetValue()
        config['serial_a']['xonxoff'] = self.porta_xonxoff.GetValue()
        config['serial_a']['rtscts'] = self.porta_rtscts.GetValue()
        config['serial_b']['serial_on'] = self.portb_serialon.GetValue()
        config['serial_b']['port'] = self.portb_port.GetValue()
        config['serial_b']['baudrate'] = self.portb_speed.GetValue()
        config['serial_b']['xonxoff'] = self.portb_xonxoff.GetValue()
        config['serial_b']['rtscts'] = self.portb_rtscts.GetValue()
        config['serial_c']['serial_on'] = self.portc_serialon.GetValue()
        config['serial_c']['port'] = self.portc_port.GetValue()
        config['serial_c']['baudrate'] = self.portc_speed.GetValue()
        config['serial_c']['xonxoff'] = self.portc_xonxoff.GetValue()
        config['serial_c']['rtscts'] = self.portc_rtscts.GetValue()
        config['common']['listmakegreytime'] =  self.commonlist_greytime.GetValue()
        config['common']['deleteitemtime'] =  self.commonlist_deletetime.GetValue()
        config['common']['refreshlisttimer'] = self.commonlist_refreshtime.GetValue()
        config['position']['override_on'] = self.manualpos_overridetoggle.GetValue()
        latitude = str(self.manualpos_latdeg.GetValue()).zfill(2) + ";" + str(self.manualpos_latmin.GetValue()).zfill(2) + "." + str(self.manualpos_latdecmin.GetValue()).zfill(2) + ";" + self.manualpos_latquad.GetValue()
        longitude = str(self.manualpos_longdeg.GetValue()).zfill(3) + ";" + str(self.manualpos_longmin.GetValue()).zfill(2) + "." + str(self.manualpos_longdecmin.GetValue()).zfill(2) + ";" + self.manualpos_longquad.GetValue()
        config['position']['latitude'] = str(latitude)
        config['position']['longitude'] = str(longitude)
        config['common']['listcolumns'] = ', '.join(self.listcolumns_as_list)
        config['common']['alertlistcolumns'] = ', '.join(self.alertlistcolumns_as_list)
        config['logging']['logging_on'] = self.filelog_logtoggle.GetValue()
        config['logging']['logtime'] = self.filelog_logtime.GetValue()
        config['logging']['logfile'] = self.filelog_logfile.GetValue()
        config['iddb_logging']['logging_on'] = self.iddblog_logtoggle.GetValue()
        config['iddb_logging']['logtime'] = self.iddblog_logtime.GetValue()
        config['iddb_logging']['logfile'] = self.iddblog_logfile.GetValue()
        config['alert']['alertfile_on'] = self.alertfile_toggle.GetValue()
        config['alert']['alertfile'] = self.alertfile_file.GetValue()
        config['alert']['remarkfile_on'] = self.remarkfile_toggle.GetValue()
        config['alert']['remarkfile'] = self.remarkfile_file.GetValue()
        config['alert']['alertsound_on'] = self.alertsoundfile_toggle.GetValue()
        config['alert']['alertsoundfile'] = self.alertsoundfile_file.GetValue()
        config['network']['client_on'] = self.netrec_clienton.GetValue()
        config['network']['client_address'] = self.netrec_clientaddress.GetValue()
        config['network']['client_port'] = self.netrec_clientport.GetValue()
        config['network']['server_on'] = self.netsend_serveron.GetValue()
        config['network']['server_address'] = self.netsend_serveraddress.GetValue()
        config['network']['server_port'] = self.netsend_serverport.GetValue()

    def OnSave(self, event):
        self.UpdateConfig()
        config.filename = configfile
        config.write()
        dlg = wx.MessageDialog(self, _("Your settings have been saved, but the program can only make use of some changed settings when running.\n\nPlease restart the program to be able to use all the updated settings."), 'Please restart', wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def OnApply(self, event):
        self.UpdateConfig()
        dlg = wx.MessageDialog(self, _("The program can only make use of some changed settings when running.\n\nPlease save your changes and restart the program to be able to use all the updated settings."), 'WARNING', wx.OK | wx.ICON_WARNING)
        dlg.ShowModal()
        dlg.Destroy()

    def OnAbort(self, event):
        self.Destroy()


class RawDataWindow(wx.Dialog):
    def __init__(self, parent, id):
        wx.Dialog.__init__(self, parent, id, title=_("Raw data"))#, size=(618,395))
        panel = wx.Panel(self, -1)
        wx.StaticBox(panel,-1,_(" Incoming raw data "),pos=(3,5),size=(915,390))
        # Create the textbox
        self.textbox = wx.TextCtrl(panel,-1,pos=(15,25),size=(895,355),style=(wx.TE_MULTILINE | wx.TE_READONLY))
        # Buttons
        self.pausebutton = wx.ToggleButton(self,1,_("&Pause"), size=(-1,35))
        self.closebutton = wx.Button(self,2,_("&Close"), size=(-1,35))

        # Sizers
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(panel, 1, wx.EXPAND, 0)
        sizer.AddSpacer((0,10))
        sizer.Add(sizer2, flag=wx.ALIGN_RIGHT)
        sizer2.Add(self.pausebutton, 0)
        sizer2.AddSpacer((150,0))
        sizer2.Add(self.closebutton, 0)
        self.SetSizerAndFit(sizer)

        # Events
        self.Bind(wx.EVT_TOGGLEBUTTON, self.OnPause, id=1)
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=2)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Timer for updating the textbox
        self.timer = wx.Timer(self, -1)
        wx.EVT_TIMER(self, -1, self.Update)
        self.OnStart(self)

    def Update(self, event):
        updatetext = ''
        # Loop if objects in queue
        while len(rawdata) > 0:
            # Pop from queue and add string to updatetext (make sure it's ascii)
            line = rawdata.popleft()
            sentence = unicode(line[3], 'ascii', 'replace').rstrip('\r\n')
            updatetext += sentence + '  => message ' + str(line[1]) + ', mmsi ' + str(line[2]) + ', source ' + str(line[0]) + '\n'
        # Write updatetext from the top of the box
        self.textbox.SetInsertionPoint(0)
        self.textbox.WriteText(updatetext)
        # Get total number of characters in box
        numberofchars = self.textbox.GetLastPosition()
        # Remove all characters over the limit (at the bottom)
        if numberofchars > 20000:
            self.textbox.Remove(20000, numberofchars)
            self.textbox.ShowPosition(0)

    def OnStart(self, event):
        # Make an update before starting timer
        self.Update(self)
        self.textbox.ShowPosition(0)
        # Start timer
        self.timer.Start(1000)

    def OnPause(self, event):
        # If button is toggled, stop timer, if not start timer
        if self.pausebutton.GetValue() is True:
            self.timer.Stop()
        elif self.pausebutton.GetValue() is False:
            self.OnStart(self)

    def OnClose(self, event):
        self.Destroy()


class AdvancedAlertWindow(wx.Dialog):
    # Copy alerts from alertlist
    queryitems = alertlist[:]

    def __init__(self, parent, id):
        # Create a dialog with two static boxes
        self.dlg = wx.Dialog.__init__(self, parent, id, title=_("Advanced alert editor"), size=(590,550))
        wx.StaticBox(self,-1,_(" Current alerts "),pos=(3,5),size=(583,200))
        wx.StaticBox(self,-1,_(" New alert "),pos=(3,210),size=(583,265))

        # Show a list with current alerts
        # panel1 - main panel
        panel1 = wx.Panel(self, -1, pos=(15,25), size=(560,170))
        # panel2 - sub panel containing the list ctrl
        panel2 = wx.Panel(panel1, -1, pos=(100,0), size=(455,165))
        self.querylist = wx.ListCtrl(panel2, -1, style=wx.LC_REPORT)
        # Create a BoxSizer for the scroll ctrl
        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(self.querylist, 1, wx.EXPAND)
        panel2.SetSizer(box)
        panel2.Layout()
        # Add columns to list
        self.querylist.InsertColumn(0, _("Sound alert"))
        self.querylist.SetColumnWidth(0, 70)
        self.querylist.InsertColumn(1, _("SQL string"))
        self.querylist.SetColumnWidth(1, 370)
        # Add buttons
        wx.Button(panel1,01,_("&Remove"),pos=(0,10))
        wx.Button(panel1,02,_("C&lear list"),pos=(0,50))
        wx.Button(panel1,03,_("&Edit..."),pos=(0,90))
        wx.Button(panel1,04,_("&Import..."),pos=(0,130))

        panel3 = wx.Panel(self, -1, pos=(15,230), size=(560,235))
        # Short explanation of how to add alert queries
        wx.StaticText(panel3, -1,
                _("New alerts are created as SQL queries by combining the three fields below.\n"
                "The argument between each field is AND."),
                pos=(0,0), size=(570,50))
        # Create panels with a total of three possible SQL query parts
        wx.StaticText(panel3, -1, 'I:', pos=(0,61))
        self.searcharg1 = self.NewSearchPanel(panel3, -1, pos=(45,35))
        wx.StaticText(panel3, -1, 'II: AND', pos=(0,116))
        self.searcharg2 = self.NewSearchPanel(panel3, -1, pos=(45,90))
        wx.StaticText(panel3, -1, 'III: AND', pos=(0,171))
        self.searcharg3 = self.NewSearchPanel(panel3, -1, pos=(45,145))
        # Checkbox for alert on/off
        self.searchalertbox = wx.CheckBox(panel3, -1, _("A&ctivate sound alert"), pos=(60, 207))
        # Button to add a query to list
        wx.Button(panel3,05,_("A&dd to list"),pos=(405,200))

        # Window buttons
        wx.Button(self,10,_("O&pen..."),pos=(3,490))
        wx.Button(self,11,_("&Save..."),pos=(103,490))
        wx.Button(self,12,_("&Close"),pos=(300,490))
        wx.Button(self,13,_("&Apply"),pos=(400,490))
        wx.Button(self,14,_("&OK"),pos=(500,490))

        # Events
        self.Bind(wx.EVT_BUTTON, self.OnOpen, id=10)
        self.Bind(wx.EVT_BUTTON, self.OnSave, id=11)
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=12)
        self.Bind(wx.EVT_BUTTON, self.OnApply, id=13)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=14)
        self.Bind(wx.EVT_BUTTON, self.OnRemove, id=01)
        self.Bind(wx.EVT_BUTTON, self.OnRemoveAll, id=02)
        self.Bind(wx.EVT_BUTTON, self.OnEdit, id=03)
        self.Bind(wx.EVT_BUTTON, self.OnImport, id=04)
        self.Bind(wx.EVT_BUTTON, self.OnAdd, id=05)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnEdit, self.querylist)
        self.Bind(wx.EVT_KEY_UP, self.OnKey)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Update the temporary list from alertlist
        self.queryitems = alertlist[:]
        # Update list ctrl
        self.UpdateValues()

    def OnKey(self, event):
        # If enter is pressed, add to list
        if event.GetKeyCode() == 13 or event.GetKeyCode() == 372:
            self.OnAdd(event)

    class NewSearchPanel(wx.Panel):
        def __init__(self, parent, id, pos):
            # Create panel
            wx.Panel.__init__(self, parent, id, pos=pos, size=(465,50))
            # Define a small font
            smallfont = wx.Font(8, wx.NORMAL, wx.NORMAL, wx.NORMAL)
            # List with SQL conditions
            sqlchoices = ['LIKE', 'NOT LIKE', '=', '<', '<=', '>', '>=']
            # Create a dict with key as in the combobox and the value as column name for the SQL-query
            self.fieldmap = {_("MMSI number"): 'mmsi',
                    _("Nation (2 chars)"): 'mid',
                    _("IMO number"): 'imo',
                    _("Name"): 'name',
                    _("Type (number)"): 'type',
                    _("Callsign"): 'callsign',
                    _("GEOREF"): 'georef',
                    _("Speed"): 'sog',
                    _("Course"): 'cog',
                    _("Destination"): 'destination',
                    _("ETA (MMDDhhmm)"): 'eta',
                    _("Length"): 'length',
                    _("Width"): 'width',
                    _("Draught"): 'draught',
                    _("Rate of turn"): 'rateofturn',
                    _("Nav Status"): 'navstatus',
                    _("Bearing"): 'bearing',
                    _("Distance"): 'distance'}
            # Iterate over fieldchoices and create a sorted list of the keys
            self.fieldchoices = []
            for i in self.fieldmap.iterkeys(): self.fieldchoices.append(i)
            self.fieldchoices.sort()

            # Create a combo box for fiels choice
            self.fieldbox = wx.ComboBox(self, -1, pos=(10,20),size=(150,-1), value=_("MMSI number"), choices=self.fieldchoices, style=wx.CB_READONLY)
            fieldtext = wx.StaticText(self, -1, _("Column"), pos=(10,5))
            fieldtext.SetFont(smallfont)
            # Create combo box for SQL condition choice
            self.sqlbox = wx.ComboBox(self, -1, pos=(175,20),size=(100,-1), value='LIKE', choices=sqlchoices, style=wx.CB_READONLY)
            sqltext= wx.StaticText(self, -1, _("Condition"), pos=(175,5))
            sqltext.SetFont(smallfont)
            # Create textctrl for value input
            self.valuebox = wx.TextCtrl(self, -1, pos=(290,20),size=(170,-1))
            valuetext = wx.StaticText(self, -1, _("Value"), pos=(290,5))
            valuetext.SetFont(smallfont)

    def UpdateValues(self):
        # Update the list ctrl with values from list queryitems
        self.querylist.DeleteAllItems()
        for x in self.queryitems:
            if x[1] == 0: col0 = _("No")
            elif x[1] == 1: col0 = _("Yes")
            currentrow = self.querylist.GetItemCount()
            self.querylist.InsertStringItem(currentrow, col0)
            self.querylist.SetStringItem(currentrow, 1, x[0])
        # Clear the input boxes
        self.searcharg1.valuebox.Clear()
        self.searcharg1.valuebox.SetFocus()
        self.searcharg2.valuebox.Clear()
        self.searcharg3.valuebox.Clear()
        self.searchalertbox.SetValue(False)

    def OnAdd(self, event):
        sqlargs = self.ExtractInputData(['searcharg1', 'searcharg2', 'searcharg3'])
        # Create a query string with AND between each part
        if len(sqlargs) > 0:
            if self.searchalertbox.GetValue():
                alert = 1
            else: alert = 0
            self.queryitems.append((' AND '.join(sqlargs),alert,0))
        # Update the list ctrl and clear input
        self.UpdateValues()
        # Make sure that the added query is visible in list
        nritems = self.querylist.GetItemCount()
        self.querylist.EnsureVisible(nritems-1)

    def ExtractInputData(self, panels):
        # This function extracts input data from the names in the list panels
        sqlargs = []
        # Add a string to sqlargs for each field that contains input
        for i in panels:
            # Create full strings for extracting data from the different fields and boxes
            fieldbox = "self." + i + ".fieldbox.GetValue()"
            fieldmap = "self." + i + ".fieldmap"
            sqlbox = "self." + i + ".sqlbox.GetValue()"
            valuebox = "self." + i + ".valuebox.GetValue()"
            # If a value has been entered into the valuebox, process
            if len(eval(valuebox)) > 0:
                sqlargs.append(eval(fieldmap)[eval(fieldbox).encode('utf_8')]
                + " " + eval(sqlbox) + " '" + eval(valuebox) + "'")
        return sqlargs

    def OnEdit(self, event):
        # Edit a serch query
        # If only one item is selected, edit
        if self.querylist.GetSelectedItemCount() == 1:
            # Step through items in list to find the selected one
            item = self.querylist.GetNextItem(-1, -1, wx.LIST_STATE_SELECTED)
            # Retreive the string itself from queryitems
            querystring = str(self.queryitems[item][0])
            # Create a dialog with a textctrl, a checkbox and two buttons
            dlg = wx.Dialog(self, -1, _("Edit alert"), size=(400,145))
            textbox = wx.TextCtrl(dlg, -1, querystring, pos=(10,10), size=(380,70), style=wx.TE_MULTILINE)
            alertbox = wx.CheckBox(dlg, -1, _("A&ctivate sound alert"), pos=(30, 95))
            buttonsizer = dlg.CreateStdDialogButtonSizer(wx.CANCEL|wx.OK)
            buttonsizer.SetDimension(210, 85, 180, 40)
            # Make the checkbox checked if the value is set in queryitems
            if self.queryitems[item][1] == 1: alertbox.SetValue(True)
            # If user press OK, update the queryitems list and update the AdvancedAlertWindow
            if dlg.ShowModal() == wx.ID_OK:
                if alertbox.GetValue():
                    alertstate = 1
                else:
                    alertstate = 0
                self.queryitems[item] = (textbox.GetValue(), alertstate, 0)
                self.UpdateValues()
        # If more than one item selected, show error
        elif self.querylist.GetSelectedItemCount() > 1:
            dlg = wx.MessageDialog(self, _("You can only edit one query at a time!"), _("Error"), wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()

    def OnRemove(self, event):
        # Remove the object that is selected in list
        # Step backwards in list and check if each object is selected
        for x in range(self.querylist.GetItemCount()-1, -1, -1):
            if self.querylist.GetItemState(x, wx.LIST_STATE_SELECTED):
                del self.queryitems[x]
        # Clear & update
        self.UpdateValues()
        return

    def OnRemoveAll(self, event):
        # Remove all objects
        del self.queryitems[:]
        # Update the list ctrl
        self.UpdateValues()
        return

    def OnImport(self, event):
        dlg = self.Import(self, -1)
        dlg.ShowModal()
        # Update
        self.UpdateValues()

    class Import(wx.Dialog):
        def __init__(self, parent, id):
            wx.Dialog.__init__(self, parent, id, title=_("Import"), size=(503,350))
            # Make a box for import from clipboard
            wx.StaticBox(self,-1,_(" Import from clipboard"),pos=(3,5),size=(496,290))
            # Explain how the import is done
            wx.StaticText(self, -1,
            _("The data from the clipboard is expected to be in column format.\n"
            "Additional arguments are written in the upper boxes while the choice\n"
            "of column for imported data is in the bottom. Choose and press Paste.\n"
            "Sound alert activation is for all the imported objects."),
            pos=(10,25), size=(470,70))

            # Map the parents variable queryitems to self.queryitems
            self.queryitems = parent.queryitems
            self.parent = parent

            # Buttons and events
            wx.Button(self,01,_("&Paste"),pos=(200,217))
            wx.Button(self,02,_("&Close"),pos=(400,310))
            self.Bind(wx.EVT_BUTTON, self.OnDoPaste, id=01)
            self.Bind(wx.EVT_BUTTON, self.OnClose, id=02)
            self.Bind(wx.EVT_CLOSE, self.OnClose)

            # Create a combobox and map the resulting values
            wx.StaticBox(self,-1,_(" Fields for the data import "),pos=(13,190),size=(475,90))
            self.fieldbox = wx.ComboBox(self, -1, pos=(25,220),size=(150,-1), value=_("MMSI number"), choices=(_("MMSI number"), _("IMO number"), _("Name"), _("Callsign")), style=wx.CB_READONLY)
            self.fieldmap = {_("MMSI number"): 'mmsi', _("IMO number"): 'imo', _("Name"): 'name', _("Callsign"): 'callsign'}
            # Create a checkbox for alert on/off
            self.alertbox = wx.CheckBox(self, -1, _("A&ctivate sound alert"), (25, 255))

            # Create panels for additional search arguments
            wx.StaticBox(self,-1,_(" Additional arguments "),pos=(13,100),size=(475,80))
            AdvancedAlertWindow.importsearcharg = parent.NewSearchPanel(self, -1, pos=(15,120))

        def OnDoPaste(self, event):
            queries = []
            clipboard = wx.Clipboard()
            # Try to open clipboard and copy text objects
            if clipboard.Open():
                clipboarddata = wx.TextDataObject()
                clipboard.GetData(clipboarddata)
                data = clipboarddata.GetText()
                clipboard.Close()
            # For each line of input from clipboard, create a query and append to list queries
            for i in data.splitlines():
                # Check if value in the additional querybox and add to the full query
                try: addquery = " AND " + self.parent.ExtractInputData(['importsearcharg'])[0]
                except: addquery = ''
                # Check if the line from clipboard contains data, if so, make the query
                if len(i) > 0:
                    queries.append(self.fieldmap[self.fieldbox.GetValue().encode('utf_8')] + " LIKE '" + i + "'" + addquery)
            # Create a nicely formatted question to approve the imported data
            formattedqueries = _("Do you approve of importing the following queries?\n\n")
            for i in queries:
                formattedqueries += str(i) + '\n'
            # Create a dialog with a yes- and a no-button
            dlg = wx.MessageDialog(self, formattedqueries, _("Approve import"), wx.YES_NO|wx.ICON_QUESTION)
            # If user answers 'yes' use the imported data and destroy dialogs
            if dlg.ShowModal() == wx.ID_YES:
                fullqueries = []
                # For each query, add alert on/off to list
                for i in queries:
                    # If alert is checked
                    if self.alertbox.GetValue():
                        fullqueries.append((i,1,0))
                    # If not
                    else:
                        fullqueries.append((i,0,0))
                # Extend the list containing all the queries
                self.queryitems.extend(fullqueries)
                # Destroy both dialogs
                dlg.Destroy()
                self.Destroy()
            # If user press 'no' destroy only the approve-dialog
            dlg.Destroy()

        def OnClose(self, event):
            self.Destroy()

    def OnApply(self, event):
        # Copy list to alertlist
        global alertlist
        alertlist = self.queryitems[:]
        # Create a joined string of list
        global alertstring
        if len(alertlist) > 0:
            alertstring = '(' + ') OR ('.join(zip(*alertlist)[0]) + ')'
        else: alertstring = '()'
        # Create a joined string of sound alert list
        querysoundlist = []
        global alertstringsound
        # Loop over alertlist and append those with sound alert to alertsoundlist
        for i in alertlist:
            if i[1] == 1:
               querysoundlist.append(i)
        # If querysoundlist is not empty, make a query string of it
        if len(querysoundlist) > 0:
            alertstringsound = '(' + ') OR ('.join(zip(*querysoundlist)[0]) + ')'
        else: alertstringsound = '()'

    def OnOK(self, event):
        # If user pressed OK, run apply function and destroy dialog
        self.OnApply('')
        self.Destroy()

    def OnOpen(self, event):
        path = ''
        wcd = _("Alert files (*.alt)|*.alt|All files (*)|*")
        dir = os.getcwd()
        open_dlg = wx.FileDialog(self, message=_("Choose a file"), defaultDir=dir, defaultFile='', wildcard=wcd, style=wx.OPEN)
        if open_dlg.ShowModal() == wx.ID_OK:
            path = open_dlg.GetPath()
        if len(path) > 0:
            try:
                file = open(path, 'rb')
                data = pickle.load(file)
                if data[0] == 'Alertdata':
                    del data[0]
                    self.queryitems.extend(data[:])
                file.close()
                self.UpdateValues()
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Could not open file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except KeyError, error:
                dlg = wx.MessageDialog(self, _("File contains illegal values") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except UnicodeDecodeError, error:
                dlg = wx.MessageDialog(self, _("Could not open file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                open_dlg.Destroy()
            except:
                dlg = wx.MessageDialog(self, _("Unknown error") + "\n" + str(sys.exc_info()[0]), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()

    def OnSave(self, event):
        self.OnApply('')
        path = ''
        wcd = _("Alert files (*.alt)|*.alt|All files (*)|*")
        dir = os.getcwd()
        open_dlg = wx.FileDialog(self, message=_("Choose a file"), defaultDir=dir, defaultFile='alert.alt', wildcard=wcd, style=wx.SAVE)
        if open_dlg.ShowModal() == wx.ID_OK:
            path = open_dlg.GetPath()
        if len(path) > 0:
            try:
                output = open(path, 'wb')
                outdata = self.queryitems[:]
                outdata.insert(0, 'Alertdata')
                pickle.dump(outdata,output)
                output.close()
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Could not save file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except UnicodeDecodeError, error:
                dlg = wx.MessageDialog(self, _("Could not save file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                open_dlg.Destroy()

    def OnClose(self, event):
        self.Destroy()


class GUI(wx.App):
    def OnInit(self):
        frame = MainWindow(None, -1, 'AIS Logger')
        frame.Show(True)
        return True


class SerialThread:
    queue = Queue.Queue()

    def reader(self, port, baudrate, rtscts, xonxoff, repr_mode, portname):
        # Define instance variables
        maint = MainThread()
        serialt = SerialThread()
        self.stats = {"received": 0, "parsed": 0}
        # Set queueitem and temp to empty, and seq_temp to "illegal" value
        queueitem = ''
        temp = ''
        seq_temp = 10
        nbr_several_parsed = 0
        # Define serial port connection
        s = serial.Serial(port, baudrate, rtscts=rtscts, xonxoff=xonxoff)
        while True:
            try:
                queueitem = self.queue.get_nowait()
            except: pass
            if queueitem == 'stop':
                s.close()
                break

            try:
                indata = s.readline()
                self.stats["received"] += 1
                if repr_mode:
                    indata = repr(indata)[1:-1]
            except: continue

            # Add the indata line to a list and pop when over 500 items in list
            rawdata.append(indata)
            while len(rawdata) > 500:
                rawdata.popleft()

            # Put in NetworkFeeder's queue
            networkdata.append(indata)
            while len(networkdata) > 500:
                networkdata.popleft()

            # Check if message is split on several lines
            lineinfo = indata.split(',')
            if lineinfo[0] == '!AIVDM':
                nbr_of_lines = int(lineinfo[1])
                try:
                    line_nbr = int(lineinfo[2])
                    line_seq_id = int(lineinfo[3])
                except: pass
                # If message is split, check that they belong together
                if nbr_of_lines > 1:
                    # If first message, set seq_temp to the sequential message ID
                    if line_nbr == 1:
                        temp = ''
                        seq_temp = line_seq_id
                    # If not first message, check that the seq ID matches that in seq_temp
                    # If not true, reset variables and continue
                    elif line_seq_id != seq_temp:
                        temp = ''
                        seq_temp = 10
                        continue
                    # Add data to variable temp
                    temp += indata
                    # If the final message has been received, join messages and decode
                    if len(temp.splitlines()) == nbr_of_lines:
                        indata = decode.jointelegrams(temp)
                        temp = ''
                        seq_temp = 10
                        nbr_several_parsed = nbr_of_lines
                    else:
                        continue

            # Set the telegramparser result in dict parser and queue it
            try:
                parser = dict(decode.telegramparser(indata))
                if len(parser) > 0:
                    # Set source in parser as serial with portname and real port
                    parser['source'] = "Serial port " + portname + " (" + port + ")"
                    maint.put(parser)
                    # Add to stats variable. If the message was more than one
                    # line, add that number to stats.
                    if nbr_several_parsed > 0:
                        self.stats["parsed"] += nbr_several_parsed
                        nbr_several_parsed = 0
                    else:
                        self.stats["parsed"] += 1
            except: continue

    def ReturnStats(self):
        return self.stats

    def put(self, item):
        self.queue.put(item)

    def start(self, openport):
        if openport == 'serial_a':
            portconfig = config['serial_a']
            # Set internal port name to A
            portname = 'A'
        elif openport == 'serial_b':
            portconfig = config['serial_b']
            # Set internal port name to B
            portname = 'B'
        elif openport == 'serial_c':
            portconfig = config['serial_c']
            # Set internal port name to C
            portname = 'C'
        port = portconfig['port']
        baudrate = portconfig.as_int('baudrate')
        rtscts = portconfig.as_bool('rtscts')
        xonxoff = portconfig.as_bool('xonxoff')
        repr_mode = portconfig.as_bool('repr_mode')
        try:
            r = threading.Thread(target=self.reader, args=(port, baudrate, rtscts, xonxoff, repr_mode, portname))
            r.setDaemon(1)
            r.start()
            return True
        except:
            return False

    def stop(self):
        for i in range(0,10):
            self.put('stop')


class NetworkServerThread:
    comqueue = Queue.Queue()

    class NetworkClientHandler(SocketServer.BaseRequestHandler):
        def handle(self):
            message = ''
            # Define an instance collection
            self.indata = collections.deque()
            # Notify the NetworkFeeder that we have liftoff...
            NetworkServerThread().put(('started', self))
            while True:
                try:
                    # Try to pop message from the collection
                    message = self.indata.popleft()
                except IndexError:
                    # If no data in collection, sleep (prevents 100% CPU drain)
                    time.sleep(0.05)
                    continue
                except: pass
                # If someone tells us to stop, stop.
                if message == 'stop': break
                # If message length is > 1, send message to socket
                if len(message) > 1:
                    try:
                        self.request.send(str(message))
                    except:
                        break
            # Stop, please.
            NetworkServerThread().put(('stopped', self))
            self.indata.clear()
            self.request.close()


    def server(self):
        # Spawn network servers as clients request connection
        server_address = config['network']['server_address']
        server_port = config['network'].as_int('server_port')
        server = SocketServer.ThreadingTCPServer((server_address, server_port), self.NetworkClientHandler)
        server.serve_forever()

    def feeder(self):
        # This function tracks each server thread and feeds them
        # with data from networkdata
        queueitem = ''
        servers = []
        while True:
            try:
                queueitem = self.comqueue.get_nowait()
                # If a server started, add to servers
                if queueitem[0] == 'started':
                    servers.append(queueitem[1])
                # If a server stopped, remove from servers
                elif queueitem[0] == 'stopped':
                    servers.remove(queueitem[1])
            # If nothing in comqueue, pass along
            except: pass
            # If someone wants to stop us, send stop to servers
            if queueitem == 'stop':
                for server in servers:
                    for i in range(0,100):
                        server.indata.append('stop')
                break
            try:
                # Pop message from collection
                message = networkdata.popleft()
            except IndexError:
                # If no data in collection, sleep (prevents 100% CPU drain)
                time.sleep(0.05)
                continue
            except: pass
            # If message length is > 1, send message to socket
            if len(message) > 1:
                for server in servers:
                    server.indata.append(message)

    def start(self):
        try:
            r2 = threading.Thread(target=self.feeder, name='NetworkFeeder')
            r2.setDaemon(1)
            r2.start()
            r = threading.Thread(target=self.server, name='NetworkServer')
            r.setDaemon(1)
            r.start()
            return True
        except:
            return False

    def stop(self):
        for i in range(0,100):
            self.comqueue.put('stop')

    def put(self, item):
        self.comqueue.put(item)


class NetworkClientThread:
    queue = Queue.Queue()

    def client(self):
        # Define thread to send data to
        commt = CommHubThread()
        # Set empty queueitem
        queueitem = ''
        # Get config data and set empty dicts
        connection_params = config['network']['client_addresses']
        connections = {}
        remainder = {}
        # See if we only will have one connection
        if not type(connection_params) == list:
            connection_params = [connection_params]
        # Open all connections
        for c in connection_params:
            # Split and put address in params[0] and port in params[1]
            params = c.split(':')
            # Connect
            connections[c] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # A connection has 30 seconds before it times out
            connections[c].settimeout(30)
            try:
                connections[c].connect((params[0], int(params[1])))
                # Ok we succeded... Go to non-blocking mode
                connections[c].setblocking(False)
            except socket.timeout:
                # Oops, we timed out... Close and continue
                connections[c].close()
                del connections[c]
                continue

        while True:
            try:
                queueitem = self.queue.get_nowait()
            except: pass
            if queueitem == 'stop':
                for con in connections.itervalues():
                    con.close()
                break

            # Now iterate over the connetions
            for (name, con) in connections.iteritems():
                try:
                    # Try to read data from socket
                    data = str(con.recv(2048)).splitlines(True)
                except:
                    # Prevent CPU drain if nothing to do
                    time.sleep(0.05)
                    continue

                # See if we have data left since last read
                # If so, concat it with the first new data
                if name in remainder:
                    data[0] = remainder.pop(name) + data[0]

                # See if the last data has a line break in it
                # If not, pop it for use at next read
                listlength = len(data)
                if listlength > 0 and not data[listlength-1].endswith('\n'):
                    remainder[name] = data.pop(listlength-1)

                for indata in data:
                    # If indata contains raw data, pass it along
                    if indata[0] == '!' or indata[0] == '$':
                        # Put it in CommHubThread's queue
                        commt.put([name,indata])

    def put(self, item):
        self.queue.put(item)

    def start(self):
        try:
            r = threading.Thread(target=self.client)
            r.setDaemon(1)
            r.start()
            return True
        except:
            return False

    def stop(self):
        self.put('stop')


class CommHubThread:
    incoming_queue = Queue.Queue()

    def runner(self):
        # Define thread to send data to
        maint = MainThread()
        # The routing matrix consists of a dict with key 'input'
        # and value 'output list'
        routing_matrix = {}
        # The message parts dict has 'input' as key and
        # and a list of previous messages as value
        message_parts = {}
        # Set statistics dict
        self.statistics = {}
        # Empty incoming queue
        incoming_item = ''
        while True:
            # Let's try to get some data in the queue
            try:
                incoming_item = self.incoming_queue.get_nowait()
            except:
                # Prevent CPU drain if nothing to do
                time.sleep(0.05)
                continue
            if incoming_item == 'stop':
                break
            # Set some variables
            source = incoming_item[0]
            data = incoming_item[1]
            try:
                outputs = routing_matrix[source]
                # Route the raw data
                for output in outputs:
                    print "outputting to:", output
                    # Put data in output queue or something
            except:
                 routing_matrix[source] = []


            # Parse data

            # Check if message is split on several lines
            lineinfo = data.split(',')
            if lineinfo[0] == '!AIVDM':
                nbr_of_lines = int(lineinfo[1])
                try:
                    line_nbr = int(lineinfo[2])
                    line_seq_id = int(lineinfo[3])
                except: pass
                # If message is split, check that they belong together
                if nbr_of_lines > 1:
                    # Get previous parts if they exist
                    parts = message_parts.get(source)
                    if parts:
                        seq_id = parts[0]
                        total_data = parts[1]
                    else:
                        seq_id = 10
                        total_data = ''
                    # If first message, set seq_id to the sequential message ID
                    if line_nbr == 1:
                        total_data = ''
                        seq_id = line_seq_id
                    # If not first message, check that the seq ID matches seq_id
                    # If not true, reset variables and continue
                    elif line_seq_id != seq_id:
                        message_parts[source] = [10, '']
                        continue
                    # Add data to variable total_data
                    total_data += data
                    # If the final message has been received, join messages and decode
                    if len(total_data.splitlines()) == nbr_of_lines:
                        data = decode.jointelegrams(total_data)
                        message_parts[source] = [10, '']
                    else:
                        message_parts[source] = [seq_id, total_data]
                        continue

            # Set the telegramparser result in dict parser and queue it
            try:
                parser = dict(decode.telegramparser(data))
                if 'mmsi' in parser:
                    # Set source in parser
                    parser['source'] = source
                    # Send data to main thread
                    maint.put(parser)
                    # Add to stats variable
                    #self.stats[source]["parsed"] += 1
                elif 'ownlatitude' and 'ownlongitude' in parser:
                    # FIXME: See if we shold set own lat/long
                    pass

                # Send raw data to the Raw Window queue
                if 'mmsi' in parser:
                    raw_mmsi = parser['mmsi']
                else:
                    raw_mmsi = 'N/A'
                if 'message' in parser:
                    raw_message = parser['message']
                else:
                    raw_message = 'N/A'
                # Append source, message number, mmsi and data to rawdata
                raw = [source, raw_message, raw_mmsi, data]
                # Add the raw line to a list and pop when over 500 items in list
                rawdata.append(raw)
                while len(rawdata) > 500:
                    rawdata.popleft()
            except: continue

    def ReturnStats(self):
        return self.stats

    def put(self, item):
        self.incoming_queue.put(item)

    def start(self):
        try:
            r = threading.Thread(target=self.runner)
            r.setDaemon(1)
            r.start()
            return True
        except:
            return False

    def stop(self):
        self.put('stop')


class MainThread:
    # Create an incoming and an outgoing queue
    # Set a limit on how large the outgoing queue can get
    queue = Queue.Queue()
    outgoing = Queue.Queue(1000)

    def __init__(self):
        # Set an empty incoming dict
        self.incoming_packet = {}

        # Define consumers
        self.consumers = []

        # Define a dict to store the metadata hashes
        self.hashdict = {}

        # Define a dict to store own position data in
        self.ownposition = {}
        # See if we should set a fixed manual position
        if config['position'].as_bool('override_on'):
            ownlatitude = decimal.Decimal(config['position']['latitude'])
            ownlongitude = decimal.Decimal(config['position']['longitude'])
            try:
                owngeoref = georef(ownlatitude,ownlongitude)
            except:
                owngeoref = None
            self.ownposition.update({'ownlatitude': ownlatitude, 'ownlongitude': ownlongitude, 'owngeoref': owngeoref})

        # Create main database
        self.db_main = pydblite.Base('dummy')
        self.dbfields = ('mmsi', 'mid', 'imo',
                         'name', 'type', 'typename',
                         'callsign', 'latitude', 'longitude',
                         'georef', 'creationtime', 'time',
                         'sog', 'cog', 'heading',
                         'destination', 'eta', 'length',
                         'width', 'draught', 'rot',
                         'navstatus', 'posacc', 'distance',
                         'bearing', 'source', 'base_station',
                         'old', 'soundalerted')
        self.db_main.create(*self.dbfields)
        self.db_main.create_index('mmsi')

        # Create ID database
        self.db_iddb = pydblite.Base('dummy2')
        self.db_iddb.create('mmsi', 'imo', 'name', 'callsign')
        self.db_iddb.create_index('mmsi')

        # Try to load ID database
        self.loadiddb()

    def DbUpdate(self, incoming_packet):
        self.incoming_packet = incoming_packet
        incoming_mmsi = self.incoming_packet['mmsi']
        new = False

        # Fetch the current data in DB for MMSI (if exists)
        currentdata = self.db_main._mmsi[incoming_mmsi]

        # If not currently in DB, add the mmsi number, creation time and MID code
        if len(currentdata) == 0:
            # Set variable to indicate a new object
            new = True
            # Map MMSI nbr to nation from MID list
            if 'mmsi' in self.incoming_packet and str(self.incoming_packet['mmsi'])[0:3] in mid:
                mid_code = mid[str(self.incoming_packet['mmsi'])[0:3]]
            else:
                mid_code = None
            self.db_main.insert(mmsi=incoming_mmsi,mid=mid_code,creationtime=self.incoming_packet['time'])
            currentdata = self.db_main._mmsi[incoming_mmsi]

        # Get the record so that we can address it
        main_record = currentdata[0]

        # Fetch current data in IDDB
        iddb = self.db_iddb._mmsi[incoming_mmsi]

        # Can we update the IDDB (is IMO in the incoming packet?)
        if 'imo' in self.incoming_packet:
            # See if we have to insert first
            if len(iddb) == 0:
                self.db_iddb.insert(mmsi=incoming_mmsi)
                # Fetch the newly inserted entry
                iddb = self.db_iddb._mmsi[incoming_mmsi]
            # Get the record so that we can address it
            iddb_record = iddb[0]
            # Check if we have callsign or name in incoming_packet
            iddb_update = {}
            if 'callsign' in self.incoming_packet:
                iddb_update['callsign'] = self.incoming_packet['callsign']
            if 'name' in self.incoming_packet:
                iddb_update['name'] = self.incoming_packet['name']
            # Make the update
            # We know that we already have IMO, don't check for it
            self.db_iddb.update(iddb_record,imo=self.incoming_packet['imo'],**iddb_update)
            # We don't update iddb och iddb_record because there is no need, the info
            # will not be used later anyway

        # Define a dictionary to hold update data
        update_dict = {}
        # Iterate over incoming and copy matching fields to update_dict
        for key, value in self.incoming_packet.iteritems():
            if key in self.dbfields:
                # Replace any Nonetypes with string N/A
                if value == None:
                    update_dict[key] = 'N/A'
                else:
                    update_dict[key] = value

        # -- TYPENAME, GEOREF, DISTANCE, BEARING
        # Map type nbr to type name from list
        if 'type' in self.incoming_packet and self.incoming_packet['type'] > 0 and str(self.incoming_packet['type']) in typecode:
            update_dict['typename'] = typecode[str(self.incoming_packet['type'])]

        # Calculate position in GEOREF
        if 'latitude' in self.incoming_packet and 'longitude' in self.incoming_packet:
            try:
                update_dict['georef'] = georef(self.incoming_packet['latitude'],self.incoming_packet['longitude'])
            except: pass

        # Calculate bearing and distance to object
        if 'ownlatitude' in self.ownposition and 'ownlongitude' in self.ownposition and 'latitude' in self.incoming_packet and 'longitude' in self.incoming_packet:
            try:
                dist = VincentyDistance((self.ownposition['ownlatitude'],self.ownposition['ownlongitude']), (self.incoming_packet['latitude'],self.incoming_packet['longitude'])).all
                update_dict['distance'] = decimal.Decimal(str(dist['km'])).quantize(decimal.Decimal('0.1'))
                update_dict['bearing'] = decimal.Decimal(str(dist['bearing'])).quantize(decimal.Decimal('0.1'))
            except: pass

        # Check if report is from a base station or a SAR station
        if 'message' in self.incoming_packet:
            # If message type 4 (Base Station Report), set property to True
            if self.incoming_packet['message'] == 4:
                update_dict['base_station'] = True
            # Abort insertion if message type 9 (Special Position Report)
            elif self.incoming_packet['message'] == 9:
                return None

        # Update the DB with new data
        self.db_main.update(main_record,old=False,**update_dict)

        # Return a dictionary of iddb
        if len(iddb) == 0:
            iddb = {}
        elif len(iddb) > 0:
            iddb = iddb[0]

        # Return the updated object and the iddb entry
        return self.db_main[main_record['__id__']], iddb, new

    def UpdateMsg(self, object_info, iddb, new=False):
        # Define the dict we're going to send
        message = {}

        # See if we need to use data from iddb
        if object_info['imo'] == None and 'imo' in iddb:
            object_info['imo'] = str(iddb['imo']) + "'"
        if object_info['callsign'] == None and 'callsign' in iddb:
            object_info['callsign'] = iddb['callsign'] + "'"
        if object_info['name'] == None and 'name' in iddb:
            object_info['name'] = iddb['name'] + "'"

        # Match against the set alerts
        # FIXME: Check for alerts!
        # If alert: set 'alert' = True
        message['alert'] = False

        # See if we need to sound the alert
        message['soundalert'] = False
        # If, so DB should be updated...

        # Make update or insert message
        if new:
            message['insert'] = object_info
        else:
            message['update'] = object_info
        # Call function to send message
        self.SendMsg(message)

    def CheckDBForOld(self):
        # Go through the DB and see if we can create 'remove' or
        # 'old' messages

        # Calculate datetime objects to compare with
        old_limit = datetime.datetime.now()-datetime.timedelta(seconds=config['common'].as_int('listmakegreytime'))
        remove_limit = datetime.datetime.now()-datetime.timedelta(seconds=config['common'].as_int('deleteitemtime'))

        # Compare objects in db against old_limit and remove_limit
        old_objects = [ r for r in self.db_main
                        if r['time'] < old_limit ]
        remove_objects = [ r for r in self.db_main
                           if r['time'] < remove_limit ]

        # Mark old as old in the DB and send messages
        for object in old_objects:
            self.db_main[object['__id__']]['old'] = True
            self.SendMsg({'old': object['mmsi']})
        # Delete removable objects in db
        self.db_main.delete(remove_objects)
        # Send removal messages
        for object in remove_objects:
            self.SendMsg({'remove': object['mmsi']})

    def SendMsg(self, message):
        # Puts message in queue for consumers to get
        try:
            self.outgoing.put(message)
        except Queue.Full:
            pass

    def ReturnOutgoing(self):
        # Return all messages in the outgoing queue
        templist = []
        try:
            while True:
                templist.append(self.outgoing.get_nowait())
        except Queue.Empty:
            return templist

    def Main(self):
        # Set some timers
        lastchecktime = time.time()
        lastlogtime = time.time()
        lastiddblogtime = time.time()
        incoming = {}
        # See if we should send a own position before looping
        if self.ownposition:
            self.SendMsg({'own_position': self.ownposition})
        while True:
            # Try to get the next item in queue
            try:
                incoming = self.queue.get()
            except: pass
            if incoming == 'stop': break
            # Check if incoming contains a MMSI number
            if 'mmsi' in incoming and incoming['mmsi'] > 1:
                update = self.DbUpdate(incoming)
                if update:
                    self.UpdateMsg(*update)
            # If incoming got own position data, use it
            elif 'ownlatitude' in incoming and 'ownlongitude' in incoming and not config['position'].as_bool('override_on'):
                ownlatitude = incoming['ownlatitude']
                ownlongitude = incoming['ownlongitude']
                try:
                    owngeoref = georef(ownlatitude,ownlongitude)
                except:
                    owngeoref = None
                self.ownposition.update({'ownlatitude': ownlatitude, 'ownlongitude': ownlongitude, 'owngeoref': owngeoref})
                # Send a position update
                self.SendMsg({'own_position': self.ownposition})
            # If incoming has special attributes
            elif 'add_consumer' in incoming:
                self.consumers.append(incoming['add_consumer'])
            elif 'consumer_delete' in incoming and incoming['consumer_delete'] in self.consumers:
                self.consumers.delete(incoming['consumer_delete'])
            elif 'query' in incoming:
                print "--> Write query code, stupid!"

            # Remove or mark objects as old if last update time is above threshold
            if lastchecktime + 10 < time.time():
                self.CheckDBForOld()
                lastchecktime = time.time()

            # Initiate logging to disk of log time is above threshold
            if config['logging'].as_bool('logging_on'):
                if config['logging'].as_int('logtime') == 0: pass
                elif lastlogtime + config['logging'].as_int('logtime') < time.time():
                    self.dblog()
                    lastlogtime = time.time()

            # Initiate iddb logging if current time is > (lastlogtime + logtime)
            if config['iddb_logging'].as_bool('logging_on'):
                if config['iddb_logging'].as_int('logtime') == 0: pass
                elif lastiddblogtime + config['iddb_logging'].as_int('logtime') < time.time():
                    self.iddblog()
                    lastiddblogtime = time.time()

    def dblog(self):
        # Make a query for the metadata, but return only rows where IMO
        # has a value, and make a MD5 hash out of the data
        newhashdict = {}
        for r in self.db_main:
            if r['imo']:
                # If base station, don't log it
                if r['base_station']: continue
                # Make of string of these fields
                infostring = str((r['imo'], r['name'], r['type'],
                                  r['callsign'], r['destination'],
                                  r['eta'], r['length'], r['width']))
                # Add info in dict as {mmsi: MD5-hash}
                newhashdict[r['mmsi']] = md5.new(infostring).digest()
        # Check what objects we should update in the metadata table
        update_mmsi = []
        for (key, value) in newhashdict.iteritems():
            # Check if we have logged this MMSI number before
            if key in self.hashdict:
                # Compare the hashes, if different: add to update list
                if cmp(value, self.hashdict[key]):
                    update_mmsi.append(key)
            else:
                # The MMSI was new, add to update list
                update_mmsi.append(key)
        # Set self.hashdict to the new hash dict
        self.hashdict = newhashdict
        # Query the memory DB
        positionquery = []
        # Calculate the oldest time we allow an object to have
        threshold = datetime.datetime.now() - datetime.timedelta(seconds=config['logging'].as_int('logtime'))
        # Iterate over all objects in db_main
        for r in self.db_main:
            # If base station, don't log it
            if r['base_station']: continue
            # If object is newer than threshold, get data
            if r['time'] > threshold:
                data = [r['time'], r['mmsi'], r['latitude'],
                        r['longitude'], r['georef'], r['sog'],
                        r['cog']]
                # Set all fields contaning value 'N/A' to Nonetype
                # (it's ugly, I know...)
                # Also convert decimal type to float
                for (i, v) in enumerate(data):
                    if v == 'N/A':
                        data[i] = None
                    elif type(v) == decimal.Decimal:
                        data[i] = float(v)
                positionquery.append(data)
        # Sort in chronological order (by time)
        positionquery.sort()
        metadataquery = []
        # Iterate over the objects we should update in metadata
        for mmsi in update_mmsi:
            # Get only the first list (should be only one anyway)
            r = self.db_main._mmsi[mmsi][0]
            data = [r['time'], r['mmsi'], r['imo'],
                    r['name'], r['type'], r['callsign'],
                    r['destination'], r['eta'], r['length'],
                    r['width']]
            # Remove any 'N/A' with Nonetype (ugly, I know...)
            for (i, v) in enumerate(data):
                if v == 'N/A':
                    data[i] = None
            metadataquery.append(data)
        # Sort in chronological order (by time)
        metadataquery.sort()
        # Open the file and log
        try:
            # Open file with filename in config['logging']['logfile']
            connection = sqlite.connect(config['logging']['logfile'])
            cursor = connection.cursor()
            # Create tables if they don't exist
            cursor.execute("CREATE TABLE IF NOT EXISTS position (time, mmsi, latitude, longitude, georef, sog, cog);")
            cursor.execute("CREATE TABLE IF NOT EXISTS metadata (time, mmsi, imo, name, type, callsign, destination, eta, length, width);")
            # Log to the two tables
            cursor.executemany("INSERT INTO position (time, mmsi, latitude, longitude, georef, sog, cog) VALUES (?, ?, ?, ?, ?, ?, ?)", positionquery)
            cursor.executemany("INSERT INTO metadata (time, mmsi, imo, name, type, callsign, destination, eta, length, width) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", metadataquery)
            # Commit changes and close file
            connection.commit()
            connection.close()
        except:
            logging.warning("Logging to disk failed", exc_info=True)

    def iddblog(self):
        # Query the memory iddb
        iddbquery = []
        for r in self.db_iddb:
            iddbquery.append((r['mmsi'], r['imo'], r['name'], r['callsign']))
        # Open the file and log
        try:
            # Open file with filename in config['iddb_logging']['logfile']
            connection = sqlite.connect(config['iddb_logging']['logfile'])
            cursor = connection.cursor()
            # Create table if it doesn't exist
            cursor.execute("CREATE TABLE IF NOT EXISTS iddb (mmsi PRIMARY KEY, imo, name, callsign);")
            # Log
            cursor.executemany("INSERT OR REPLACE INTO iddb (mmsi, imo, name, callsign) VALUES (?, ?, ?, ?)", iddbquery)
            # Commit changes and close file
            connection.commit()
            connection.close()
        except:
            logging.warning("Logging IDDB to disk failed", exc_info=True)

    def loadiddb(self):
        # See if an iddb logfile exists, if not, return
        try:
            dbfile = open(config['iddb_logging']['logfile'])
            dbfile.close()
        except: return
        try:
            # Open the db
            connection = sqlite.connect(config['iddb_logging']['logfile'])
            cursor = connection.cursor()
            # Select data from table iddb
            cursor.execute("SELECT * FROM iddb;",())
            iddb_data = cursor.fetchall()
            # Close connection
            connection.close()
            # Put iddb_data in the memory db
            for ship in iddb_data:
                self.db_iddb.insert(mmsi=int(ship[0]), imo=int(ship[1]), name=ship[2], callsign=ship[3])
        except:
            logging.warning("Reading from IDDB file failed", exc_info=True)

    def put(self, item):
        self.queue.put(item)

    def start(self):
        try:
            r = threading.Thread(target=self.Main)
            r.setDaemon(1)
            r.start()
            return True
        except:
            return False

    def stop(self):
        self.put('stop')


# Start threads
MainThread().start()
CommHubThread().start()
if config['serial_a'].as_bool('serial_on'):
    seriala = SerialThread()
    seriala.start('serial_a')
if config['serial_b'].as_bool('serial_on'):
    serialb = SerialThread()
    serialb.start('serial_b')
if config['serial_c'].as_bool('serial_on'):
    serialc = SerialThread()
    serialc.start('serial_c')
if config['network'].as_bool('server_on'):
    NetworkServerThread().start()
if config['network'].as_bool('client_on'):
    networkc = NetworkClientThread()
    networkc.start()

# Function for getting statistics from the various threads
def GetStats():
    stats = {}
    try:
        stats['serial_a'] = seriala.ReturnStats()
    except: pass
    try:
        stats['serial_b'] = serialb.ReturnStats()
    except: pass
    try:
        stats['serial_c'] = serialc.ReturnStats()
    except: pass
    try:
        stats['network'] = networkc.ReturnStats()
    except: pass
    return stats

# Start the GUI
# Wait some time before initiating, to let the threads settle
time.sleep(0.2)
app = GUI(0)
app.MainLoop()

# Stop threads
SerialThread().stop()
NetworkServerThread().stop()
NetworkClientThread().stop()
CommHubThread().stop()
MainThread().stop()

# Exit program when only one thread remains
while True:
    threads = threading.enumerate()
    nrofthreads = len(threads)
    try:
        networkserver_exist = threads.index('Thread(NetworkServer, started daemon)>')
    except ValueError:
        nrofthreads -=1
    if nrofthreads > 1:
        pass
    else:
        break
