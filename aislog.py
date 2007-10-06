#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# aislog.py (part of "AIS Logger")
# Simple AIS logging and display software
#
# Copyright (c) 2006-2007 Erik I.J. Olsson <olcai@users.sourceforge.net>
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

import sys, os, optparse, logging
import time, datetime
import threading, Queue, collections
import socket, SocketServer
import pickle
import md5

from pysqlite2 import dbapi2 as sqlite
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
columnsetup = {'mmsi': [_("MMSI"), 80], 'mid': [_("Nation"), 55], 'imo': [_("IMO"), 80], 'name': [_("Name"), 150], 'type': [_("Type nbr"), 45], 'typename': [_("Type"), 50], 'callsign': [_("CS"), 60], 'latitude': [_("Latitude"), 85], 'longitude': [_("Longitude"), 90], 'georef': [_("GEOREF"), 85], 'creationtime': [_("Created"), 75], 'time': [_("Updated"), 75], 'sog': [_("Speed"), 60], 'cog': [_("Course"), 60], 'heading': [_("Heading"), 70], 'destination': [_("Destination"), 150], 'eta': [_("ETA"), 80], 'length': [_("Length"), 45], 'width': [_("Width"), 45], 'draught': [_("Draught"), 90], 'rateofturn': [_("ROT"), 60], 'bit': [_("BIT"), 35], 'tamper': [_("Tamper"), 60], 'navstatus': [_("NavStatus"), 150], 'posacc': [_("PosAcc"), 55], 'bearing': [_("Bearing"), 65], 'distance': [_("Distance"), 70], 'remark': [_("Remark"), 150]}
# Set default keys and values
defaultconfig = {'common': {'refreshlisttimer': 10000, 'listmakegreytime': 600, 'deleteitemtime': 3600, 'listcolumns': 'mmsi, mid, name, typename, callsign, georef, creationtime, time, sog, cog, destination, navstatus, bearing, distance, remark', 'alertlistcolumns': 'mmsi, mid, name, typename, callsign, georef, creationtime, time, sog, cog, destination, navstatus, bearing, distance, remark'},
                 'logging': {'logging_on': False, 'logtime': '600', 'logfile': ''},
                 'iddb_logging': {'logging_on': False, 'logtime': '600', 'logfile': 'testiddb.db'},
                 'alert': {'alertfile_on': False, 'alertfile': '', 'remarkfile_on': False, 'remarkfile': '', 'alertsound_on': False, 'alertsoundfile': ''},
                 'position': {'override_on': False, 'latitude': '00;00.00;N', 'longitude': '000;00.00;E'},
                 'serial_a': {'serial_on': False, 'port': '0', 'baudrate': '9600', 'rtscts': '0', 'xonxoff': '0', 'repr_mode': '0'},
                 'serial_b': {'serial_on': False, 'port': '1', 'baudrate': '9600', 'rtscts': '0', 'xonxoff': '0', 'repr_mode': '0'},
                 'network': {'server_on': False, 'server_address': 'localhost', 'server_port': '23000', 'client_on': False, 'client_address': 'localhost', 'client_port': '23000'}}
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
config['position'].comments['latitude'] = ['Latitude in deg and min']
config['position'].comments['longitude'] = ['Longitude in deg and min']
config['network'].comments['server_on'] = ['Enable network server']
config['network'].comments['server_address'] = ['Server hostname or IP (server side)']
config['network'].comments['server_port'] = ['Server port (server side)']
config['network'].comments['client_on'] = ['Enable network client']
config['network'].comments['client_address'] = ['Server hostname or IP']
config['network'].comments['client_port'] = ['Server port']

# Log exceptions to file
logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(levelname)s %(message)s',filename='except.log',filemode='a')

# Define empty global variables
mid = {}
midfull = {}
typecode = {}
data = {}
owndata = {}
alertlist = []
alertstring = ''
alertstringsound = ''
rawdata = collections.deque()
networkdata = collections.deque()
remarkdict = {}

