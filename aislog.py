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
import pickle, codecs, csv
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
if os.name == 'nt':
    import serialwin32 as serial
    platform = 'nt'
elif os.name == 'posix':
    import serialposix as serial
    platform = 'posix'
else:
    platform = 'unknown'

### Fetch command line arguments
# Define standard config file
configfile = 'config.ini'

# Create optparse object
cmdlineparser = optparse.OptionParser()
# Add an option for supplying a different config file than the default one
cmdlineparser.add_option("-c", "--config", dest="configfile", help="Specify a config file other than the default")
cmdlineparser.add_option("-n", "--nogui", action="store_true", dest="nogui", default=False, help="Run without GUI, i.e. as a server and logger")
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
columnsetup = {'mmsi': [_("MMSI"), 80], 'mid': [_("Nation"), 55], 'imo': [_("IMO"), 80], 'name': [_("Name"), 150], 'type': [_("Type nbr"), 45], 'typename': [_("Type"), 80], 'callsign': [_("CS"), 65], 'latitude': [_("Latitude"), 110], 'longitude': [_("Longitude"), 115], 'georef': [_("GEOREF"), 85], 'creationtime': [_("Created"), 75], 'time': [_("Updated"), 75], 'sog': [_("Speed"), 60], 'cog': [_("Course"), 60], 'heading': [_("Heading"), 70], 'destination': [_("Destination"), 150], 'eta': [_("ETA"), 80], 'length': [_("Length"), 45], 'width': [_("Width"), 45], 'draught': [_("Draught"), 90], 'rateofturn': [_("ROT"), 60], 'navstatus': [_("NavStatus"), 150], 'posacc': [_("PosAcc"), 55], 'transponder_type': [_("Transponder type"), 90], 'bearing': [_("Bearing"), 65], 'distance': [_("Distance"), 70], 'remark': [_("Remark"), 150]}
# Set default keys and values
defaultconfig = {'common': {'listmakegreytime': 600, 'deleteitemtime': 3600, 'showbasestations': True, 'showclassbstations': True, 'showafterupdates': 3, 'listcolumns': 'mmsi, mid, name, typename, callsign, georef, creationtime, time, sog, cog, destination, navstatus, bearing, distance, remark', 'alertlistcolumns': 'mmsi, mid, name, typename, callsign, georef, creationtime, time, sog, cog, destination, navstatus, bearing, distance, remark'},
                 'logging': {'logging_on': False, 'logtime': '600', 'logfile': '', 'logbasestations': False},
                 'iddb_logging': {'logging_on': False, 'logtime': '600', 'logfile': 'testiddb.db'},
                 'alert': {'remarkfile_on': False, 'remarkfile': '', 'alertsound_on': False, 'alertsoundfile': ''},
                 'position': {'override_on': False, 'latitude': '0', 'longitude': '0', 'position_format': 'dms', 'use_position_from': 'any'},
                 'serial_a': {'serial_on': False, 'port': '0', 'baudrate': '38400', 'rtscts': False, 'xonxoff': False, 'send_to_serial_server': False, 'send_to_network_server': False},
                 'serial_server': {'server_on': False, 'port': '0', 'baudrate': '38400', 'rtscts': False, 'xonxoff': False},
                 'network': {'server_on': False, 'server_address': 'localhost', 'server_port': '23000', 'client_on': False, 'client_addresses': ['localhost:23000'], 'clients_to_serial': [], 'clients_to_server': []}}
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
config.comments['serial_server'] = ['', 'Settings for sending data through a serial port']
config.comments['network'] = ['', 'Settings for sending/receiving data through a network connection']
config['common'].comments['listmakegreytime'] = ['Number of s between last update and greying out an item']
config['common'].comments['deleteitemtime'] = ['Number of s between last update and removing an item from memory']
config['common'].comments['showbasestations'] = ['Enable display of base stations']
config['common'].comments['showclassbstations'] = ['Enable display of AIS Class B stations (small ships)']
config['common'].comments['showafterupdates'] = ['Number of updates to an object before displaying it']
config['common'].comments['listcolumns'] = ['Define visible columns in list view using db column names']
config['common'].comments['alertlistcolumns'] = ['Define visible columns in alert list view using db column names']
config['logging'].comments['logging_on'] = ['Enable file logging']
config['logging'].comments['logtime'] = ['Number of s between writes to log file']
config['logging'].comments['logfile'] = ['Filename of log file']
config['logging'].comments['logbasestations'] = ['Enable logging of base stations']
config['iddb_logging'].comments['logging_on'] = ['Enable IDDB file logging']
config['iddb_logging'].comments['logtime'] = ['Number of s between writes to log file']
config['iddb_logging'].comments['logfile'] = ['Filename of log file']
config['alert'].comments['remarkfile_on'] = ['Enable loading of remark file at program start']
config['alert'].comments['remarkfile'] = ['Filename of remark file']
config['alert'].comments['alertsound_on'] = ['Enable audio alert']
config['alert'].comments['alertsoundfile'] = ['Filename of wave sound file for audio alert']
config['position'].comments['override_on'] = ['Enable manual position override']
config['position'].comments['position_format'] = ['Define the position presentation format in DD, DM or DMS']
config['position'].comments['latitude'] = ['Latitude in decimal degrees (DD)']
config['position'].comments['longitude'] = ['Longitude in decimal degrees (DD)']
config['position'].comments['use_position_from'] = ['Define the source to get GPS position from']
config['network'].comments['server_on'] = ['Enable network server']
config['network'].comments['server_address'] = ['Server hostname or IP (server side)']
config['network'].comments['server_port'] = ['Server port (server side)']
config['network'].comments['client_on'] = ['Enable network client']
config['network'].comments['client_addresses'] =['List of server:port to connect and use data from']
config['network'].comments['clients_to_serial'] =['List of server:port to send data to serial out']
config['network'].comments['clients_to_server'] =['List of server:port to send data to network server']


# Define global variables
mid = {}
midfull = {}
typecode = {}
data = {}
owndata = {}
# Define collections
rawdata = collections.deque()
# Set start time to start_time
start_time = datetime.datetime.now()


class MainWindow(wx.Frame):
    # Intialize a set, a dict and a list
    # active_set for the MMSI numers who are active,
    # grey_dict for grey-outed MMSI numbers (and distance)
    # last_own_pos for last own position
    active_set = set()
    grey_dict = {}
    last_own_pos = []

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

        # Set some dlg pointers to None
        self.set_alerts_dlg = None
        self.stats_dlg = None
        self.raw_data_dlg = None
        # A dict for keeping track of open Detail Windows
        self.detailwindow_dict = {}

    def GetMessages(self, event):
        # Get messages from main thread
        messages = main_thread.ReturnOutgoing()
        # See what to do with them
        for message in messages:
            if 'update' in message:
                # "Move" from grey_dict to active_set
                if message['update']['mmsi'] in self.grey_dict:
                    del self.grey_dict[message['update']['mmsi']]
                self.active_set.add(message['update']['mmsi'])
                # Update lists
                self.splist.Update(message)
                self.spalert.Update(message)
                # See if we should send to a detail window
                if message['update']['mmsi'] in self.detailwindow_dict:
                    self.detailwindow_dict[message['update']['mmsi']].DoUpdate(message['update'])
            elif 'insert' in message:
                # Insert to active_set
                self.active_set.add(message['insert']['mmsi'])
                # Refresh status row
                self.OnRefreshStatus()
                # Update lists
                self.splist.Update(message)
                self.spalert.Update(message)
            elif 'old' in message:
                # "Move" from active_set to grey_dict
                distance = message['old'].get('distance', None)
                if message['old']['mmsi'] in self.active_set:
                    self.active_set.discard(message['old']['mmsi'])
                    self.grey_dict[message['old']['mmsi']] = distance
                # Refresh status row
                self.OnRefreshStatus()
                # Update lists
                self.splist.Update(message)
                self.spalert.Update(message)
            elif 'remove' in message:
                # Remove from grey_dict (and active_set to be sure)
                self.active_set.discard(message['remove'])
                if message['remove'] in self.grey_dict:
                    del self.grey_dict[message['remove']]
                # Refresh status row
                self.OnRefreshStatus()
                # Update lists
                self.splist.Update(message)
                self.spalert.Update(message)
            elif 'own_position' in message:
                # Refresh status row with own_position
                self.OnRefreshStatus(message['own_position'])
            elif 'query' in message:
                # See if we should send to a detail window
                if message['query']['mmsi'] in self.detailwindow_dict:
                    self.detailwindow_dict[message['query']['mmsi']].DoUpdate(message['query'])
            elif 'remarkdict' in message:
                # See if we should send to set alert window
                if self.set_alerts_dlg:
                    self.set_alerts_dlg.GetData(message)
            elif 'iddb' in message:
                # See if we should send to set alert window
                if self.set_alerts_dlg:
                    self.set_alerts_dlg.GetData(message)
            elif 'error' in message:
                # Create a dialog and display error
                self.ShowErrorMsg(message['error'])
        # Refresh the listctrls (by sorting)
        self.splist.Refresh()
        self.spalert.Refresh()
        # See if we should fetch statistics data from CommHubThread
        # Also add data in grey_dict and nbr of items
        if self.stats_dlg:
            self.stats_dlg.SetData([comm_hub_thread.ReturnStats(), self.grey_dict, len(self.active_set)])
        # See if we should fetch raw data from CommHubThread
        if self.raw_data_dlg:
            self.raw_data_dlg.SetData(comm_hub_thread.ReturnRaw())

    def splitwindows(self, window=None):
        if self.split.IsSplit(): self.split.Unsplit(window)
        else: self.split.SplitHorizontally(self.splist, self.spalert, 0)

    def ShowErrorMsg(self, messagestring):
        # Format and show a message dialog displaying the error and
        # the last line from the traceback (internal exception message)
        messagelist = messagestring.splitlines(True)
        message = messagelist[0]
        if len(messagelist) > 1:
            traceback = messagelist[-1]
        else:
            traceback = ''
        dlg = wx.MessageDialog(self, "\n" +message+ "\n" +traceback, style=wx.OK|wx.ICON_ERROR)
        dlg.ShowModal()

    def AddDetailWindow(self, window, mmsi):
        # If there already is a window open with the same MMSI number,
        # destroy the new window. Else add window dict
        if mmsi in self.detailwindow_dict:
            window.Destroy()
        else:
            self.detailwindow_dict[mmsi] = window

    def RemoveDetailWindow(self, mmsi):
        # Remove window from the dict
        del self.detailwindow_dict[mmsi]

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
            # Try to read line as ASCII/UTF-8, if error, try cp1252
            try:
                typecode[row[0]] = unicode(row[1], 'utf-8')
            except:
                typecode[row[0]] = unicode(row[1], 'cp1252')
        f.close()

    def OnRefreshStatus(self, own_pos=False):
        # Update the status row
        # Get total number of items by taking the length of the union
        # between active_set and grey_dict
        nbrgreyitems = len(self.grey_dict)
        nbritems = len(self.active_set) + nbrgreyitems
        # See if we should update the position row
        if own_pos:
            # Get human-readable position and save to variable
            self.last_own_pos = [PositionConversion(own_pos['ownlatitude'],own_pos['ownlongitude']).default, own_pos['owngeoref']]
        if self.last_own_pos:
            # Set text with own position
            self.SetStatusText(_("Own position: ") + self.last_own_pos[0][0] + '  ' + self.last_own_pos[0][1] + '  (' + self.last_own_pos[1] + ')', 0)
        # Set number of objects and old objects
        self.SetStatusText(_("Total nbr of objects / old: ") + str(nbritems) + ' / ' + str(nbrgreyitems), 1)

    def OnShowRawdata(self, event):
        self.raw_data_dlg = RawDataWindow(None, -1)
        self.raw_data_dlg.Show()

    def OnStatistics(self, event):
        self.stats_dlg = StatsWindow(None, -1)
        self.stats_dlg.Show()

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
        name = 'File'
        lastupdate_line = 0
        for linenumber, line in enumerate(f):

            # If indata contains raw data, pass it along
            if line[0] == '!' or line[0] == '$':
                # Put it in CommHubThread's queue
                comm_hub_thread.put([name,line])

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
        self.set_alerts_dlg = SetAlertsWindow(None, -1)
        self.set_alerts_dlg.Show()

    def OnSettings(self, event):
        dlg = SettingsWindow(None, -1)
        dlg.Show()


class ListWindow(wx.Panel):
    def __init__(self, parent, id):
        wx.Panel.__init__(self, parent, id, style=wx.CLIP_CHILDREN)

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
        wx.Panel.__init__(self, parent, id, style=wx.CLIP_CHILDREN)

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
        if message.get('alert', False):
            # Update the underlying listctrl data with message
            self.list.OnUpdate(message)
        # Sound an alert for selected objects
        if message.get('soundalert', False):
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
        self.Bind(wx.EVT_KEY_UP, self.OnKey)

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

    def OnKey(self, event):
        # Deselect all objects if escape is pressed
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            for i in range(self.GetItemCount()):
                self.SetItemState(i, 0, wx.LIST_STATE_SELECTED)
            self.selected = -1

    def OnUpdate(self, message):
        # See what message we should work with
        if 'update' in message:
            data = message['update']
            # Remove object from grey item set
            self.greyitems.discard(data['mmsi'])
            # If alert, put it in alert item set
            if message.get('alert', False):
                self.alertitems.add(data['mmsi'])
            # Get the data formatted
            self.itemDataMap[data['mmsi']] = self.FormatData(data)
        elif 'insert' in message:
            # Set a new item count in the listctrl
            self.SetItemCount(self.GetItemCount()+1)
            data = message['insert']
            # If alert, put it in alert item set
            if message.get('alert', False):
                self.alertitems.add(data['mmsi'])
            # Get the data formatted
            self.itemDataMap[data['mmsi']] = self.FormatData(data)
        elif 'remove' in message:
            # Get the MMSI number
            mmsi = message['remove']
            # Remove object from sets
            self.greyitems.discard(mmsi)
            self.alertitems.discard(mmsi)
            # Remove object if possible
            if mmsi in self.itemDataMap:
                # Set a new item count in the listctrl
                self.SetItemCount(self.GetItemCount()-1)
                # Remove object from list dict
                del self.itemDataMap[mmsi]
        elif 'old' in message:
            # Get the MMSI number
            mmsi = message['old']['mmsi']
            # Add object to set if already in lists
            if mmsi in self.itemDataMap:
                self.greyitems.add(message['old']['mmsi'])

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
                elif col == 'time':
                    try: new[i] = data[col].isoformat()[11:19]
                    except: new[i] = ''
                elif col == 'latitude':
                    latpos = i
                elif col == 'longitude':
                    longpos = i
                elif col == 'navstatus':
                    navstatus = data[col]
                    if navstatus == None: navstatus = ''
                    elif navstatus == 0: navstatus = _("Under Way")
                    elif navstatus == 1: navstatus = _("At Anchor")
                    elif navstatus == 2: navstatus = _("Not Under Command")
                    elif navstatus == 3: navstatus = _("Restricted Manoeuvrability")
                    elif navstatus == 4: navstatus = _("Constrained by her draught")
                    elif navstatus == 5: navstatus = _("Moored")
                    elif navstatus == 6: navstatus = _("Aground")
                    elif navstatus == 7: navstatus = _("Engaged in Fishing")
                    elif navstatus == 8: navstatus = _("Under way sailing")
                    new[i] = navstatus
                elif col == 'posacc':
                    if data[col] == 0: new[i] = _('GPS')
                    elif data[col] == 1: new[i] = _('DGPS')
                    else: new[i] = ''
                elif col == 'transponder_type':
                    if data[col] == 'A': new[i] = _('Class A')
                    elif data[col] == 'B': new[i] = _('Class B')
                    elif data[col] == 'base': new[i] = _('Base station')
        # Get position in a more human-readable format
        if data.get('latitude',False) and data.get('longitude',False) and data['latitude'] != 'N/A' and data['longitude'] != 'N/A':
            pos = PositionConversion(data['latitude'],data['longitude']).default
            if latpos:
                new[latpos] = pos[0]
            if longpos:
                new[longpos] = pos[1]
        return new

    def OnGetItemText(self, item, col):
        # Return the text in item, col
        mmsi = self.itemIndexMap[item]
        string = unicode(self.itemDataMap[mmsi][col])
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
        # Sort items
        items = list(self.itemDataMap.keys())
        items.sort(sorter)
        self.itemIndexMap = items

        # Workaround for updating listctrl on Windows
        if platform == 'nt':
            self.Refresh(False)

        # See if the previous selected row exists after the sort
        # If the MMSI number is found, set the new position as
        # selected. If not found, deselect all objects
        try:
            if self.selected in self.itemDataMap:
                new_position = self.FindItem(-1, unicode(self.selected))
                self.SetItemState(new_position, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
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
        # Set self.itemmmsi to itemmmsi
        self.itemmmsi = itemmmsi

        # Define the dialog
        wx.Dialog.__init__(self, parent, id, title=str(itemmmsi)+' - '+_("Detail window"))
        # Create panels
        shipdata_panel = wx.Panel(self, -1)
        voyagedata_panel = wx.Panel(self, -1)
        transponderdata_panel = wx.Panel(self, -1)
        objinfo_panel = wx.Panel(self, -1)
        self.remark_panel = wx.Panel(self, -1)
        # Create static boxes
        wx.StaticBox(shipdata_panel,-1,_(" Ship data "),pos=(3,5),size=(380,205))
        wx.StaticBox(voyagedata_panel,-1,_(" Voyage data "),pos=(3,5),size=(320,205))
        wx.StaticBox(transponderdata_panel,-1,_(" Received transponder data "),pos=(3,5),size=(380,85))
        wx.StaticBox(objinfo_panel,-1,_(" Object information "),pos=(3,5),size=(320,155))
        wx.StaticBox(self.remark_panel,-1,_(" Remark "), pos=(3,5),size=(380,65))
        self.remark_panel.Enable(False)
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
        wx.StaticText(transponderdata_panel,-1,_("Navigational Status: "),pos=(12,25),size=(150,16))
        wx.StaticText(transponderdata_panel,-1,_("Position Accuracy: "),pos=(12,45),size=(150,16))
        wx.StaticText(transponderdata_panel,-1,_("Transponder Type: "),pos=(12,65),size=(150,16))
        # Object information such as bearing and distance
        wx.StaticText(objinfo_panel,-1,_("Bearing: "),pos=(12,25),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Distance: "),pos=(12,45),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Updates: "),pos=(12,65),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Source: "),pos=(12,85),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Created: "),pos=(12,105),size=(150,16))
        wx.StaticText(objinfo_panel,-1,_("Updated: "),pos=(12,125),size=(150,16))

        # Set ship data
        self.text_mmsi = wx.StaticText(shipdata_panel,-1,'',pos=(100,25),size=(280,16))
        self.text_imo = wx.StaticText(shipdata_panel,-1,'',pos=(100,45),size=(280,16))
        self.text_country = wx.StaticText(shipdata_panel,-1,'',size=(280,16),pos=(100,65))
        self.text_name = wx.StaticText(shipdata_panel,-1,'',pos=(100,85),size=(280,16))
        self.text_type = wx.StaticText(shipdata_panel,-1,'',pos=(100,105),size=(280,16))
        self.text_callsign = wx.StaticText(shipdata_panel,-1,'',pos=(100,125),size=(280,16))
        self.text_length = wx.StaticText(shipdata_panel,-1,'',pos=(100,145),size=(280,16))
        self.text_width = wx.StaticText(shipdata_panel,-1,'',pos=(100,165),size=(280,16))
        self.text_draught = wx.StaticText(shipdata_panel,-1,'',pos=(100,185),size=(280,16))
        # Set voyage data
        self.text_destination = wx.StaticText(voyagedata_panel,-1,'',pos=(100,25),size=(215,16))
        self.text_etatime = wx.StaticText(voyagedata_panel,-1,'',pos=(100,45),size=(215,16))
        self.text_latitude = wx.StaticText(voyagedata_panel,-1,'',pos=(100,65),size=(215,16))
        self.text_longitude = wx.StaticText(voyagedata_panel,-1,'',pos=(100,85),size=(215,16))
        self.text_georef = wx.StaticText(voyagedata_panel,-1,'',pos=(100,105),size=(215,16))
        self.text_sog = wx.StaticText(voyagedata_panel,-1,'',pos=(100,125),size=(215,16))
        self.text_cog = wx.StaticText(voyagedata_panel,-1,'',pos=(100,145),size=(215,16))
        self.text_heading = wx.StaticText(voyagedata_panel,-1,'',pos=(100,165),size=(215,16))
        self.text_rateofturn = wx.StaticText(voyagedata_panel,-1,'',pos=(100,185),size=(215,16))
        # Set transponderdata
        self.text_navstatus = wx.StaticText(transponderdata_panel,-1,'',pos=(145,25),size=(125,16))
        self.text_posacc = wx.StaticText(transponderdata_panel,-1,'',pos=(145,45),size=(125,16))
        self.text_transpondertype = wx.StaticText(transponderdata_panel,-1,'',pos=(145,65),size=(125,16))
        # Set object information
        self.text_bearing = wx.StaticText(objinfo_panel,-1,'',pos=(105,25),size=(215,16))
        self.text_distance = wx.StaticText(objinfo_panel,-1,'',pos=(105,45),size=(215,16))
        self.text_updates = wx.StaticText(objinfo_panel,-1,'',pos=(105,65),size=(215,16))
        self.text_source = wx.StaticText(objinfo_panel,-1,'',pos=(105,85),size=(215,16))
        self.text_creationtime = wx.StaticText(objinfo_panel,-1,'',pos=(105,105),size=(215,16))
        self.text_time = wx.StaticText(objinfo_panel,-1,'',pos=(105,125),size=(215,16))
        # Set remark text
        self.text_remark = wx.StaticText(self.remark_panel,-1,'',pos=(12,25),size=(350,40),style=wx.ST_NO_AUTORESIZE)

        # Add window to the message detail window send list
        main_window.AddDetailWindow(self, itemmmsi)

        # Set query in MainThread's queue
        main_thread.put({'query': itemmmsi})

        # Buttons & events
        closebutton = wx.Button(self,1,_("&Close"),pos=(490,438))
        closebutton.SetFocus()
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=1)
        self.Bind(wx.EVT_KEY_UP, self.OnKey)
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
        sizer2.Add(self.remark_panel, 0)
        sizer1.Add(sizer2)
        sizer1.Add(objinfo_panel, 0)
        mainsizer.Add(sizer1)
        mainsizer.AddSpacer((0,10))
        sizer_button.Add(closebutton, 0)
        mainsizer.Add(sizer_button, flag=wx.ALIGN_RIGHT)
        self.SetSizerAndFit(mainsizer)

    def OnKey(self, event):
        # Close dialog if escape is pressed
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.OnClose(event)

    def DoUpdate(self, data):
        # Set ship data
        self.text_mmsi.SetLabel(str(data['mmsi']))
        if data['imo']: self.text_imo.SetLabel(str(data['imo']))
        if data['mid']: country = data['mid']
        else: country = _("[Non ISO]")
        if str(data['mmsi'])[0:3] in midfull: country += ' - ' + midfull[str(data['mmsi'])[0:3]]
        self.text_country.SetLabel(country)
        if data['name']: self.text_name.SetLabel(data['name'])
        if data['type']: type = str(data['type'])
        else: type = ''
        if data['typename']: type += ' - ' + unicode(data['typename'])
        self.text_type.SetLabel(type)
        if data['callsign']: self.text_callsign.SetLabel(data['callsign'])
        if data['length'] == 'N/A': self.text_length.SetLabel('N/A')
        elif not data['length'] is None: self.text_length.SetLabel(str(data['length'])+' m')
        if data['width'] == 'N/A': self.text_width.SetLabel('N/A')
        elif not data['width'] is None: self.text_width.SetLabel(str(data['width'])+' m')
        if data['draught'] == 'N/A': self.text_draught.SetLabel('N/A')
        elif not data['draught'] is None: self.text_draught.SetLabel(str(data['draught'])+' m')
        # Set voyage data
        if data['destination']: self.text_destination.SetLabel(data['destination'])
        if data['eta']:
            try:
                etatime = 0,int(data['eta'][0:2]),int(data['eta'][2:4]),int(data['eta'][4:6]),int(data['eta'][6:8]),1,1,1,1
                fulletatime = time.strftime(_("%d %B at %H:%M"),etatime)
            except: fulletatime = data['eta']
            if fulletatime == '00002460': fulletatime = 'N/A'
            self.text_etatime.SetLabel(fulletatime)
        if data.get('latitude',False) and data.get('longitude',False) and data['latitude'] != 'N/A' and data['longitude'] != 'N/A':
            pos = PositionConversion(data['latitude'],data['longitude']).default
            self.text_latitude.SetLabel(pos[0])
            self.text_longitude.SetLabel(pos[1])
        elif not data['latitude'] is None and not data['longitude'] is None:
            self.text_latitude.SetLabel(data['latitude'])
            self.text_longitude.SetLabel(data['longitude'])
        if data['georef']: self.text_georef.SetLabel(data['georef'])
        if data['sog'] == 'N/A': self.text_sog.SetLabel('N/A')
        elif not data['sog'] is None: self.text_sog.SetLabel(str(data['sog'])+' kn')
        if data['cog'] == 'N/A': self.text_cog.SetLabel('N/A')
        elif not data['cog'] is None: self.text_cog.SetLabel(str(data['cog'])+u'°')
        if data['heading'] == 'N/A':  self.text_heading.SetLabel('N/A')
        elif not data['heading'] is None: self.text_heading.SetLabel(str(data['heading'])+u'°')
        if data['rot'] == 'N/A': self.text_rateofturn.SetLabel('N/A')
        elif not data['rot'] is None: self.text_rateofturn.SetLabel(str(data['rot'])+u'°/m')
        # Set transponder data
        navstatus = data['navstatus']
        if navstatus == None: navstatus = ''
        elif navstatus == 0: navstatus = _("Under Way")
        elif navstatus == 1: navstatus = _("At Anchor")
        elif navstatus == 2: navstatus = _("Not Under Command")
        elif navstatus == 3: navstatus = _("Restricted Manoeuvrability")
        elif navstatus == 4: navstatus = _("Constrained by her draught")
        elif navstatus == 5: navstatus = _("Moored")
        elif navstatus == 6: navstatus = _("Aground")
        elif navstatus == 7: navstatus = _("Engaged in Fishing")
        elif navstatus == 8: navstatus = _("Under way sailing")
        else: navstatus = str(navstatus)
        self.text_navstatus.SetLabel(navstatus)
        if not data['posacc'] is None:
            if data['posacc']: posacc = _("Very good / DGPS")
            else: posacc = _("Good / GPS")
            self.text_posacc.SetLabel(posacc)
        if not data.get('transponder_type', None) is None:
            if data['transponder_type'] == 'A': transponder_type = _("Class A")
            elif data['transponder_type'] == 'B': transponder_type = _("Class B")
            elif data['transponder_type'] == 'base': transponder_type = _("Base station")
            else: transponder_type = data['transponder_type']
            self.text_transpondertype.SetLabel(transponder_type)
        # Set local info
        if data['bearing'] and data['distance']:
            self.text_bearing.SetLabel(str(data['bearing'])+u'°')
            self.text_distance.SetLabel(str(data['distance'])+' km')
        if data['creationtime']:
            self.text_creationtime.SetLabel(data['creationtime'].strftime('%Y-%m-%d %H:%M:%S'))
        if data['time']:
            self.text_time.SetLabel(data['time'].strftime('%Y-%m-%d %H:%M:%S'))
        if not data['__version__'] is None:
            self.text_updates.SetLabel(str(data['__version__']))
        if data['source']:
            self.text_source.SetLabel(str(data['source']))
        # Set remark text
        if data['remark']:
            self.remark_panel.Enable(True)
            self.text_remark.SetLabel(unicode(data['remark']))

    def OnClose(self, event):
        # Remove window to the message detail window send list
        main_window.RemoveDetailWindow(self.itemmmsi)
        # Destory dialog
        self.Destroy()