class MainWindow(wx.Frame):
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

        load = wx.MenuItem(file, 101, _("&Load snapshot file..."), _("Loads a snapshot file"))
        file.AppendItem(load)

        save = wx.MenuItem(file, 102, _("&Save snapshot file..."), _("Saves the data in memory to a snapshot file"))
        file.AppendItem(save)
        file.AppendSeparator()

        load_raw = wx.MenuItem(file, 103, _("Load &raw data...\tCtrl+R"), _("Loads a file containing raw (unparsed) messages"))
        file.AppendItem(load_raw)
        file.AppendSeparator()

        quit = wx.MenuItem(file, 104, _("E&xit\tCtrl+X"), _("Exit program"))
        file.AppendItem(quit)

        view = wx.Menu()
        showsplit = wx.MenuItem(view, 201, _("Show &alert view\tF8"), _("Shows or hides the alert view"))
        view.AppendItem(showsplit)

        refresh = wx.MenuItem(view, 202, _("&Refresh views\tF5"), _("Do a forced refresh of list views"))
        view.AppendItem(refresh)
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

        self.Bind(wx.EVT_MENU, self.OnLoadFile, id=101)
        self.Bind(wx.EVT_MENU, self.OnSaveFile, id=102)
        self.Bind(wx.EVT_MENU, self.OnLoadRawFile, id=103)
        self.Bind(wx.EVT_MENU, self.Quit, id=104)
        self.Bind(wx.EVT_MENU, self.OnShowSplit, id=201)
        self.Bind(wx.EVT_MENU, self.OnRefresh, id=202)
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

        # Timer for updating the status row
        self.timer = wx.Timer(self, -1)
        self.timer.Start(5000)
        wx.EVT_TIMER(self, -1, self.OnRefreshStatus)

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
        # Read a list with ship type codes from typkod.lst
        f = open('typkod.lst', 'r')
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
                    data[int(row[0])] = str(row[1])
                f.close()
                global remarkdict
                remarkdict = data.copy()
            except:
                dlg = wx.MessageDialog(self, _("Error, could not load the remark file!") + "\n\n" + str(sys.exc_info()[0]), style=wx.OK|wx.wx.ICON_ERROR)
                dlg.ShowModal()

    def OnRefreshStatus(self, event):
        # Update the status row
        # Fetch the total number of rows in the db
        query1 = execSQL(DbCmd(SqlCmd, [("SELECT mmsi FROM data", ())]))
        nritems = len(query1)
        # Fetch the greyed out rows in the db
        query2 = execSQL(DbCmd(SqlCmd, [("SELECT mmsi FROM data WHERE datetime(time) < datetime('now', 'localtime', '-%s seconds')" % config['common'].as_int('listmakegreytime'), ())]))
        nrgreyitems = len(query2)
        # Print strings
        if owndata.has_key('ownlatitude') and owndata.has_key('ownlongitude') and owndata.has_key('owngeoref'):
            # Create a nice latitude string
            latitude = owndata['ownlatitude']
            latitude =  latitude[1:3] + '° ' + latitude[3:5] + '.' + latitude[5:] + "' " + latitude[0:1]
            # Create a nice longitude string
            longitude = owndata['ownlongitude']
            longitude = longitude[1:4] + '° ' + longitude[4:6] + '.' + longitude[6:] + "' " + longitude[0:1]
            self.SetStatusText(_("Own position: ") + latitude + '  ' + longitude + ' - ' + owndata['owngeoref'], 0)
        self.SetStatusText(_("Total nbr of objects / old: ") + str(nritems) + ' / ' + str(nrgreyitems), 1)

    def OnShowRawdata(self, event):
        dlg = RawDataWindow(None, -1)
        dlg.Show()

    def OnStatistics(self, event):
        dlg = StatsWindow(None, -1)
        dlg.Show()

    def OnLoadFile(self, event):
        path = ''
        wcd = _("Snapshot files (*.pkl)|*.pkl|All files (*)|*")
        dir = os.getcwd()
        open_dlg = wx.FileDialog(self, message=_("Choose a file"), defaultDir=dir, defaultFile='', wildcard=wcd, style=wx.OPEN|wx.CHANGE_DIR)
        if open_dlg.ShowModal() == wx.ID_OK:
            path = open_dlg.GetPath()
        if len(path) > 0:
            try:
                file = open(path, 'rb')
                data = pickle.load(file)
                execSQL(DbCmd(SqlManyCmd, [
                    ("INSERT OR IGNORE INTO data (mmsi, mid, imo, name, type, typename, callsign, latitude, longitude, georef, creationtime, time, sog, cog, heading, destination, eta, length, width, draught, rateofturn, bit, tamper, navstatus, posacc, distance, bearing, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",(data))]))
                file.close()
                self.OnRefresh(event)
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

    def OnSaveFile(self, event):
        path = ''
        wcd = _("Snapshot files (*.pkl)|*.pkl|All files (*)|*")
        dir = os.getcwd()
        open_dlg = wx.FileDialog(self, message=_("Choose a file"), defaultDir=dir, defaultFile='datadump.pkl', wildcard=wcd, style=wx.SAVE|wx.CHANGE_DIR)
        if open_dlg.ShowModal() == wx.ID_OK:
            path = open_dlg.GetPath()
        if len(path) > 0:
            try:
                output = open(path, 'wb')
                query = execSQL(DbCmd(SqlCmd, [("SELECT * FROM data", ())]))
                pickle.dump(query,output)
                output.close()
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Could not save file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except UnicodeDecodeError, error:
                dlg = wx.MessageDialog(self, _("Could not save file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                open_dlg.Destroy()

    def OnLoadRawFile(self, event):
        path = ''
        wcd = _('All files (*)|*|Text files (*.txt)|*.txt')
        dir = os.getcwd()
        open_dlg = wx.FileDialog(self, message=_("Choose a file"), defaultDir=dir, defaultFile='', wildcard=wcd, style=wx.OPEN|wx.CHANGE_DIR)
        if open_dlg.ShowModal() == wx.ID_OK:
            path = open_dlg.GetPath()
        if len(path) > 0:
            try:
                self.rawfileloader(path)
                self.OnRefresh(event)
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Could not open file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except UnicodeDecodeError, error:
                dlg = wx.MessageDialog(self, _("Could not open file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                open_dlg.Destroy()

    def rawfileloader(self, filename):
        # Load raw data from file and queue it to the MainThread

        # Open file
        f=open(filename, 'r')

        num_lines = 0
        for line in f:
            num_lines += 1
        f.seek(0)

        # Create a progress dialog
        progress = wx.ProgressDialog(_("Loading file..."), _("Loading file..."), num_lines)

        # Step through each row in the file
        temp = ''
        cur_line = 0
        lastupdate_line = 0
        maint = MainThread()
        for line in f:

            # Check if message is split on several rows
            lineinfo = line.split(',')
            if lineinfo[0] == '!AIVDM' and int(lineinfo[1]) > 1:
                temp += line
                if len(temp.splitlines()) == int(lineinfo[1]):
                    line = decode.jointelegrams(temp)
                    temp = ''
                else:
                    continue

            # Use the result from telegramparser and put it in MainThread's queue
            try:
                parser = dict(decode.telegramparser(line))
                if len(parser) > 0:
                    parser['source'] = 'File'
                    maint.put(parser)
                # Update the progress dialog for each 100 rows
                cur_line += 1
                if lastupdate_line + 100 < cur_line:
                    progress.Update(cur_line)
                    lastupdate_line = cur_line
            except:
                cur_line += 1
                continue
        # Close file
        f.close()
        progress.Destroy()

    def Quit(self, event):
        self.Destroy()

    def OnShowSplit(self, event):
        self.splitwindows(self.spalert)

    def OnRefresh(self, event):
        self.splist.OnRefresh(event)
        self.spalert.OnRefresh(event)

    def OnAbout(self, event):
        aboutstring = 'AIS Logger\n(C) Erik I.J. Olsson 2006-2007\n\naislog.py\ndecode.py\nutil.py'
        dlg = wx.MessageDialog(self, aboutstring, _("About"), wx.OK|wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def OnSetAlerts(self, event):
        dlg = SetAlertsWindow(None, -1)
        dlg.Show()

    def OnSettings(self, event):
        dlg = SettingsWindow(None, -1)
        dlg.Show()


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

        # Define and start the timer that update the list at a defined interval
        self.timer = wx.Timer(self, -1)
        self.timer.Start(config['common'].as_int('refreshlisttimer'))
        wx.EVT_TIMER(self, -1, self.OnRefresh)
    
    def OnRefresh(self, event):
        # Update the listctrl 
        self.list.OnUpdate()


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

        # Define and start the timer that update the list at a defined interval
        self.timer = wx.Timer(self, -1)
        self.timer.Start(config['common'].as_int('refreshlisttimer'))
        wx.EVT_TIMER(self, -1, self.OnRefresh)
    
    def OnRefresh(self, event):
        # Define a default query (gives empty result)
        query = "mmsi='0'"
        # Check if alertstring has content, if so set query to it
        if len(alertstring) > 3: query = alertstring
        # Update the listctrl with the query
        self.list.OnUpdate(query)
        # Sound an alert for selected objects
        self.soundalert()
    
    def soundalert(self):
        # This function checks for new objects that matches the alertstringsound SQL-query and plays a sound if a new one appear. It will then mark the object with soundalerted = 1
        # If alertstringsound is larger than 3, run the query
        if len(alertstringsound) > 3:
            # Run a SELECT
            newitems = execSQL(DbCmd(SqlCmd, [("SELECT mmsi FROM data WHERE (%s) AND (soundalerted IS null)" % alertstringsound, ())]))
            # If the query returns one or more objects, play sound
            if len(newitems) > 0:
                sound = wx.Sound()
                if config['alert'].as_bool('alertsound_on') and len(config['alert']['alertsoundfile']) > 0 and sound.Create(config['alert']['alertsoundfile']):
                    sound.Play(wx.SOUND_ASYNC)
            # Update the object and set soundalerted = 1
            execSQL(DbCmd(SqlCmd, [("UPDATE data SET soundalerted='1' WHERE %s AND (soundalerted IS Null)" % alertstringsound, ())]))


class Distance:
    def distance(self, latitude, longitude):
        # Calculate lat/long in whole degrees from DM-format
        def floatlatitude(latitude):
            # Latitude
            wholedegree = float(latitude[1:3])
            decimaldegree = float((latitude[3:5] + '.' + latitude[5:])) * (1/60.)
            if latitude[0] == 'S':
                latitude = -(wholedegree + decimaldegree)
            elif latitude[0] == 'N':
                latitude = +(wholedegree + decimaldegree)
            return latitude
        def floatlongitude(longitude):
            # Longitude
            wholedegree = float(longitude[1:4])
            decimaldegree = float((longitude[4:6] + '.' + longitude[6:])) * (1/60.)
            if longitude[0] == 'W':
                longitude = -(wholedegree + decimaldegree)
            elif longitude[0] == 'E':
                longitude = +(wholedegree + decimaldegree)
            return longitude
        try:
            latitude = floatlatitude(latitude)
            longitude = floatlongitude(longitude)
            ownlatitude = floatlatitude(owndata['ownlatitude'])
            ownlongitude = floatlongitude(owndata['ownlongitude'])
            return VincentyDistance((ownlatitude, ownlongitude), (latitude, longitude)).all
        except: return


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
            self.columnlist.append(k[0]) # Append each SQL column name to a list

        # Use the mixins
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        listmix.ColumnSorterMixin.__init__(self, len(self.columnlist))

        # Do inital update
        self.OnUpdate(query="mmsi LIKE ''")
        # Do initial sorting on column 0, ascending order (1)
        self.SortListItems(0, 1)

        # Define events
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)

    def OnItemActivated(self, event):
        # Get the MMSI number associated with the row activated
        itemmmsi = self.itemIndexMap[event.m_itemIndex]
        # Open the detail window
        dlg = DetailWindow(None, -1, itemmmsi)
        dlg.Show()

    def OnUpdate(self, query="mmsi LIKE '%'"):
        # Check if a row is selected, if true, extract the mmsi
        selected_row = self.GetNextItem(-1, -1, wx.LIST_STATE_SELECTED)
        if selected_row != -1:
            selected_mmsi = self.itemIndexMap[selected_row]
        # Create a comma separated string from self.columnlist
        # If the remark column is in list, don't use it in
        columnlistcopy = self.columnlist[:]
        if 'remark' in self.columnlist:
            columnlistcopy.remove('remark')
        columnlist_string = ','.join([v for v in columnlistcopy])
        # Run the main SQL-query
        query_result = execSQL(DbCmd(SqlCmd, [("SELECT mmsi,time,%s FROM data WHERE %s" % (columnlist_string, query), ())]))
        # Run the IDDB query
        iddb_result = execSQL(DbCmd(SqlCmd, [("SELECT * FROM iddb WHERE (SELECT mmsi FROM data)",())]))
        # If alertstring has content, run the alert query and create a list from the result
        self.alertitems = []
        if len(alertstring) > 3:
            alertquery_result = execSQL(DbCmd(SqlCmd, [("SELECT mmsi FROM data WHERE %s" % alertstring, ())]))
            self.alertitems = [v[0] for v in alertquery_result]
        # Put the number of objects in a variable
        nrofobjects = len(query_result)
        # If the number of objects returned from the SQL-query doesn't match number currently in the listctrl, set new ItemCount.
        if self.GetItemCount() != nrofobjects:
            self.SetItemCount(nrofobjects)
        # Loop over query_result using function LoopQuery and put the result into data
        data = self.LoopQuery(query_result, iddb_result)
        # Create another dictionary and a list of keys from data
        self.itemDataMap = data
        self.itemIndexMap = data.keys()
        # Create a dictionary from query_result with mmsi as key and time as value
        self.itemOldMap = {}
        for v in query_result:
            self.itemOldMap[v[0]] = v[1]

        # Sort the data (including a refresh of the listctrl)
        self.SortListItems()

        # See if the previous selected row exists after the list update
        # If the mmsi is found, set the new position as selected
        try:
            new_position = self.FindItem(-1, unicode(selected_mmsi))
            self.SetItemState(new_position, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
        except: pass

    def LoopQuery(self, query_result, iddb_result):
        # Create an IDDB dictionary and map the result from iddb_result to it
        iddb_dict = {}
        for v in iddb_result:
            # For each list v in iddb_result, map the mmsi as key for iddb_dict and add imo, name and callsign
            iddb_dict[v[0]] = (v[1], v[2], v[3])
        # Create a dictionary, data, and populate it with data from the SQL-query. Use MMSI numbers as keys.
        data = {}
        for v in query_result:
            # Create a temporary list, r, to assign new values to 
            mmsi = v[0]
            r = list(v[2:])
            # Check for some special cases and edit r as needed
            # If imo, name or callsign is None, try to use data from iddb_dict
            if 'imo' in self.columnlist:
                pos = self.columnlist.index('imo')
                if r[pos] == None and mmsi in iddb_dict:
                    r[pos] = unicode(iddb_dict[mmsi][0]) + "'"
            if 'name' in self.columnlist:
                pos = self.columnlist.index('name')
                if r[pos] == None and mmsi in iddb_dict:
                    r[pos] = unicode(iddb_dict[mmsi][1]) + "'"
            if 'callsign' in self.columnlist:
                pos = self.columnlist.index('callsign')
                if r[pos] == None and mmsi in iddb_dict:
                    r[pos] = unicode(iddb_dict[mmsi][2]) + "'"
            # Other special cases
            if 'creationtime' in self.columnlist:
                pos = self.columnlist.index('creationtime')
                try: r[pos] = r[pos][11:]
                except: r[pos] = None
            if 'time' in self.columnlist:
                pos = self.columnlist.index('time')
                try: r[pos] = r[pos][11:]
                except: r[pos] = None
            if 'eta' in self.columnlist:
                pos = self.columnlist.index('eta')
                if r[pos] == '00002460': r[pos] = None
                else: r[pos] = r[pos]
            if 'bit' in self.columnlist:
                pos = self.columnlist.index('bit')
                if r[pos] == '0': r[pos] = unicode('OK')
                elif r[pos] == None: r[pos] = None
                else: r[pos] = unicode('Fel')
            if 'tamper' in self.columnlist:
                pos = self.columnlist.index('tamper')
                if r[pos] == '0': r[pos] = unicode('No')
                elif r[pos] == None: r[pos] = None
                else: r[pos] = unicode('YES')
            if 'posacc' in self.columnlist:
                pos = self.columnlist.index('posacc')
                if r[pos] == '0': r[pos] = unicode('Bad')
                elif r[pos] == None: r[pos] = None
                else: r[pos] = unicode('DGPS')
            # Very special case, the remark column
            if 'remark' in self.columnlist:
                pos = self.columnlist.index('remark')
                if remarkdict.has_key(mmsi):
                    r.insert(pos, str(remarkdict[mmsi]))
                else:
                    r.insert(pos, None)
            # Populate the dictionary
            data[mmsi] = r
        return data

    def OnGetItemText(self, item, col):
        # Return the text in item, col
        mmsi = self.itemIndexMap[item]
        string = self.itemDataMap[mmsi][col]
        # Workaround: the mmsi is an integer for sorting reasons, convert to unicode before displaying
        if 'mmsi' in self.columnlist:
            pos = self.columnlist.index('mmsi')
            if col == pos:
                string = unicode(string)
        # If string is a Nonetype, replace with an empty string
        if string == None:
            string = unicode('')
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
        try:
            # Create a datetime object from the time string
            lasttime = datetime.datetime(*time.strptime(self.itemOldMap[mmsi], "%Y-%m-%dT%H:%M:%S")[0:6])
            if lasttime + datetime.timedelta(0,config['common'].as_int('listmakegreytime')) < datetime.datetime.now():
                self.attr.SetTextColour("LIGHT GREY")
        except: pass
        return self.attr

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
        wx.StaticText(transponderdata_panel,-1,_("BIT: "),pos=(12,25),size=(150,16))
        wx.StaticText(transponderdata_panel,-1,_("Tamper: "),pos=(12,45),size=(150,16))
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
        self.text_bit = wx.StaticText(transponderdata_panel,-1,'',pos=(105,25),size=(185,16))
        self.text_tamper = wx.StaticText(transponderdata_panel,-1,'',pos=(105,45),size=(185,16))
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
                fulletatime = time.strftime(_("%d %B kl %H:%M"),etatime)
            except: fulletatime = itemdata[16]
            if fulletatime == '00002460': fulletatime = ''
            self.text_etatime.SetLabel(fulletatime)
        if itemdata[7]:
            latitude = str(itemdata[7])
            try: latitude =  latitude[1:3] + '° ' + latitude[3:5] + '.' + latitude[5:] + "' " + latitude[0:1]
            except: pass
            self.text_latitude.SetLabel(latitude)
        if itemdata[8]:
            longitude = str(itemdata[8])
            try: longitude = longitude[1:4] + '° ' + longitude[4:6] + '.' + longitude[6:] + "' " + longitude[0:1]
            except: pass
            self.text_longitude.SetLabel(longitude)
        if itemdata[9]: self.text_georef.SetLabel(itemdata[9])
        if itemdata[12]: self.text_sog.SetLabel(str(itemdata[12])+' kn')
        if itemdata[13]: self.text_cog.SetLabel(str(itemdata[13])+'°')
        if itemdata[14]: self.text_heading.SetLabel(str(itemdata[14])+'°')
        if itemdata[20]: self.text_rateofturn.SetLabel(str(itemdata[20])+' °/m')
        # Set transponder data
        if itemdata[21]:
            if itemdata[21] == '0': bit = _("OK")
            else: bit = _("Error")
            self.text_bit.SetLabel(bit)
        if itemdata[22]:
            if itemdata[22] == '0': tamper = _("No")
            else: tamper = _("YES")
            self.text_tamper.SetLabel(tamper)
        if itemdata[23]:
            self.text_navstatus.SetLabel(itemdata[23])
        if itemdata[24]:
            if itemdata[24] == '0': posacc = _("Good / GPS")
            else: posacc = _("Very good / DGPS")
            self.text_posacc.SetLabel(posacc)
        # Set local info
        if itemdata[25] and itemdata[26]:
            self.text_bearing.SetLabel(str(itemdata[26])+'°')
            self.text_distance.SetLabel(str(itemdata[25])+' km')
        if itemdata[10]:
            try: creationtime = itemdata[10].replace('T', _(" kl "))
            except: creationtime = ''
            self.text_creationtime.SetLabel(creationtime)
        if itemdata[11]:
            try: lasttime = itemdata[11].replace('T', _(" kl "))
            except: lasttime = ''
            self.text_time.SetLabel(lasttime)
        if itemdata[28]:
            self.text_updates.SetLabel(str(itemdata[28]))
        if itemdata[27]:
            self.text_source.SetLabel(str(itemdata[27]))
        # Set remark text
        if remarkdict.has_key(int(itemdata[0])): self.text_remark.SetLabel(str(remarkdict[int(itemdata[0])]))

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
        horizon_panel.SetMinSize((280,-1))
        input_panel = wx.Panel(self, -1)
        input_panel.SetMinSize((250,-1))
        # Create static boxes
        box_objects = wx.StaticBox(objects_panel,-1,_(" Objects "))
        box_input = wx.StaticBox(input_panel,-1,_(" Input "))
        box_horizon = wx.StaticBox(horizon_panel,-1,_(" Radio Horizon (calculated) "))
        
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
        input_panel_left = wx.Panel(input_panel)
        input_panel_right = wx.Panel(input_panel)
        wx.StaticText(input_panel_left,-1,_("Serial Port A received:"),pos=(-1,0))
        wx.StaticText(input_panel_left,-1,_("Serial Port A parsed:"),pos=(-1,20))
        wx.StaticText(input_panel_left,-1,_("Serial Port B received:"),pos=(-1,60))
        wx.StaticText(input_panel_left,-1,_("Serial Port B parsed:"),pos=(-1,80))
        wx.StaticText(input_panel_left,-1,_("Network received:"),pos=(-1,120))
        wx.StaticText(input_panel_left,-1,_("Network parsed:"),pos=(-1,140))
        self.text_input_ser_a_r = wx.StaticText(input_panel_right,-1,'',pos=(-1,0))
        self.text_input_ser_a_p = wx.StaticText(input_panel_right,-1,'',pos=(-1,20))
        self.text_input_ser_b_r = wx.StaticText(input_panel_right,-1,'',pos=(-1,60))
        self.text_input_ser_b_p = wx.StaticText(input_panel_right,-1,'',pos=(-1,80))
        self.text_input_net_r = wx.StaticText(input_panel_right,-1,'',pos=(-1,120))
        self.text_input_net_p = wx.StaticText(input_panel_right,-1,'',pos=(-1,140))
        input_sizer = wx.StaticBoxSizer(box_input, wx.HORIZONTAL)
        input_sizer.AddSpacer(5)
        input_sizer.Add(input_panel_left)
        input_sizer.AddSpacer(10)
        input_sizer.Add(input_panel_right, wx.EXPAND)
        input_panel.SetSizer(input_sizer)

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
        sizer2.Add(horizon_panel, 0)
        sizer1.Add(sizer2)
        sizer1.AddSpacer(5)
        sizer1.Add(input_panel, 0, wx.EXPAND)
        mainsizer.Add(sizer1)
        mainsizer.AddSpacer((0,10))
        sizer_button.Add(closebutton, 0)
        mainsizer.Add(sizer_button, flag=wx.ALIGN_RIGHT)
        self.SetSizerAndFit(mainsizer)

        # Update the initial data
        self.OnUpdate('')

        # Timer for updating the window
        self.timer = wx.Timer(self, -1)
        self.timer.Start(2000)
        wx.EVT_TIMER(self, -1, self.OnUpdate)

    def OnUpdate(self, event):
        horizon = self.CalcHorizon()
        input_stats = GetStats()
        self.text_object_nbr.SetLabel(str(horizon[0]))
        self.text_object_grey_nbr.SetLabel(str(horizon[1]))
        self.text_object_distance_nbr.SetLabel(str(horizon[2]))
        self.text_horizon_min.SetLabel(str(horizon[3]) + " km")
        self.text_horizon_max.SetLabel(str(horizon[4]) + " km")
        self.text_horizon_mean.SetLabel(str(horizon[5]) + " km")
        self.text_horizon_median.SetLabel(str(horizon[6]) + " km")
        if input_stats.has_key('serial_a'):
            self.text_input_ser_a_r.SetLabel(str(input_stats['serial_a']['received']))
            self.text_input_ser_a_p.SetLabel(str(input_stats['serial_a']['parsed']))
        if input_stats.has_key('serial_b'):
            self.text_input_ser_b_r.SetLabel(str(input_stats['serial_b']['received']))
            self.text_input_ser_b_p.SetLabel(str(input_stats['serial_b']['parsed']))
        if input_stats.has_key('network'):
            self.text_input_net_r.SetLabel(str(input_stats['network']['received']))
            self.text_input_net_p.SetLabel(str(input_stats['network']['parsed']))

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
        #innerlist_panel = wx.Panel(list_panel, -1, pos=(10,15), size=(670,250))
        self.lc = self.List(list_panel, self)
        #listsizer = wx.StaticBoxSizer(list_staticbox, wx.VERTICAL)
        #listsizer.Add(self.lc, 1, wx.EXPAND)
        #innerlist_panel.SetSizer(listsizer)

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
        remark_newstate = self.textctrl_remark.GetValue()
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
        # If user press OK, check that the textbox only contains digits, check if the number already exists
        # and if not, update either the alertlist or the remarkdict
        if dlg.ShowModal() == wx.ID_OK:
            if not textbox.GetValue().isdigit() or len(textbox.GetValue()) > 9:
                dlg = wx.MessageDialog(self, _("Only nine digits are allowed in a MMSI number! Insert failed."), _("Error"), wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            elif self.lc.CheckForMmsi(int(textbox.GetValue())):
                dlg = wx.MessageDialog(self, _("The specified MMSI number already exists! Insert failed."), _("Error"), wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            elif radiobox.GetSelection() == 0:
                query = "mmsi LIKE '" + unicode(textbox.GetValue()) + "'"
                alertlist.append((query, 0, 0))
            elif radiobox.GetSelection() == 1:
                remarkdict[int(textbox.GetValue())] = ""
            # Update list ctrl
            self.lc.OnUpdate()
            # Set active item
            self.lc.SetActiveItem(textbox.GetValue())

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
                output = open(file, 'w')
                for entry in remarkdict.iteritems():
                    # For each entry split the data using ','
                    mmsi = str(entry[0])
                    remark = entry[1]
                    output.write(mmsi + "," + remark + "\n")
                output.close()
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Cannot save remark file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except UnicodeDecodeError, error:
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
                output = open(file, 'w')
                output.write(exportdata)
                output.close()
            except IOError, error:
                dlg = wx.MessageDialog(self, _("Cannot save file") + "\n" + str(error), style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            except UnicodeDecodeError, error:
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
                    remark = str(remarkdict[mmsi])
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
                    list_dict[mmsi] = [mmsi, imo, callsign, name, alert, remark]
                
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
            # See if the previous selected row exists after list update
            new_position = self.FindItem(-1, str(mmsi))
            # If the mmsi is found, set the new position as selected and visible
            if new_position != -1:
                self.SetItemState(new_position, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
                self.EnsureVisible(new_position)
                return True
            else: return False

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
            if col == 4:
                if string == 0: string = _("No")
                elif string == 1: string = _("Yes")
                elif string == 2: string = _("Yes/Sound")
            # If string is a Nonetype, replace with an empty string
            if string == None:
                string = unicode('')
            if type(string) == int:
                string = unicode(string)
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
        wx.StaticBox(porta_panel, -1, _(" Settings for a primary serial port "), pos=(10,5), size=(450,190))
        self.porta_serialon = wx.CheckBox(porta_panel, -1, _("Activate reading from the primary serial port"), pos=(20,28))
        wx.StaticText(porta_panel, -1, _("Port: "), pos=(20,60))
        self.porta_port = wx.ComboBox(porta_panel, -1, pos=(110,60), size=(100,-1), choices=('Com1', 'Com2'))
        wx.StaticText(porta_panel, -1, _("Speed: "), pos=(20,95))
        self.porta_speed = wx.ComboBox(porta_panel, -1, pos=(110,90), size=(100,-1), choices=('9600', '38400'))
        self.porta_xonxoff = wx.CheckBox(porta_panel, -1, _("Software flow control:"), pos=(20,130), style=wx.ALIGN_RIGHT)
        self.porta_rtscts = wx.CheckBox(porta_panel, -1, _("RTS/CTS flow control:"), pos=(20,160), style=wx.ALIGN_RIGHT)
        # Port B config
        portb_panel = wx.Panel(serial_panel, -1)
        wx.StaticBox(portb_panel, -1, _(" Settings for a secondary serial port "), pos=(10,-1), size=(450,190))
        self.portb_serialon = wx.CheckBox(portb_panel, -1, _("Activate reading from the secondary serial port"), pos=(20,28))
        wx.StaticText(portb_panel, -1, _("Port: "), pos=(20,60))
        self.portb_port = wx.ComboBox(portb_panel, -1, pos=(110,60), size=(100,-1), choices=('Com1', 'Com2'))
        wx.StaticText(portb_panel, -1, _("Speed: "), pos=(20,95))
        self.portb_speed = wx.ComboBox(portb_panel, -1, pos=(110,90), size=(100,-1), choices=('9600', '38400'))
        self.portb_xonxoff = wx.CheckBox(portb_panel, -1, _("Software flow control:"), pos=(20,130), style=wx.ALIGN_RIGHT)
        self.portb_rtscts = wx.CheckBox(portb_panel, -1, _("RTS/CTS flow control:"), pos=(20,160), style=wx.ALIGN_RIGHT)
        # Add panels to main sizer
        serial_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        serial_panel_sizer.Add(porta_panel, 0)
        serial_panel_sizer.Add(portb_panel, 0)
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

    def OnSave(self, event):
        dlg = wx.MessageDialog(self, _("This function is not implemented yet"), 'FIXME', wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def OnApply(self, event):
        self.OnSave(0)

    def OnAbort(self, event):
        self.Destroy()


class RawDataWindow(wx.Dialog):
    def __init__(self, parent, id):
        wx.Dialog.__init__(self, parent, id, title=_("Raw data"))#, size=(618,395))
        panel = wx.Panel(self, -1)
        wx.StaticBox(panel,-1,_(" Incoming raw data "),pos=(3,5),size=(615,340))
        # Create the textbox
        self.textbox = wx.TextCtrl(panel,-1,pos=(15,25),size=(595,305),style=(wx.TE_MULTILINE | wx.TE_READONLY))
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
            updatetext += unicode(rawdata.popleft(), 'ascii' , 'replace')
        # Write updatetext from the top of the box
        self.textbox.SetInsertionPoint(0)
        self.textbox.WriteText(updatetext)
        # Get total number of charchters in box
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
            for x in range(self.querylist.GetItemCount(), -1, -1):
                if self.querylist.GetItemState(x, wx.LIST_STATE_SELECTED):
                    # Retreive the string itself from queryitems
                    querystring = str(self.queryitems[x][0])
                    # Create a dialog with a textctrl, a checkbox and two buttons
                    dlg = wx.Dialog(self, -1, _("Edit alert"), size=(400,130))
                    textbox = wx.TextCtrl(dlg, -1, querystring, pos=(10,10), size=(380,70), style=wx.TE_MULTILINE)
                    alertbox = wx.CheckBox(dlg, -1, _("A&ctivate sound alert"), pos=(30, 95))
                    buttonsizer = dlg.CreateStdDialogButtonSizer(wx.CANCEL|wx.OK)
                    buttonsizer.SetDimension(210, 85, 180, 40)
                    # Make the checkbox checked if the value is set in queryitems
                    if self.queryitems[x][1] == 1: alertbox.SetValue(True)
                    # If user press OK, update the queryitems list and update the AdvancedAlertWindow
                    if dlg.ShowModal() == wx.ID_OK:
                        if alertbox.GetValue():
                            alertstate = 1
                        else:
                            alertstate = 0
                        self.queryitems[x] = (textbox.GetValue(), alertstate, 0)
                        self.UpdateValues()
        # If more than one item selected, show error
        elif self.querylist.GetSelectedItemCount() > 1:
            dlg = wx.MessageDialog(self, _("You can only edit one query at a time!"), _("Error"), wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()

    def OnRemove(self, event):
        # Remove the object that is selected in list
        # Step backwards in list and check if each object is selected
        for x in range(self.querylist.GetItemCount(), -1, -1):
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
        open_dlg = wx.FileDialog(self, message=_("Choose a file"), defaultDir=dir, defaultFile='', wildcard=wcd, style=wx.OPEN|wx.CHANGE_DIR)
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
        open_dlg = wx.FileDialog(self, message=_("Choose a file"), defaultDir=dir, defaultFile='alert.alt', wildcard=wcd, style=wx.SAVE|wx.CHANGE_DIR)
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
    stats = {"received": 0, "parsed": 0}

    def reader(self, port, baudrate, rtscts, xonxoff, repr_mode):
        # Define serial port connection
        s = serial.Serial(port, baudrate, rtscts=rtscts, xonxoff=xonxoff)
        maint = MainThread()
        serialt = SerialThread()
        queueitem = ''
        temp = ''
        seq_temp = 10
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

            # Check if message is split on several lines
            lineinfo = indata.split(',')
            nbr_of_lines = int(lineinfo[1])
            line_nbr = int(lineinfo[2])
            line_seq_id = int(lineinfo[3])
            # If message is split, check that they belong together
            if lineinfo[0] == '!AIVDM' and nbr_of_lines > 1:
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
                else:
                    continue

            # Set the telegramparser result in dict parser and queue it
            try:
                parser = dict(decode.telegramparser(indata))
                if len(parser) > 0:
                    # Put in NetworkServer's queue
                    if parser.has_key('mmsi'):
                        networkdata.append(parser)
                        while len(networkdata) > 500:
                            networkdata.popleft()
                    # Set source in parser as serial
                    parser['source'] = "Serial port " + port
                    maint.put(parser)
                    self.stats["parsed"] += 1
            except: continue

    def ReturnStats(self):
        return self.stats

    def put(self, item):
        self.queue.put(item)

    def start(self, openport):
        if openport == 'serial_a':
            port = config['serial_a']['port']
            baudrate = config['serial_a'].as_int('baudrate')
            rtscts = config['serial_a'].as_int('rtscts')
            xonxoff = config['serial_a'].as_int('xonxoff')
            repr_mode = config['serial_a'].as_int('repr_mode')
        elif openport == 'serial_b':
            port = config['serial_b']['port']
            baudrate = config['serial_b'].as_int('baudrate')
            rtscts = config['serial_b'].as_int('rtscts')
            xonxoff = config['serial_b'].as_int('xonxoff')
            repr_mode = config['serial_b'].as_int('repr_mode')
        try:
            r = threading.Thread(target=self.reader, args=(port, baudrate, rtscts, xonxoff, repr_mode))
            r.setDaemon(1)
            r.start()
            return True
        except:
            return False

    def stop(self):
        for i in range(0,10):
            self.put('stop')


class NetworkServerThread:
    class NetworkClientHandler(SocketServer.BaseRequestHandler):
        def handle(self):
            message = ''
            while True:
                try:
                    # Pop message from queue
                    message = networkdata.popleft()
                except: pass
                if message == 'stop': break
                # message has a length greater than 1, pickle message and send it to socket
                if len(message) > 1:
                    pickled_message = pickle.dumps(message.copy())
                    self.request.send(pickled_message)
            self.request.close()


    def server(self):
        # Spawn network servers as clients request connection
        server_address = config['network']['server_address']
        server_port = config['network'].as_int('server_port')
        server = SocketServer.ThreadingTCPServer((server_address, server_port), self.NetworkClientHandler)
        server.serve_forever()

    def start(self):
        try:
            r = threading.Thread(target=self.server, name='NetworkServer')
            r.setDaemon(1)
            r.start()
            return True
        except:
            return False

    def stop(self):
        for i in range(0,100):
            networkdata.append('stop')


class NetworkClientThread:
    queue = Queue.Queue()

    def client(self):
        queueitem = ''
        data = ''
        message = {}
        maint = MainThread()
        client_address = config['network']['client_address']
        client_port = config['network'].as_int('client_port')
        socketobj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketobj.connect((client_address, client_port))
        while True:
            try:
                queueitem = self.queue.get_nowait()
            except: pass
            if queueitem == 'stop':
                socketobj.close()
                break
            try:
                # Try to read data from socket and unpickle it
                data = socketobj.recv(1024)
                message = pickle.loads(data)
            except: continue
            # Set source in parser as network
            message['source'] = 'Network'
            # Put message in MainThread's queue
            maint.put(message)

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


class MainThread:
    queue = Queue.Queue()
    hashdict = {}

    def updater(self):
        execSQL(DbCmd(ConnectCmd, ":memory:"))
        execSQL(DbCmd(SqlCmd, [
            ("create table data (mmsi PRIMARY KEY, mid, imo, name, type, typename, callsign, latitude, longitude, georef, creationtime, time, sog, cog, heading, destination, eta, length, width, draught, rateofturn, bit, tamper, navstatus, posacc, distance, bearing, source, updates, soundalerted);",()),
            ("create table iddb (mmsi PRIMARY KEY, imo, name, callsign);",()),
            ("CREATE TRIGGER update_iddb AFTER UPDATE OF imo ON data BEGIN INSERT OR IGNORE INTO iddb (mmsi) VALUES (new.mmsi); UPDATE iddb SET imo=new.imo,name=new.name,callsign=new.callsign WHERE mmsi=new.mmsi; END;",())]))
        lastcleartime = time.time()
        lastlogtime = time.time()
        lastiddblogtime = time.time()
        parser = {}
        self.loadiddb()
        while True:
            # Store the result from telegramparser in dict parser
            try:
                parser = self.queue.get()
            except: pass
            if parser == 'stop': break
            # Check that parser contains a MMSI number
            if parser.has_key('mmsi') and len(parser['mmsi']) > 1:
                # Calculate position in GEOREF
                if parser.has_key('latitude') and parser.has_key('longitude') and len(parser['latitude']) == 9 and len(parser['longitude']) == 10:
                    try:
                        parser['georef'] = georef(parser['latitude'],parser['longitude'])
                    except: pass
                # Map MMSI nbr to nation from MID list
                if 'mmsi' in parser and mid.has_key(parser['mmsi'][0:3]):
                    parser['mid'] = mid[parser['mmsi'][0:3]]
                # Map type nbr to type name from list
                if 'type' in parser and len(parser['type']) > 0 and typecode.has_key(parser['type']):
                    parser['typename'] = typecode[parser['type']]
                # Check if user has set a fixed manual position, and if so, use it...
                if config['position'].as_bool('override_on'):
                    config_lat = config['position']['latitude'].split(';')
                    config_long = config['position']['longitude'].split(';')                   
                    ownlatitude = config_lat[2] + (config_lat[0] + config_lat[1].split('.')[0] + config_lat[1].split('.')[1]).ljust(8, '0')
                    ownlongitude = config_long[2] + (config_long[0] + config_long[1].split('.')[0] + config_long[1].split('.')[1]).ljust(9, '0')
                    try:
                        owngeoref = georef(ownlatitude,ownlongitude)
                    except:
                        owngeoref = ""
                    v = {'ownlatitude': ownlatitude, 'ownlongitude': ownlongitude, 'owngeoref': owngeoref}
                    owndata.update(v)
                # Calculate bearing and distance to object
                if owndata.has_key('ownlatitude') and owndata.has_key('ownlongitude') and 'latitude' in parser and 'longitude' in parser:
                    try:
                        dist = Distance().distance(parser['latitude'],parser['longitude'])
                        parser['distance'] = str(round(dist['km'], 1)).zfill(5)
                        parser['bearing'] = str(round(dist['bearing'], 1)).zfill(5)
                    except: pass
                # Append data to dbexp and dbvalues
                dbexp = []
                dbvalues = []
                if 'mid' in parser: dbexp.append('mid'); dbvalues.append(parser['mid'])
                if 'imo' in parser: dbexp.append('imo'); dbvalues.append(parser['imo'])
                if 'name' in parser: dbexp.append('name'); dbvalues.append(parser['name'])
                if 'type' in parser: dbexp.append('type'); dbvalues.append(parser['type'])
                if 'typename' in parser: dbexp.append('typename'); dbvalues.append(parser['typename'])
                if 'callsign' in parser: dbexp.append('callsign'); dbvalues.append(parser['callsign'])
                if 'latitude' in parser: dbexp.append('latitude'); dbvalues.append(parser['latitude'])
                if 'longitude' in parser: dbexp.append('longitude'); dbvalues.append(parser['longitude'])
                if 'georef' in parser: dbexp.append('georef'); dbvalues.append(parser['georef'])
                if 'sog' in parser: dbexp.append('sog'); dbvalues.append(parser['sog'])
                if 'cog' in parser: dbexp.append('cog'); dbvalues.append(parser['cog'])
                if 'heading' in parser: dbexp.append('heading'); dbvalues.append(parser['heading'])
                if 'destination' in parser: dbexp.append('destination'); dbvalues.append(parser['destination'])
                if 'eta' in parser: dbexp.append('eta'); dbvalues.append(parser['eta'])
                if 'length' in parser: dbexp.append('length'); dbvalues.append(parser['length'])
                if 'width' in parser: dbexp.append('width'); dbvalues.append(parser['width'])
                if 'draught' in parser: dbexp.append('draught'); dbvalues.append(parser['draught'])
                if 'rateofturn' in parser: dbexp.append('rateofturn'); dbvalues.append(parser['rateofturn'])
                if 'bit' in parser: dbexp.append('bit'); dbvalues.append(parser['bit'])
                if 'tamper' in parser: dbexp.append('tamper'); dbvalues.append(parser['tamper'])
                if 'navstatus' in parser: dbexp.append('navstatus'); dbvalues.append(parser['navstatus'])
                if 'posacc' in parser: dbexp.append('posacc'); dbvalues.append(parser['posacc'])
                if 'time' in parser: dbexp.append('time'); dbvalues.append(parser['time'])
                if 'distance' in parser: dbexp.append('distance'); dbvalues.append(parser['distance'])
                if 'bearing' in parser: dbexp.append('bearing'); dbvalues.append(parser['bearing'])
                if 'source' in parser: dbexp.append('source'); dbvalues.append(parser['source'])
                # Create an expression from the column=value pairs from aboce
                dbexpression = ','.join(['''%s="%s"''' % (e, v) for e,v in zip(dbexp, dbvalues)])
                # Create or ignore a row from the MMSI key and update this row with current values
                execSQL(DbCmd(SqlCmd, [
                    ("INSERT OR IGNORE INTO data (mmsi, creationtime, updates) VALUES (%s,'%s', 0)" % (int(parser['mmsi']), parser['time']),()),
                    ("UPDATE data SET %s,updates=updates+1 WHERE mmsi=%s" % (dbexpression, int(parser['mmsi'])),())]))
            elif parser.has_key('ownlatitude') and parser.has_key('ownlongitude') and len(parser['ownlatitude']) == 9 and len(parser['ownlongitude']) == 10 and not config['position'].as_bool('override_on'):
                ownlatitude = parser['ownlatitude']
                ownlongitude = parser['ownlongitude']
                try:
                    owngeoref = georef(ownlatitude,ownlongitude)
                except:
                    owngeoref = ""
                v = {'ownlatitude': ownlatitude, 'ownlongitude': ownlongitude, 'owngeoref': owngeoref}
                owndata.update(v)

            # Remove object if last update time is above threshold
            if lastcleartime + 10 < time.time():
                execSQL(DbCmd(SqlCmd, [("DELETE FROM data WHERE datetime(time, '+%s seconds') < datetime('now', 'localtime')" % config['common'].as_int('deleteitemtime'),())]))
                lastcleartime = time.time()
                        
            # Initiate logging to disk of log time is above threshold
            if config['logging'].as_bool('logging_on'):
                if config['logging'].as_int('logtime') == 0: continue
                elif lastlogtime + config['logging'].as_int('logtime') < time.time():
                    self.dblog()
                    lastlogtime = time.time()

            # Initiate iddb logging if current time is > (lastlogtime + logtime)
            if config['iddb_logging'].as_bool('logging_on'):
                if config['iddb_logging'].as_int('logtime') == 0: continue
                elif lastiddblogtime + config['iddb_logging'].as_int('logtime') < time.time():
                    self.iddblog()
                    lastiddblogtime = time.time()

        execSQL(DbCmd(StopCmd))

    def dblog(self):
        # Make a query for the metadata, but return only rows where imo has a value
        metainfoquery = execSQL(DbCmd(SqlCmd, [("SELECT mmsi, imo, name, type, callsign, destination, eta, length, width FROM data WHERE imo NOTNULL",())]))
        newhashdict = {}
        updatemmsilist = []
        updatemmsiquery = "mmsi == NULL"
        for i in metainfoquery:
            mmsi = i[0]
            infostring = str(i[1:]) # Take everything in list except mmsi and make a string of it
            newhashdict[mmsi] = md5.new(infostring).digest() # Make a dict like {mmsi: MD5-hash}
        for i in newhashdict:
            if self.hashdict.has_key(i): # Check if the mmsi was around at last update
                if cmp(newhashdict[i], self.hashdict[i]) != 0: # Compare the hash, if different: add to update list
                    updatemmsilist.append(i)
            else: # New mmsi, add to update list
                updatemmsilist.append(i)
        # Set self.hashdict to the new hash dict
        self.hashdict = newhashdict
        # Create a querystring for metadataquery
        if len(updatemmsilist) > 0: updatemmsiquery = 'mmsi == ' + str(updatemmsilist[0])
        if len(updatemmsilist) > 1:
            for i in updatemmsilist[1:]: updatemmsiquery += ' OR mmsi == ' + str(i)
        # Query the memory db
        positionquery = execSQL(DbCmd(SqlCmd, [("SELECT time, mmsi, latitude, longitude, georef, sog, cog FROM data WHERE datetime(time, '+%s seconds') > datetime('now', 'localtime') ORDER BY time" % config['logging'].as_int('logtime'),())]))
        metadataquery = execSQL(DbCmd(SqlCmd, [("SELECT time, mmsi, imo, name, type, callsign, destination, eta, length, width FROM data WHERE %s ORDER BY time" % updatemmsiquery,())]))
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
        iddbquery = execSQL(DbCmd(SqlCmd, [("SELECT mmsi, imo, name, callsign FROM iddb",())]))
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
            execSQL(DbCmd(SqlManyCmd, [("INSERT INTO iddb (mmsi, imo, name, callsign) VALUES (?, ?, ?, ?);", (iddb_data))]))
        except:
            logging.warning("Reading from IDDB file failed", exc_info=True)

    def put(self, item):
        self.queue.put(item)

    def start(self):
        try:
            r = threading.Thread(target=self.updater)
            r.setDaemon(1)
            r.start()
            return True
        except:
            return False

    def stop(self):
        self.put('stop')


# Start threads
MainThread().start()
if config['serial_a'].as_bool('serial_on'):
    seriala = SerialThread()
    seriala.start('serial_a')
if config['serial_b'].as_bool('serial_on'):
    serialb = SerialThread()
    serialb.start('serial_b')
if config['network'].as_bool('server_on'):
    NetworkServerThread().start()
if config['network'].as_bool('client_on'):
    NetworkClientThread().start()

# Function for getting statistics from the various threads
def GetStats():
    stats = {}
    try:
        stats['serial_a'] = seriala.ReturnStats()
    except: pass
    try:
        stats['serial_b'] = serialb.ReturnStats()
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