class StatsWindow(wx.Dialog):
    def __init__(self, parent, id):
        # Define the dialog
        wx.Dialog.__init__(self, parent, id, title=_("Statistics"))
        # Create panels
        objects_panel = wx.Panel(self, -1)
        objects_panel.SetMinSize((280,-1))
        horizon_panel = wx.Panel(self, -1)
        horizon_panel.SetMinSize((210,-1))
        self.input_panel = wx.Panel(self, -1)
        self.input_panel.SetMinSize((450,-1))
        uptime_panel = wx.Panel(self, -1)
        # Create static boxes
        box_objects = wx.StaticBox(objects_panel,-1,_(" Objects "))
        box_horizon = wx.StaticBox(horizon_panel,-1,_(" Radio Horizon (calculated) "))
        box_input = wx.StaticBox(self.input_panel,-1,_(" Inputs "))
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

        # Initial input panel and sizer
        # The sub-boxes are created on request in Update
        self.maininput_sizer = wx.StaticBoxSizer(box_input, wx.VERTICAL)
        self.input_sizer = wx.GridSizer(0, 2, 10, 10)
        self.maininput_sizer.Add(self.input_sizer, 0, wx.EXPAND)
        self.input_panel.SetSizer(self.maininput_sizer)

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
        self.mainsizer = wx.BoxSizer(wx.VERTICAL)
        sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer2 = wx.BoxSizer(wx.VERTICAL)
        sizer_button = wx.BoxSizer(wx.HORIZONTAL)
        # Sizer1 is the sizer positioning the different panels and boxes
        # Sizer2 is an inner sizer for the objects data and update panels
        sizer2.Add(objects_panel, 0)
        sizer2.AddSpacer(5)
        sizer2.Add(uptime_panel, 0, wx.EXPAND)
        sizer1.Add(sizer2)
        sizer1.AddSpacer(5)
        sizer1.Add(horizon_panel, 0, wx.EXPAND)
        self.mainsizer.Add(sizer1)
        self.mainsizer.AddSpacer(5)
        self.mainsizer.Add(self.input_panel, 0, wx.EXPAND)
        self.mainsizer.AddSpacer((0,10))
        sizer_button.Add(closebutton, 0)
        self.mainsizer.Add(sizer_button, flag=wx.ALIGN_RIGHT)
        self.SetSizerAndFit(self.mainsizer)

        # Define dict for storing input boxes
        self.input_boxes = {}

        # Set variables to hold data for calculating parse rate
        self.LastUpdateTime = 0
        self.OldParseStats = {}

    def MakeInputStatBox(self, panel, boxlabel):
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
        rate = wx.StaticText(panel_right,-1,'',pos=(-1,40))
        sizer.AddSpacer(5)
        sizer.Add(panel_left, 0)
        sizer.AddSpacer(10)
        sizer.Add(panel_right, 1, wx.EXPAND)
        return {'sizer': sizer, 'received': received, 'parsed': parsed, 'rate': rate}

    def Update(self, input_stats, grey_dict, nbr_tot_items):
        # Update data in the window
        horizon = self.CalcHorizon(grey_dict)
        # Objects text
        self.text_object_nbr.SetLabel(str(nbr_tot_items))
        self.text_object_grey_nbr.SetLabel(str(horizon[0]))
        self.text_object_distance_nbr.SetLabel(str(horizon[1]))
        # Horizon text
        self.text_horizon_min.SetLabel(str(round(horizon[2],1)) + " km")
        self.text_horizon_max.SetLabel(str(round(horizon[3],1)) + " km")
        self.text_horizon_mean.SetLabel(str(round(horizon[4],1)) + " km")
        self.text_horizon_median.SetLabel(str(round(horizon[5],1)) + " km")
        # Uptime text
        uptime = datetime.datetime.now() - start_time
        up_since = start_time.isoformat()[:19]
        self.text_uptime_delta.SetLabel(str(uptime).split('.')[0])
        self.text_uptime_since.SetLabel(str(up_since.replace('T', " "+_("at")+" ")))
        # Iterate over items in the statistics dict
        for (name, data) in input_stats.iteritems():
            if name in self.input_boxes:
                # Just update the box
                box = self.input_boxes[name]
                if 'received' in data:
                    box['received'].SetLabel(str(data['received'])+_(" msgs"))
                if 'parsed' in data:
                    box['parsed'].SetLabel(str(data['parsed'])+_(" msgs"))
                    rate = self.CalcParseRate(name, data['parsed'])
                    box['rate'].SetLabel(str(rate)+_(" msgs/sec"))
            else:
                # New input name, redraw input panel
                self.input_boxes[name] = self.MakeInputStatBox(self.input_panel, " " + name + " ")
                self.input_sizer.Add(self.input_boxes[name]['sizer'], 1, wx.EXPAND)
                self.maininput_sizer.Layout()
                self.SetSizerAndFit(self.mainsizer)
        # Set current time to LastUpdateTime
        self.LastUpdateTime = time.time()
                
    def CalcParseRate(self, name, nbrparsed):
        # Compare data from five runs ago with new data and calculate
        # a parse rate
        rate = 0
        # If there are a LastUpdateTime, check for input_stats
        if self.LastUpdateTime:
            # Calculate a timediff (in seconds)
            timediff = time.time() - self.LastUpdateTime
            # Check if OldParseStats are available
            if name in self.OldParseStats:
                # Calculate a rate based on the oldest of the five
                # previous updates
                diff = nbrparsed - self.OldParseStats[name][0]
                # Calculate the rate
                rate = round((diff / (timediff * 5)), 1)
            else:
                # Set the list to current values
                self.OldParseStats[name] = [nbrparsed,nbrparsed,nbrparsed,nbrparsed,nbrparsed]
            # Set new stats to the OldParseStats list
            self.OldParseStats[name].append(nbrparsed)
            # Remove the oldest (first) item
            del self.OldParseStats[name][0]
        # Return rate
        return rate

    def CalcHorizon(self, grey_dict):
        # Calculate a "horizon", the distance to greyed out objects
        # Set as initial values
        nbrgreyitems = 0
        nbrhorizonitems = 0
        totaldistance = 0
        distancevalues = []
        # Extract values from grey_dict
        for distance in grey_dict.itervalues():
            nbrgreyitems += 1
            if distance:
                totaldistance += float(distance)
                distancevalues.append(float(distance))
                nbrhorizonitems += 1
        # Calculate median
        median = 0
        # Calculate meanvalue
        if totaldistance > 0: mean = (totaldistance/nbrhorizonitems)
        else: mean = 0
        # Sort the list and take the middle element.
        n = len(distancevalues)
        # Make sure that "numbers" keeps its original order
        copy = distancevalues[:]
        copy.sort()
        if n > 2:
            # If there is an odd number of elements
            if n & 1:
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
        return nbrgreyitems, nbrhorizonitems, minimum, maximum, mean, median

    def SetData(self, data):
        # Make an update with the new data
        # data[0] is the stats dict
        # data[1] is the grey dict
        # data[2] is the total nbr of items
        self.Update(data[0], data[1], data[2])

    def OnClose(self, event):
        self.Destroy()


class SetAlertsWindow(wx.Dialog):
    # Make a dict for the list ctrl data
    list_data = {}

    def __init__(self, parent, id):
        # Define the dialog
        wx.Dialog.__init__(self, parent, id, title=_("Set alerts and remarks"))
        # Create panels
        filter_panel = wx.Panel(self, -1)
        list_panel = wx.Panel(self, -1, style=wx.CLIP_CHILDREN)
        self.object_panel = wx.Panel(self, -1)
        action_panel = wx.Panel(self, -1)
        # Create static boxes
        wx.StaticBox(filter_panel, -1, _(" Filter "), pos=(3,5), size=(700,100))
        list_staticbox = wx.StaticBox(list_panel, -1, _(" List view "), pos=(3,5), size=(700,280))
        wx.StaticBox(self.object_panel, -1, _(" Selected object "), pos=(3,5), size=(570,160))
        wx.StaticBox(action_panel, -1, _(" Actions "), pos=(3,5), size=(130,160))

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
        self.current_filter = {}

        # Create the object information objects
        wx.StaticText(self.object_panel, -1, _("MMSI nbr:"), pos=(20,25))
        self.statictext_mmsi = wx.StaticText(self.object_panel, -1, '', pos=(20,45))
        wx.StaticText(self.object_panel, -1, _("IMO nbr:"), pos=(120,25))
        self.statictext_imo = wx.StaticText(self.object_panel, -1, '', pos=(120,45))
        wx.StaticText(self.object_panel, -1, _("Callsign:"), pos=(220,25))
        self.statictext_cs = wx.StaticText(self.object_panel, -1, '', pos=(220,45))
        wx.StaticText(self.object_panel, -1, _("Name:"), pos=(320,25))
        self.statictext_name = wx.StaticText(self.object_panel, -1, '', pos=(320,45))
        statictext_remark = wx.StaticText(self.object_panel, -1, _("Remark field:"), pos=(25,73))
        statictext_remark.SetFont(wx.Font(10, wx.NORMAL, wx.NORMAL, wx.NORMAL))
        self.textctrl_remark = wx.TextCtrl(self.object_panel, -1, pos=(20,90), size=(300,60), style=wx.TE_MULTILINE)
        self.radiobox_alert = wx.RadioBox(self.object_panel, -1, _(" Alert "), pos=(340,70), choices=(_("&No"), _("&Yes"), _("&Sound")))
        self.update_button = wx.Button(self.object_panel, 10, _("&Update object"), pos=(350,120))
        self.object_panel.Enable(False)

        # Create the list control
        self.lc = self.List(list_panel, self)

        # Create buttons
        wx.Button(action_panel, 20, _("&Insert new..."), pos=(20,50))
        wx.Button(action_panel, 22, _("&Export list..."), pos=(20,90))
        self.apply_button = wx.Button(self, 31, _("&Apply changes"))
        self.apply_button.Enable(False)
        self.save_button = wx.Button(self, 32, _("&Save changes"))
        self.save_button.Enable(False)
        close_button = wx.Button(self, 30, _("&Close"))

        # Create sizers
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        mainsizer.Add(filter_panel, 1, wx.EXPAND, 0)
        mainsizer.Add(list_panel, 0)
        lowsizer = wx.BoxSizer(wx.HORIZONTAL)
        lowsizer.Add(self.object_panel, 1)
        lowsizer.Add(action_panel, 0, wx.EXPAND)
        mainsizer.Add(lowsizer, 0)
        mainsizer.AddSpacer((0,10))
        mainsizer.Add(sizer2, 0, flag=wx.ALIGN_RIGHT)
        sizer2.Add(self.apply_button, 0)
        sizer2.AddSpacer((15,0))
        sizer2.Add(self.save_button, 0)
        sizer2.AddSpacer((50,0))
        sizer2.Add(close_button, 0)
        self.SetSizerAndFit(mainsizer)
        mainsizer.Layout()

        # Define events
        self.Bind(wx.EVT_CHECKBOX, self.OnFilter, self.checkbox_filteralerts)
        self.Bind(wx.EVT_CHECKBOX, self.OnFilter, self.checkbox_filterremarks)
        self.Bind(wx.EVT_TEXT, self.OnFilter, self.textctrl_filtertext)
        self.Bind(wx.EVT_TEXT, self.OnObjectEdit, self.textctrl_remark)
        self.Bind(wx.EVT_RADIOBOX, self.OnObjectEdit, self.radiobox_alert)
        self.Bind(wx.EVT_BUTTON, self.OnObjectUpdate, id=10)
        self.Bind(wx.EVT_BUTTON, self.OnInsertNew, id=20)
        self.Bind(wx.EVT_BUTTON, self.OnExportList, id=22)
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=30)
        self.Bind(wx.EVT_BUTTON, self.OnApplyChanges, id=31)
        self.Bind(wx.EVT_BUTTON, self.OnSaveChanges, id=32)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Set queries in MainThread's queue
        main_thread.put({'remarkdict_query': None})
        main_thread.put({'iddb_query': None})

        # Show a dialog asking the user to wait
        self.progress = wx.ProgressDialog(_("Please wait"), _("Populating list..."), parent=self)

    def GetData(self, message):
        # Update the list ctrl dict with new data
        # If remarks, put in alerts and remarks in dict
        if 'remarkdict' in message:
            for mmsi, (alert,remark) in message['remarkdict'].iteritems():
                row = self.list_data.get(mmsi, {})
                row['alert'] = alert
                row['remark'] = remark
                self.list_data[mmsi] = row
        # If IDDB data, put in metadata in dict
        elif 'iddb' in message:
            for object in message['iddb']:
                mmsi = object['mmsi']
                row = self.list_data.get(mmsi, {})
                row['imo'] = object['imo']
                row['callsign'] = object['callsign']
                row['name'] = object['name']
                self.list_data[mmsi] = row
        # Destroy progress dialog
        if self.progress:
            self.progress.Destroy()
        # Update the listctrl
        self.lc.OnUpdate()

    def PopulateObject(self, objectinfo):
        # Populate the objec_panel with info from the currently selected list row
        if objectinfo:
            self.object_panel.Enable(True)
            self.update_button.Enable(False)
            self.loaded_objectinfo = objectinfo
            self.statictext_mmsi.SetLabel(unicode(objectinfo[0]))
            self.statictext_imo.SetLabel(unicode(objectinfo[1]))
            self.statictext_cs.SetLabel(unicode(objectinfo[2]))
            self.statictext_name.SetLabel(unicode(objectinfo[3]))
            self.radiobox_alert.SetSelection(int(objectinfo[4]))
            self.textctrl_remark.ChangeValue(unicode(objectinfo[5]))
        else:
            self.object_panel.Enable(False)
            self.update_button.Enable(False)
            self.loaded_objectinfo = None
            self.statictext_mmsi.SetLabel('')
            self.statictext_imo.SetLabel('')
            self.statictext_cs.SetLabel('')
            self.statictext_name.SetLabel('')
            self.radiobox_alert.SetSelection(0)
            self.textctrl_remark.ChangeValue('')

    def OnObjectEdit(self, event):
        # Enable update button
        self.update_button.Enable(True)

    def OnObjectUpdate(self, event):
        # Check if variable exist, if not, return
        try:
            assert self.loaded_objectinfo
        except: return
        # Read in the object information to be saved
        mmsi = int(self.loaded_objectinfo[0])
        alert_box = self.radiobox_alert.GetSelection()
        remark_box = unicode(self.textctrl_remark.GetValue()).strip().replace(",",";")
        # Set alert
        if alert_box == 1:
            alert = 'A'
        elif alert_box == 2:
            alert = 'AS'
        else:
            alert = ''
        self.list_data[mmsi]['alert'] = alert
        # Set remark
        if remark_box.isspace():
            # Set remark to empty if it only contains whitespace
            self.list_data[mmsi]['remark'] = ''
        else:
            # Set remark
            self.list_data[mmsi]['remark'] = remark_box
        # Update the listctrl
        self.lc.OnUpdate()
        # Make main save and apply buttons enabled
        self.save_button.Enable(True)
        self.apply_button.Enable(True)
        # Make object update button disabled
        self.update_button.Enable(False)
        # Update the text ctrl
        self.textctrl_remark.ChangeValue(remark_box)

    def OnFilter(self, event):
        # Read values from the filter controls and set appropriate values in self.current_filter
        self.current_filter["filter_alerts"] = self.checkbox_filteralerts.GetValue()
        self.current_filter["filter_remarks"] = self.checkbox_filterremarks.GetValue()
        # If the text control contains text, set a query from the value
        # in the combobox and the text control. Replace dangerous char (,)
        # Else, set the filter query to empty.
        if len(self.textctrl_filtertext.GetValue()) > 0:
            self.current_filter["filter_column"] = self.combobox_filtercolumn.GetValue()
            self.current_filter["filter_query"] = self.textctrl_filtertext.GetValue().replace(",","").upper()
        else:
            self.current_filter["filter_column"] = ""
            self.current_filter["filter_query"] = ""
        # Update the listctrl
        self.lc.OnUpdate()

    def OnInsertNew(self, event):
        # Create a dialog with a textctrl, a checkbox and two buttons
        dlg = wx.Dialog(self, -1, _("Insert new MMSI number"), size=(280,130))
        wx.StaticText(dlg, -1, _("Fill in the MMSI number you want to insert:"), pos=(20,10), size=(260,30))
        textbox = wx.TextCtrl(dlg, -1, pos=(20,40), size=(150,-1))
        buttonsizer = dlg.CreateStdDialogButtonSizer(wx.CANCEL|wx.OK)
        buttonsizer.SetDimension(110, 80, 150, 40)
        textbox.SetFocus()
        # If user press OK, check that the textbox only contains digits,
        # check if the number already exists and if not, create object
        if dlg.ShowModal() == wx.ID_OK:
            new_mmsi = textbox.GetValue()
            if not new_mmsi.isdigit() or len(new_mmsi) > 9:
                dlg = wx.MessageDialog(self, _("Only nine digits are allowed in a MMSI number! Insert failed."), _("Error"), wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            elif int(new_mmsi) in self.list_data:
                dlg = wx.MessageDialog(self, _("The specified MMSI number already exists! Insert failed."), _("Error"), wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            else:
                self.list_data[int(new_mmsi)] = {}
            # Update list ctrl
            self.lc.OnUpdate()
            # Set active item
            self.lc.SetSelectedItem(int(new_mmsi))

    def OnApplyChanges(self, event):
        # Applies changes by sending them to MainThread
        alertdict = {}
        # Iterate over the data and pick out alerts and remarks
        for mmsi, entry in self.list_data.iteritems():
            # Get alert
            alert = entry.get('alert','')
            # Get remark
            remark = entry.get('remark','')
            # If neither remark or alert is set, don't save
            if len(alert) == 0 and len(remark) == 0:
                pass
            else:
                # For each entry split the data using ','
                alertdict[mmsi] = (alert, remark)
        # Send to main thread
        main_thread.put({'update_remarkdict': alertdict})
        # Make apply disabled
        self.apply_button.Enable(False)

    def OnSaveChanges(self, event):
        # Saves alerts and remarks to the loaded keyfile.
        # First, apply changes
        self.OnApplyChanges(None)
        # Save file
        remark_file = config['alert']['remarkfile']
        if config['alert'].as_bool('remarkfile_on'):
            # Saves remarks to a supplied file
            if len(remark_file) > 0:
                try:
                    # Open file
                    output = codecs.open(remark_file, 'w', encoding='cp1252')
                    # Loop over data
                    for mmsi, entry in self.list_data.iteritems():
                        # Get alert
                        alert = entry.get('alert','')
                        # Get remark
                        remark = entry.get('remark','')
                        # If neither remark or alert is set, don't save
                        if len(alert) == 0 and len(remark) == 0:
                            pass
                        else:
                            # For each entry split the data using ','
                            output.write(str(mmsi) + "," + alert + "," + remark + "\r\n")
                    output.close()
                    # Make save button and apply button disabled
                    self.save_button.Enable(False)
                    self.apply_button.Enable(False)
                except IOError, error:
                    dlg = wx.MessageDialog(self, _("Cannot save remark file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                    dlg.ShowModal()
                except Exception, error:
                    dlg = wx.MessageDialog(self, _("Cannot save remark file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                    dlg.ShowModal()
        else:
            dlg = wx.MessageDialog(self, _("Cannot save remark file. No remark file is loaded.") + "\n" + _("Edit the remark file settings and restart the program."), style=wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()

    def OnExportList(self, event):
        # Exports the current list view to a CSV-like file.
        exportdata = ""
        for mmsi, row in self.lc.itemDataMap.iteritems():
            alert = row[4]
            if alert == 0:
                alert = "No"
            elif alert == 1:
                alert = "Yes"
            elif alert == 2:
                alert = "Yes/Sound"
            exportdata += str(mmsi) + "," + str(row[1]) + "," + row[2] + "," + row[3] + "," + alert + "," + row[5] + "\n"
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

            # Set selected object to none
            self.selected = -1
            
            # Do inital update
            self.OnUpdate()
            # Do initial sorting on column 0, ascending order (1)
            self.SortListItems(0, 1)

            # Define events
            self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
            self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemDeselected)

        def OnItemSelected(self, event):
            # When an object is selected, extract the MMSI number and
            # put it in self.selected
            self.selected = self.itemIndexMap[event.m_itemIndex]
            # Populate the object box
            self.topparent.PopulateObject(self.itemDataMap[self.selected])

        def OnItemDeselected(self, event):
            # Deselect objects
            self.selected = -1
            # Depopulate the object box
            self.topparent.PopulateObject(None)

        def SetSelectedItem(self, mmsi):
            # Set selected
            self.selected = mmsi
            # Refresh ctrl
            self.SortListItems()
            # Populate the object box
            self.topparent.PopulateObject(self.itemDataMap[mmsi])

        def OnUpdate(self):
            # Set empty dict
            list_dict = {}

            # Get current filter settings
            filter = self.topparent.current_filter.copy()
            filter_alerts = filter.get('filter_alerts',False)
            filter_remarks = filter.get('filter_remarks',False)
            filter_column = filter.get('filter_column','')
            filter_query = filter.get('filter_query','')

            # Populate the list dict with data
            for mmsi, value in self.topparent.list_data.iteritems():
                # The row list has data according to list
                # [mmsi, imo, callsign, name, alert, remark]
                row =  [mmsi, None, None, None, None, None]
                row[1] = value.get('imo','')
                row[2] = value.get('callsign','')
                row[3] = value.get('name','')
                alert = value.get('alert','')
                if alert == 'A':
                    # Alert active
                    row[4] = 1
                elif alert == 'AS':
                    # Alert+sound active
                    row[4] = 2
                else:
                    # No alert
                    row[4] = 0
                row[5] = value.get('remark','')
                # See if we should add mmsi to dict
                # Filter on columns, alerts and remarks
                if filter_query and filter_column == 'MMSI' and unicode(mmsi).find(filter_query) == -1:
                    pass
                elif filter_query and filter_column == 'IMO' and unicode(row[1]).find(filter_query) == -1:
                    pass
                elif filter_query and filter_column == 'Callsign' and unicode(row[2]).find(filter_query) == -1:
                    pass
                elif filter_query and filter_column == 'Name' and unicode(row[3]).find(filter_query) == -1:
                    pass
                elif filter_alerts and not alert:
                    pass
                elif filter_remarks and not row[5]:
                    pass
                else:
                    list_dict[mmsi] = row

            # Set new ItemCount for the list ctrl if different from the current number
            nbrofobjects = len(list_dict)
            if self.GetItemCount() != nbrofobjects:
                self.SetItemCount(nbrofobjects)

            # Assign to variables for the virtual list ctrl
            self.itemDataMap = list_dict.copy()
            self.itemIndexMap = list_dict.keys()

            # If no objects in list, deselect all
            if nbrofobjects == 0:
                # Deselect objects
                self.selected = -1
                # Depopulate the object box
                self.topparent.PopulateObject(None)

            self.SortListItems()

        def OnGetItemText(self, item, col):
            # Return the text in item, col
            mmsi = self.itemIndexMap[item]
            string = self.itemDataMap[mmsi][col]
            # If column with alerts, map 0, 1 and 2 to text strings
            if col == 4:
                if string == '0': string = _("No")
                elif string == '1': string = _("Yes")
                elif string == '2': string = _("Yes/Sound")
            # If string is a Nonetype, replace with an empty string
            elif string == None:
                string = u''
            return unicode(string)

        def SortItems(self,sorter=cmp):
            items = list(self.itemDataMap.keys())
            items.sort(sorter)
            self.itemIndexMap = items

            # Workaround for updating listctrl on Windows
            if platform == 'nt':
                self.Refresh()

            # See if the previous selected row exists after the sort
            # If the MMSI number is found, set the new position as
            # selected and visible. If not found, deselect all objects
            # and depopulate the object box
            try:
                if self.selected in self.itemDataMap:
                    new_position = self.FindItem(-1, unicode(self.selected))
                    self.SetItemState(new_position, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
                    self.EnsureVisible(new_position)
                else:
                    for i in range(self.GetItemCount()):
                        self.SetItemState(i, 0, wx.LIST_STATE_SELECTED)
                        self.selected = -1
                        # Depopulate the object box
                        self.topparent.PopulateObject(None)
            except: pass

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
        self.pause = False
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

    def Update(self, data):
        updatetext = ''
        # Get data and add string to updatetext (make sure it's ascii)
        for line in data:
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

    def SetData(self, data):
        # If not paused, update
        if not self.pause:
            self.Update(data)

    def OnPause(self, event):
        # Set pause to togglebutton value
        self.pause = self.pausebutton.GetValue()

    def OnClose(self, event):
        self.Destroy()


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
        latmin = (self.latitude - latdegree) * 60
        longmin = (self.longitude - longdegree) * 60
        if self.latitude > 0:
            lat = u"%(deg)02d° %(min)07.4f'N" %{'deg': abs(latdegree), 'min': abs(latmin)}
        elif self.latitude < 0:
            lat = u"%(deg)02d° %(min)07.4f'S" %{'deg': abs(latdegree), 'min': abs(latmin)}
        if self.longitude > 0:
            long = u"%(deg)03d° %(min)07.4f'E" %{'deg': abs(longdegree), 'min': abs(longmin)}
        elif self.longitude < 0:
            long = u"%(deg)03d° %(min)07.4f'W" %{'deg': abs(longdegree), 'min': abs(longmin)}
        return lat, long

    @property
    def dms(self):
        # Return a human-readable DMS position
        latdegree = int(self.latitude)
        longdegree = int(self.longitude)
        latmin = (self.latitude - latdegree) * 60
        longmin = (self.longitude - longdegree) * 60
        latsec = (latmin - int(latmin)) * 60
        longsec = (longmin - int(longmin)) * 60
        if self.latitude > 0:
            lat = u"%(deg)02d° %(min)02d' %(sec)05.2f''N" %{'deg': abs(latdegree), 'min': abs(latmin), 'sec': abs(latsec)}
        elif self.latitude < 0:
            lat = u"%(deg)02d° %(min)02d' %(sec)05.2f''S" %{'deg': abs(latdegree), 'min': abs(latmin), 'sec': abs(latsec)}
        if self.longitude > 0:
            long = u"%(deg)03d° %(min)02d' %(sec)05.2f''E" %{'deg': abs(longdegree), 'min': abs(longmin), 'sec': abs(longsec)}
        elif self.longitude < 0:
            long = u"%(deg)03d° %(min)02d' %(sec)05.2f''W" %{'deg': abs(longdegree), 'min': abs(longmin), 'sec': abs(longsec)}
        return lat, long


class GUI(wx.App):
    def OnInit(self):
        self.frame = MainWindow(None, -1, 'AIS Logger')
        self.frame.Show(True)
        return True

    def GetFrame(self):
        return self.frame


class SerialThread:
    queue = Queue.Queue()
    # Define a queue for inserting data to send
    comqueue = Queue.Queue(500)

    def reader(self, name, s):
        # Set empty queueitem
        queueitem = ''
        # Start loop
        while True:
            # See if we shall stop
            try:
                queueitem = self.queue.get_nowait()
            # If no data in queue, sleep (prevents 100% CPU drain)
            except Queue.Empty:
                time.sleep(0.001)
            if queueitem == 'stop':
                s.close()
                break

            data = ''
            try:
                # Try to read data from serial port
                data = s.readline()
            except serial.SerialException:
                # On timeout or other errors, reopen port
                logging.debug("%(port)s timed out" %{'port': name}, exc_info=True)
                s.close()
                s.open()
                time.sleep(1)
                continue

            # If data contains raw data, pass it along
            try:
                if data[0] == '!' or data[0] == '$':
                    # Put it in CommHubThread's queue
                    comm_hub_thread.put([name,data])
            except IndexError:
                pass


    def server(self):
        # See if we should act as a serial server
        if config['serial_server'].as_bool('server_on'):
            port = config['serial_server']['port']
            baudrate = config['serial_server']['baudrate']
            rtscts = config['serial_server']['rtscts']
            xonxoff = config['serial_server']['xonxoff']
            try:
                serial_server = serial.Serial(port, baudrate, rtscts=rtscts, xonxoff=xonxoff, timeout=5)
            except serial.SerialException:
                logging.error("Could not open serial port %(port)s to act as a serial server" %{'port': port}, exc_info=True)
                return False
        else:
            # Server is not on, exit thread
            return False
        # Set empty queueitem
        queueitem = ''
        # Start loop
        while True:
            # See if we shall stop
            try:
                queueitem = self.queue.get_nowait()
            # If no data in queue, sleep (prevents 100% CPU drain)
            except Queue.Empty:
                time.sleep(0.1)
            if queueitem == 'stop':
                serial_server.flushOutput()
                serial_server.close()
                break
            # Do we have carrier?
            if serial_server.getCD():
                lines = []
                # Try to get data from queue
                while True:
                    try:
                        lines.append(self.comqueue.get_nowait())
                    except Queue.Empty:
                        break
                # Write to port
                try:
                    serial_server.write(''.join(lines))
                except serial.SerialException:
                    # Don't handle error, port should be open
                    pass
        
    def ReturnStats(self):
        return self.stats

    def put(self, item):
        self.queue.put(item)

    def put_send(self, item):
        try:
            self.comqueue.put_nowait(item)
        except Queue.Full:
            self.comqueue.get_nowait()
            self.comqueue.put_nowait(item)

    def start(self):
        try:
            # Fire off server thread
            server = threading.Thread(target=self.server)
            server.setDaemon(1)
            server.start()

            # See what reader threads we should start
            # Get all entries in config starting with 'serial'
            conf_ports = [ port for port in config.iterkeys()
                      if port.find('serial') != -1 ]
            # Iterate over ports and set port data
            for port_data in conf_ports:
                # Don't send serial data from server to itself...
                if port_data == 'serial_server':
                    continue
                # Get config
                conf = config[port_data]
                # Ok, set up port
                if 'serial_on' in conf and conf.as_bool('serial_on') and 'port' in conf:
                    # Try to get these values, if not, use standard
                    baudrate = 38400
                    rtscts = False
                    xonxoff = False
                    try:
                        # Baudrate
                        baudrate = conf.as_int('baudrate')
                        # RTS/CTS
                        rtscts = conf.as_bool('rtscts')
                        # XON/XOFF
                        xonxoff = conf.as_bool('xonxoff')
                    except: pass
                    # Create port name (the part after 'serial_')
                    portname = 'Serial port ' + port_data[7:] + ' (' + conf['port'] + ')'
                    # OK, try to open serial port, and add to serial_ports dict
                    try:
                        s = serial.Serial(conf['port'], baudrate, rtscts=rtscts, xonxoff=xonxoff, timeout=60)
                    except serial.SerialException:
                        logging.error("Could not open serial port %(port)s to read data from" %{'port': conf['port']}, exc_info=True)
                        continue
                    # Fire off reader thread
                    read = threading.Thread(target=self.reader, args=(portname, s))
                    read.setDaemon(1)
                    read.start()
            return True
        except:
            return False

    def stop(self):
        for i in range(0,100):
            self.put('stop')


class NetworkServerThread:
    # Define a queue for inserting data to send
    comqueue = Queue.Queue(500)

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
        try:
            server = SocketServer.ThreadingTCPServer((server_address, server_port), self.NetworkClientHandler)
            server.serve_forever()
        except:
            logging.error("Could not start the network server on address %(address)s and port %(port)s" %{'address': server_address, 'port': server_port}, exc_info=True)

    def feeder(self):
        # This function tracks each server thread and feeds them
        # with data from the queue
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
                # If someone wants to stop us, send stop to servers
                elif queueitem == 'stop':
                    for server in servers:
                        for i in range(0,100):
                            server.indata.append('stop')
                    break
            # If no data in queue, sleep (prevents 100% CPU drain)
            except Queue.Empty:
                time.sleep(0.05)
                continue
            # If something in queue, but not in form of a list, pass
            except IndexError: pass

            # If queueitem length is > 1, send message to socket
            if len(queueitem) > 1:
                for server in servers:
                    server.indata.append(queueitem)

    def start(self):
        try:
            feeder = threading.Thread(target=self.feeder, name='NetworkFeeder')
            feeder.setDaemon(1)
            feeder.start()
            server = threading.Thread(target=self.server, name='NetworkServer')
            server.setDaemon(1)
            server.start()
            return True
        except:
            return False

    def stop(self):
        for i in range(0,100):
            self.comqueue.put('stop')

    def put(self, item):
        try:
            self.comqueue.put_nowait(item)
        except Queue.Full:
            self.comqueue.get_nowait()
            self.comqueue.put_nowait(item)


class NetworkClientThread:
    queue = Queue.Queue()

    def client(self):
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
                logging.error("The connection to the network server on address %(address)s and port %(port)s timed out." %{'address': params[0], 'port': params[1]}, exc_info=True)
                continue

        while True:
            try:
                queueitem = self.queue.get_nowait()
            except: pass
            if queueitem == 'stop':
                try:
                    for con in connections.itervalues():
                        con.close()
                except: pass
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
                        comm_hub_thread.put([name,indata])

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
    raw_queue = Queue.Queue(500)
    stats = {}

    def runner(self):
        # The routing matrix consists of a dict with key 'input'
        # and value 'output list'
        routing_matrix = self.CreateRoutingMatrix()
        # The message parts dict has 'input' as key and
        # and a list of previous messages as value
        message_parts = {}
        # Empty incoming queue
        incoming_item = ''
        # Set the source to take position data from
        position_source = config['position']['use_position_from']
        if position_source.find('serial') != -1:
            try:
                position_source = 'Serial port ' + position_source[7:] + ' (' + config[position_source]['port'] + ')'
            except KeyError:
                logging.error("The serial port source used for GPS data (%(source)s) has no port associated with it" %{'source': position_source}, exc_info=True)
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

            # See if we got source in stats dict
            if not source in self.stats:
                self.stats[source] = {}
                self.stats[source]['received'] = 0
                self.stats[source]['parsed'] = 0

            # See if we should route the data
            outputs = routing_matrix.get(source,[])
            # Route the raw data
            for output in outputs:
                if output == 'serial':
                    serial_thread.put_send(data)
                elif output == 'network':
                    network_server_thread.put(data)

            # Check if message is split on several lines
            lineinfo = data.split(',')
            if lineinfo[0] == '!AIVDM':
                try:
                    nbr_of_lines = int(lineinfo[1])
                except: continue
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
                # Add one to stats dict
                self.stats[source]['received'] += 1
                # Parse data
                parser = dict(decode.telegramparser(data))
                # Set source in parser
                parser['source'] = source
                # See if we should send it, and if so: do it!
                if 'mmsi' in parser:
                    # Send data to main thread
                    main_thread.put(parser)
                    # Add to stats dict if we have decoded message
                    # (see if 'decoded' is True)
                    if parser.get('decoded',True):
                        self.stats[source]['parsed'] += 1
                # See if we have a position and if we should use it
                elif 'ownlatitude' in parser and 'ownlongitude' in parser:
                    if position_source == 'any' or position_source == source:
                        # Send data to main thread
                        main_thread.put(parser)
                        # Add to stats dict
                        self.stats[source]['parsed'] += 1

                # Send raw data to the Raw Window queue
                raw_mmsi = parser.get('mmsi','N/A')
                raw_message = parser.get('message','N/A')
                # Append source, message number, mmsi and data to rawdata
                raw = [source, raw_message, raw_mmsi, data]
                # Add the raw line to the raw queue
                try:
                    self.raw_queue.put_nowait(raw)
                except Queue.Full:
                    self.raw_queue.get_nowait()
                    self.raw_queue.put_nowait(raw)
            except: continue

    def CreateRoutingMatrix(self):
        # Creates a routing matrix dict from the set config options

        # Define the matrix
        matrix = {}

        # Get network config options
        clients_to_serial = config['network']['clients_to_serial']
        clients_to_server = config['network']['clients_to_server']

        # See if we only will have one in the send list
        if not type(clients_to_serial) == list:
            clients_to_serial = [clients_to_serial]
        if not type(clients_to_server) == list:
            clients_to_server = [clients_to_server]

        # Add to matrix
        for network_source in clients_to_serial:
            if network_source:
                send_list = matrix.get(network_source,[])
                send_list.append('serial')
                matrix[network_source] = send_list
        for network_source in clients_to_server:
            if network_source:
                send_list = matrix.get(network_source,[])
                send_list.append('network')
                matrix[network_source] = send_list

        # Get serial config options
        conf_ports = [ port for port in config.iterkeys()
                       if port.find('serial') != -1 ]

        # Iterate over configured ports
        for port in conf_ports:
            if 'port' in config[port]:
                # Try to create port name (the part after 'serial_')
                try:
                    portname = 'Serial port ' + port[7:] + ' (' + config[port]['port'] + ')'
                except: continue
                # Add to serial server send list
                try:
                    if config[port].as_bool('send_to_serial_server'):
                        send_list = matrix.get(portname,[])
                        send_list.append('serial')
                        matrix[portname] = send_list
                except: pass
                # Add to network server send list
                try:
                    if config[port].as_bool('send_to_network_server'):
                        send_list = matrix.get(portname,[])
                        send_list.append('network')
                        matrix[portname] = send_list
                except: pass

        return matrix

    def ReturnStats(self):
        return self.stats

    def ReturnRaw(self):
        # Return all data in the raw queue
        temp = []
        while True:
            try:
                temp.append(self.raw_queue.get_nowait())
            except Queue.Empty:
                break
        return temp
            
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

        # Define a dict to store the metadata hashes
        self.hashdict = {}

        # Define a dict to store own position data in
        self.ownposition = {}

        # Define a dict to store remarks/alerts in
        self.remarkdict = {}

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
                         'bearing', 'source', 'transponder_type'
                         'old')
        self.db_main.create(*self.dbfields)
        self.db_main.create_index('mmsi')

        # Create ID database
        self.db_iddb = pydblite.Base('dummy2')
        self.db_iddb.create('mmsi', 'imo', 'name', 'callsign')
        self.db_iddb.create_index('mmsi')

        # Try to load ID database
        self.loadiddb()

        # Try to load remark file
        self.loadremarkfile()

    def DbUpdate(self, incoming_packet):
        self.incoming_packet = incoming_packet
        incoming_mmsi = self.incoming_packet['mmsi']
        new = False

        # Fetch the current data in DB for MMSI (if exists)
        currentdata = self.db_main._mmsi[incoming_mmsi]

        # Define a dictionary to hold update data
        update_dict = {}

        # Check if report needs special treatment
        if 'message' in self.incoming_packet:
            message = self.incoming_packet['message']
            # If message type 1, 2 or 3 (Mobile Position Report) or
            # message type 5 (Static and Voyage Related Data):
            if message == '1' or message == '2' or message == '3' or message == '5':
                update_dict['transponder_type'] = 'A'
            # If message type S02 (Standard Position), S0E (Identification)
            # or S0F (Vessel Data):
            elif message == 'S02' or message == 'S0E' or message == 'S0F':
                update_dict['transponder_type'] = 'A'
            # If message type 4 (Base Station Report):
            elif message == '4':
                update_dict['transponder_type'] = 'base'
            # If message type 18, 19 or 24 (Class B messages):
            elif message == '18' or message == '19' or message == '24':
                update_dict['transponder_type'] = 'B'
            # Abort insertion if message type 9 (Special Position
            # Report), or type S0D and S11 (aviation reports)
            elif message == '9' or message == 'S0D' or message == 'S11':
                return None
            # FIXME: Should we just throw the rest of these messages?
            else:
                return None

        # If not currently in DB, add the mmsi number, creation time and MID code
        if len(currentdata) == 0:
            # Set variable to indicate a new object
            new = True
            # Map MMSI nbr to nation from MID list
            if 'mmsi' in self.incoming_packet and str(self.incoming_packet['mmsi'])[0:3] in mid:
                mid_code = mid[str(self.incoming_packet['mmsi'])[0:3]]
            else:
                mid_code = None
            self.db_main.insert(mmsi=incoming_mmsi,mid=mid_code,creationtime=self.incoming_packet['time'],
                                time=self.incoming_packet['time'])
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

        # Update the DB with new data
        self.db_main.update(main_record,old=False,**update_dict)

        # Return a dictionary of iddb
        if len(iddb) == 0:
            iddb = {}
        elif len(iddb) > 0:
            iddb = iddb[0]

        # Return the updated object and the iddb entry
        return self.db_main[main_record['__id__']], iddb, new

    def UpdateMsg(self, object_info, iddb, new=False, query=False):
        # See if we not should send message
        transponder_type = object_info.get('transponder_type',None)
        # See if we know the transponder type
        if transponder_type:
            # See if we display base stations
            if transponder_type == 'base' and not config['common'].as_bool('showbasestations'):
                return
            # See if we display Class B stations
            elif transponder_type == 'B' and not config['common'].as_bool('showclassbstations'):
                return
        else:
            # Unknown transponder type, don't display it
            return

        # See if we have enough updates
        if object_info['__version__'] < config['common'].as_int('showafterupdates'):
            return
        elif object_info['__version__'] == config['common'].as_int('showafterupdates') and query == False:
            new=True

        # Define the dict we're going to send
        message = {}

        # See if we need to use data from iddb
        if object_info['imo'] is None and 'imo' in iddb and iddb['imo'] != 'None':
            object_info['imo'] = str(iddb['imo']) + "'"
        if object_info['callsign'] is None and 'callsign' in iddb and iddb['callsign'] != 'None':
            object_info['callsign'] = iddb['callsign'] + "'"
        if object_info['name'] is None and 'name' in iddb and iddb['name'] != 'None':
            object_info['name'] = iddb['name'] + "'"

        # Match against set alerts
        remarks = self.remarkdict.get(object_info['mmsi'], [])
        if len(remarks) == 2 and remarks[0] == 'A':
            message['alert'] = True
            message['soundalert'] = False
        elif len(remarks) == 2 and remarks[0] == 'AS':
            message['alert'] = True
            # If new object, set sound alert, otherwise don't
            if new:
                message['soundalert'] = True
            else:
                message['soundalert'] = False
        else:
            message['alert'] = False
            message['soundalert'] = False

        # Match against set remarks
        if len(remarks) == 2 and len(remarks[1]):
            object_info['remark'] = remarks[1]
        else:
            object_info['remark'] = None

        # Make update, insert or query message
        if new:
            message['insert'] = object_info
        elif query:
            message['query'] = object_info
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
                        if not r['old'] and r['time'] < old_limit ]
        remove_objects = [ r for r in self.db_main
                           if r['time'] < remove_limit ]

        # Mark old as old in the DB and send messages
        for object in old_objects:
            self.db_main[object['__id__']]['old'] = True
            self.SendMsg({'old': {'mmsi': object['mmsi'], 'distance': object['distance']}})
        # Delete removable objects in db
        self.db_main.delete(remove_objects)
        # Send removal messages
        for object in remove_objects:
            self.SendMsg({'remove': object['mmsi']})

    def SendMsg(self, message):
        # Puts message in queue for consumers to get
        try:
            self.outgoing.put_nowait(message)
        except Queue.Full:
            self.outgoing.get_nowait()
            self.outgoing.put_nowait(message)

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
                incoming = self.queue.get_nowait()
            except:
                # Prevent CPU drain if nothing to do
                time.sleep(0.05)
                incoming = {}
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
            elif 'query' in incoming and incoming['query'] > 0:
                # Fetch the current data in DB for MMSI
                query = self.db_main._mmsi[incoming['query']]
                # Return a dictionary of query
                if len(query) == 0:
                    query = {}
                elif len(query) > 0:
                    query = query[0]
                # Fetch current data in IDDB
                iddb = self.db_iddb._mmsi[incoming['query']]
                # Return a dictionary of iddb
                if len(iddb) == 0:
                    iddb = {}
                elif len(iddb) > 0:
                    iddb = iddb[0]
                # Send the message
                self.UpdateMsg(query, iddb, query=True)
            # If the remark/alert dict is asked for
            elif 'remarkdict_query' in incoming:
                # Send a copy of the remark/alert dict
                self.SendMsg({'remarkdict': self.remarkdict.copy()})
            # If the IDDB is asked for
            elif 'iddb_query' in incoming:
                iddb = [ r for r in self.db_iddb ]
                # Send a copy of the remark/alert dict
                self.SendMsg({'iddb': iddb})
            # If we should update our remark/alert dict
            elif 'update_remarkdict' in incoming:
                self.remarkdict = incoming['update_remarkdict']
            # If we should pass on an error to the GUI
            elif 'error' in incoming:
                self.SendMsg(incoming)

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
                # If base station, see if we should log it
                if r['transponder_type'] == 'base' and not config['logging'].as_bool('logbasestations'):
                    continue
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
            # If base station, see if we should log it
            if r['transponder_type'] == 'base' and not config['logging'].as_bool('logbasestations'):
                continue
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
                self.db_iddb.insert(mmsi=int(ship[0]), imo=ship[1], name=ship[2], callsign=ship[3])
        except:
            logging.warning("Reading from IDDB file failed", exc_info=True)

    def loadremarkfile(self):
        # This function will try to read a remark/alert file, if defined in config
        path = config['alert']['remarkfile']
        if config['alert'].as_bool('remarkfile_on') and len(path) > 0:
            try:
                temp = {}
                file = open(path, 'rb')
                csv_reader = csv.reader(file)
                for row in csv_reader:
                    # Try to read line as ASCII/UTF-8, if error, try cp1252
                    try:
                        temp[int(row[0])] = (unicode(row[1]), unicode(row[2], 'utf-8'))
                    except:
                        temp[int(row[0])] = (unicode(row[1]), unicode(row[2], 'cp1252'))
                file.close()
                self.remarkdict = temp.copy()
            except:
                logging.warning("Reading from remark file failed", exc_info=True)

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


# Initialize thread classes
main_thread = MainThread()
comm_hub_thread = CommHubThread()
serial_thread = SerialThread()
network_server_thread = NetworkServerThread()
network_client_thread = NetworkClientThread()

# Set up loggers and logging handling
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

class GUIErrorHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        # Send to main thread
        main_thread.put({'error': self.format(record)})

if cmdlineoptions.nogui:
    # Send logging to sys.stderr instead of to the GUI
    handler = logging.StreamHandler()
    formatter = logging.Formatter('\n%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    # Set a logging handler for errors and send these to the GUI
    gui_handler = GUIErrorHandler()
    gui_formatter = logging.Formatter('%(levelname)s %(message)s')
    gui_handler.setFormatter(gui_formatter)
    gui_handler.setLevel(logging.ERROR)
    logger.addHandler(gui_handler)

# Set a logging handler for everything and save to file
file_handler = logging.FileHandler(filename='except.log')
file_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Start threads
main_thread.start()
comm_hub_thread.start()
serial_thread.start()
if config['network'].as_bool('server_on'):
    network_server_thread.start()
if config['network'].as_bool('client_on'):
    network_client_thread.start()

# Start the GUI
# Wait some time before initiating, to let the threads settle
time.sleep(0.2)
# See if we shall start the GUI
if cmdlineoptions.nogui:
    # Say hello
    print "\nAIS Logger running without GUI."
    print "Press any key to terminate program...\n"
    # Wait for key press
    raw_input()
    print "Terminating program..."
else:
    # Start GUI
    app = GUI(0)
    main_window = app.GetFrame()
    app.MainLoop()

# Stop threads
comm_hub_thread.stop()
serial_thread.stop()
network_server_thread.stop()
network_client_thread.stop()
main_thread.stop()

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
