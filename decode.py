#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# decode.py (part of "AIS Logger")
# Simple AIS sentence parsing
#
# This parser has support for both standard !AIVDM type messages and for
# $PAIS type messages received from SAAB TransponderTech transponders
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

import binascii
import datetime
import math
import decimal
import unittest

def jointelegrams(inputstring):
    # Creates an AIVDM-message combined of several sentences with a
    # row break between each sentence
    telegrams = inputstring.splitlines()
    joinedphrase = ''
    # Check the checksum of each sentence and join them
    for x in telegrams[:]:
        if not checksum(x):
            return
        phrase = x.split(',')
        joinedphrase = joinedphrase + phrase[5]
    # Create a full AIVDM-sentence
    fullphrase = '!AIVDM,1,1,,,' + joinedphrase + ',0*'
    # Create a checksum
    csum = hex(makechecksum(fullphrase))
    # Combine the sentence and the checksum and create a single
    # AIVDM-message
    fullphrase = fullphrase + csum[2:]
    return fullphrase

def telegramparser(inputstring):
    # This function decodes certain types of messages from the
    # receiver and returns the interesting data as a dictionary where
    # each key describes the information of each message part

    # Observe that the navigational status is set as an integer
    # according to ITU-R M.1371, and is thus converted for SAAB
    # PAIS messages to these values

    # For each value where we have a N/A-state None is returned

    # Convert the raw input string to a list of separated values
    telegram = inputstring.split(',')

    # Depending on what sentence the list contains, extract the
    # information and create a dictionary with the MMSI number as key
    # and a value which contain another dictionary with the actual
    # data

    # If the sentence follows the SAAB TransponderTech standard:
    if telegram[0] == '$PAIS':
        # Check the checksum
        #if not checksum(inputstring):
        #    return

        # Get the source MMSI number
        mmsi = int(telegram[2],16)

        # Extract the message type number and prefix the number with
        # an 'S' to indicate SAAB messages
        message = 'S' + telegram[1]

        # Get current computer time to timestamp messages
        timestamp = datetime.datetime.now()

        # If the sentence contains 02 - AIS Standard Position:
        if message == 'S02':
            # Rate of turn in degrees/minute from -127 to +127 where 128=N/A
            rateofturn = int(telegram[3], 16)
            if rateofturn >=0 and rateofturn <128: # Turning right
                # Convert between ROTais and ROTind
                rateofturn = int(math.pow((rateofturn/4.733), 2))
                if rateofturn > 720:
                    rateofturn = 720 # Full
            elif rateofturn >128 and rateofturn <=255: # Turning left
                rateofturn = 256 - rateofturn
                # Convert between ROTais and ROTind
                rateofturn = -int(math.pow((rateofturn/4.733), 2))
                if rateofturn < -720:
                    rateofturn = -720 # Full
            else:
                rateofturn = None # N/A
            # Navigation status converted to ITU-R M.1371 standard
            navstatus = telegram[4]
            if navstatus == '1': navstatus = 0 # Under Way
            elif navstatus == '2': navstatus = 2 # Not Under Command
            elif navstatus == '3': navstatus = 3 # Restricted Manoeuvrability
            elif navstatus == '4': navstatus = 1 # At Anchor
            elif navstatus == '5': navstatus = None # (MAYDAY?) sets to N/A
            else: navstatus = None # N/A
            # Latitude in decimal degrees (DD)
            latitude = calclatitude(tobin(int(telegram[5],16),27))
            # Longitude in decimal degrees (DD)
            longitude = calclongitude(tobin(int(telegram[6],16),28))
            # Speed over ground in 1/10 knots
            sog = decimal.Decimal(int(telegram[7],16)) / 10
            if sog > decimal.Decimal("102.2"):
                sog = None # N/A
            # Course over ground in 1/10 degrees where 0=360
            cog = decimal.Decimal(int(telegram[8],16)) / 10
            if cog > 360: # 360 and above means 360=N/A
                cog = None
            # Heading in whole degrees between 0-359 and 511=N/A
            heading = int(telegram[9],16)
            if heading > 359:
                heading = None # N/A
            # Position accuracy where 0=bad and 1=good/DGPS
            posacc = int(telegram[11])
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'rot': rateofturn,
                    'navstatus': navstatus,
                    'latitude': latitude,
                    'longitude': longitude,
                    'sog': sog,
                    'cog': cog,
                    'heading': heading,
                    'posacc': posacc,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 04 - Addressed Text Telegram:
        elif message == 'S04':
            # Content of message in ASCII (replace any " with ')
            content = telegram[4].replace('''"''',"'")
            # Destination MMSI number
            to_mmsi = int(telegram[5],16)
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'content': content,
                    'to_mmsi': to_mmsi,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 06 - Broadcast Text Telegram:
        elif message == 'S06':
            # Content of message in ASCII (replace any " with ')
            content = str(telegram[4]).replace('''"''',"'")
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'content': content,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 07 - Addressed Binary Telegram:
        elif message == 'S07':
            # Binary data payload
            payload = []
            for char in telegram[4]:
                payload.append(tobin(int(char,16),4))
            payload = ''.join(payload)
            # Destination MMSI number
            to_mmsi = int(telegram[5],16)
            # Application ID (Designated Area Code, DAC) + (Function
            # Identification, FI)
            appid = []
            for char in telegram[7]:
                appid.append(tobin(int(char,16),4))
            appid = ''.join(appid)
            dac = int(appid[0:10],2)
            fi = int(appid[10:16],2)
            # Try to decode message payload
            decoded = binaryparser(dac,fi,payload)
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'to_mmsi': to_mmsi,
                    'dac': dac,
                    'fi': fi,
                    'decoded': decoded,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 09 - Broadcast Binary Telegram:
        elif message == 'S09':
            # Binary data payload
            payload = []
            for char in telegram[4]:
                payload.append(tobin(int(char,16),4))
            payload = ''.join(payload)
            # Application ID (Designated Area Code, DAC) + (Function
            # Identification, FI)
            appid = []
            for char in telegram[6]:
                appid.append(tobin(int(char,16),4))
            appid = ''.join(appid)
            dac = int(appid[0:10],2)
            fi = int(appid[10:16],2)
            # Try to decode message payload
            decoded = binaryparser(dac,fi,payload)
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'dac': dac,
                    'fi': fi,
                    'decoded': decoded,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 0D - Standard Position,
        # aviation, or message 11 - SAR Standard Position
        elif message == 'S0D' or 'S11':
            # Latitude in decimal degrees (DD)
            latitude = calclatitude(tobin(int(telegram[3],16),27))
            # Longitude in decimal degrees (DD)
            longitude = calclongitude(tobin(int(telegram[4],16),28))
            # Speed over ground in knots
            sog = int(telegram[5],16)
            if sog > 1022:
                sog = None # N/A
            # Course over ground in 1/10 degrees where 0=360
            cog = decimal.Decimal(int(telegram[6],16)) / 10
            if cog > 360: # 360 and above means 360=N/A
                cog = None
            # Altitude in meters, 4095=N/A
            altitude = int(telegram[7],16)
            if altitude == 4095:
                altitude = None # N/A
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'altitude': altitude,
                    'sog': sog,
                    'latitude': latitude,
                    'longitude': longitude,
                    'cog': cog,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains 0E - Identification Data:
        elif message == 'S0E':
            # Name, removes the characters @, ' ' and "
            name = telegram[3].strip('''@ ''').replace('''"''',"'")
            # Callsign, removes the characters @, ' ' and "
            callsign = telegram[4].strip('''@ ''').replace('''"''',"'")
            # IMO number where 00000000=N/A
            imo = int(telegram[5],16)
            if imo == 0:
                imo = None
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'name': name,
                    'callsign': callsign,
                    'imo': imo,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains 0F - Vessel Data:
        elif message == 'S0F':
            # Ship type, a two-digit code where 00=N/A
            type = int(telegram[3],16)
            if type == 0:
                type = None # N/A
            # Draught in 1/10 meters, where 0.0 = N/A
            draught = decimal.Decimal(int(telegram[4],16)) / 10
            if draught == 0:
                draught = None
            # Calculate ship width and length in meters from
            # antenna position in hex
            # Convert hex->int->bits
            ant_binnumber = tobin(int(telegram[5],16),count=30)
            # Add integers from the two parts to form length
            length = int(ant_binnumber[12:21],2) + int(ant_binnumber[21:30],2)
            # Add integers from the two parts to form width
            width = int(ant_binnumber[0:6],2) + int(ant_binnumber[6:12],2)
            # Destination, removes the characters @, ' ' and "
            destination = telegram[6].strip('''@ ''').replace('''"''',"'")
            # Received estimated time of arrival in format
            # month-day-hour-minute: MMDDHHMM where 00000000=N/A
            eta = telegram[8]
            if eta == '00000000':
                eta = None
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'type': type,
                    'draught': draught,
                    'length': length,
                    'width': width,
                    'destination': destination,
                    'eta': eta,
                    'time': timestamp,
                    'message': message}

        else:
            # If we don't decode the message, at least return message type
            return {'mmsi': mmsi, 'time': timestamp, 'message': message, 'decoded': False}


    # If the sentence follows the ITU-R M.1371 standard:
    if telegram[0] == '!AIVDM':
        # Check the checksum
        if not checksum(inputstring):
            return

        # Convert the 6-bit string to a binary string
        bindata = sixtobin(telegram[5])

        # Extract the message type number
        message = str(int(bindata[0:6],2))

        # Get the source MMSI number
        mmsi = int(bindata[8:38],2)

        # Get current computer time to timestamp messages
        timestamp = datetime.datetime.now()

        # If the sentence contains message 1, 2 or 3 - Position Report:
        if message == '1' or message == '2' or message == '3':
            # Navigation status according to ITU-R M.1371
            navstatus = int(bindata[38:42],2)
            if navstatus == 0: navstatus = 0 # Under Way
            elif navstatus == 1: navstatus = 1 # At Anchor
            elif navstatus == 2: navstatus = 2 # Not Under Command
            elif navstatus == 3: navstatus = 3 # Restricted Manoeuvrability
            elif navstatus == 4: navstatus = 4 # Constrained by her draught
            elif navstatus == 5: navstatus = 5 # Moored
            elif navstatus == 6: navstatus = 6 # Aground
            elif navstatus == 7: navstatus = 7 # Engaged in Fishing
            elif navstatus == 8: navstatus = 8 # Under way sailing
            else: navstatus = None # N/A
            # Rate of turn in degrees/minute from -127 to +127 where 128=N/A
            sign_rateofturn = int(bindata[42])
            rateofturn = int(bindata[43:50],2)
            if rateofturn > 126:
                rateofturn = None # N/A
            elif sign_rateofturn and rateofturn > 1:
                # Turning left
                rateofturn = 128 - rateofturn
                # Convert between ROTais and ROTind
                rateofturn = -int(math.pow((rateofturn/4.733), 2))
                if rateofturn < -720:
                    rateofturn = -720 # Full
            else:
                # Turning right
                # Convert between ROTais and ROTind
                rateofturn = int(math.pow((rateofturn/4.733), 2))
                if rateofturn > 720:
                    rateofturn = 720 # Full
            # Speed over ground in 1/10 knots
            sog = decimal.Decimal(int(bindata[50:60],2)) / 10
            if sog > decimal.Decimal("102.2"):
                sog = None # N/A
            # Position accuracy where 0=bad and 1=good/DGPS
            posacc = int(bindata[60],2)
            # Longitude in decimal degrees (DD)
            longitude = calclongitude(bindata[61:89])
            # Latitude in decimal degrees (DD)
            latitude = calclatitude(bindata[89:116])
            # Course over ground in 1/10 degrees between 0-359
            cog = decimal.Decimal(int(bindata[116:128],2)) / 10
            if cog > 360: # 360 and above means 360=N/A
                cog = None
            # Heading in whole degrees between 0-359 and 511=N/A
            heading = int(bindata[128:137],2)
            if heading > 359:
                heading = None # N/A
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'rot': rateofturn,
                    'navstatus': navstatus,
                    'latitude': latitude,
                    'longitude': longitude,
                    'sog': sog,
                    'cog': cog,
                    'heading': heading,
                    'posacc': posacc,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 4 - Base Station Report:
        elif message == '4':
            # Bits 38-78 contains current station time in UTC
            try:
                station_time = datetime.datetime(int(bindata[38:52],2),
                                                 int(bindata[52:56],2),
                                                 int(bindata[56:61],2),
                                                 int(bindata[61:66],2),
                                                 int(bindata[66:72],2),
                                                 int(bindata[72:78],2))
            except ValueError:
                station_time = None # N/A
            # Position accuracy where 0=bad and 1=good/DGPS
            posacc = int(bindata[78],2)
            # Longitude in decimal degrees (DD)
            longitude = calclongitude(bindata[79:107])
            # Latitude in decimal degrees (DD)
            latitude = calclatitude(bindata[107:134])
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'station_time': station_time,
                    'posacc': posacc,
                    'latitude': latitude,
                    'longitude': longitude,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 5 - Ship Static and Voyage
        # Related Data:
        elif message == '5' and int(bindata[38:40],2) == 0:
            # IMO number where 00000000=N/A
            imo = int(bindata[40:70],2)
            if imo == 0:
                imo = None # N/A
            # Callsign, removes the characters @, ' ' and "
            callsign = bintoascii(bindata[70:112]).strip('''@ ''').replace('''"''',"'")
            # Name, removes the characters @, ' ' and "
            name = bintoascii(bindata[112:232]).strip('''@ ''').replace('''"''',"'")
            # Ship type, a two-digit code where 00=N/A
            type = int(bindata[232:240],2)
            if type == 0:
                type = None # N/A
            # Ship length calculated from antenna position
            length = (int(bindata[240:249],2) + int(bindata[249:258],2))
            # Ship width calculated from antenna position
            width = (int(bindata[258:264],2) + int(bindata[264:270],2))
            # Received estimated time of arrival in format
            # month-day-hour-minute: MMDDHHMM where 00000000=N/A
            eta = (str(int(bindata[274:278],2)).zfill(2) +
                  str(int(bindata[278:283],2)).zfill(2) +
                  str(int(bindata[283:288],2)).zfill(2) +
                  str(int(bindata[288:294],2)).zfill(2))
            if eta == '00000000':
                eta = None
            # Draught in 1/10 meters, where 0.0 == N/A
            draught = decimal.Decimal(int(bindata[294:302],2)) / 10
            if draught == 0:
                draught = None
            # Destination, removes the characters @, ' ' and "
            destination = bintoascii(bindata[302:422]).strip('''@ ''').replace('''"''',"'")
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'imo': imo,
                    'callsign': callsign,
                    'name': name,
                    'type': type,
                    'length': length,
                    'width': width,
                    'eta': eta,
                    'destination': destination,
                    'draught': draught,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 6 - Addressed Binary Message:
        elif message == '6':
            # Sequence number
            sequence = int(bindata[38:40],2)
            # Destination MMSI number
            to_mmsi = int(bindata[40:70],2)
            # Application ID (Designated Area Code, DAC) + (Function
            # Identification, FI)
            dac = int(bindata[72:82],2)
            fi = int(bindata[82:88],2)
            # Binary data payload
            payload = bindata[88:1048]
            # Try to decode message payload
            decoded = binaryparser(dac,fi,payload)
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'sequence': sequence,
                    'to_mmsi': to_mmsi,
                    'dac': dac,
                    'fi': fi,
                    'decoded': decoded,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 8 - Binary Broadcast Message:
        elif message == '8':
            # Application ID (Designated Area Code, DAC) + (Function
            # Identification, FI)
            dac = int(bindata[40:50],2)
            fi = int(bindata[50:56],2)
            # Binary data payload
            payload = bindata[56:1008]
            # Try to decode message payload
            decoded = binaryparser(dac,fi,payload)
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'dac': dac,
                    'fi': fi,
                    'decoded': decoded,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 9 - SAR Aircraft position
        # report:
        elif message == '9':
            # Altitude in meters, 4095=N/A, 4094=>4094
            altitude = int(bindata[38:50],2)
            if altitude == 4095:
                altitude = None # N/A
            # Speed over ground in knots, 1023=N/A, 1022=>1022
            sog = int(bindata[50:60],2)
            if sog == 1023:
                sog = None # N/A
            # Position accuracy where 0=bad and 1=good/DGPS
            posacc = int(bindata[60],2)
            # Longitude in decimal degrees (DD)
            longitude = calclongitude(bindata[61:89])
            # Latitude in decimal degrees (DD)
            latitude = calclatitude(bindata[89:116])
            # Course over ground in 1/10 degrees between 0-359
            cog = decimal.Decimal(int(bindata[116:128],2)) / 10
            if cog > 360: # 360 and above means 360=N/A
                cog = None
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'altitude': altitude,
                    'sog': sog,
                    'posacc': posacc,
                    'latitude': latitude,
                    'longitude': longitude,
                    'cog': cog,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 12 - Addressed safety
        # related message:
        elif message == '12':
            # Sequence number
            sequence = int(bindata[38:40],2)
            # Destination MMSI number
            to_mmsi = int(bindata[40:70],2)
            # Content of message in ASCII (replace any " with ')
            content = bintoascii(bindata[72:1008]).replace('''"''',"'")
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'sequence': sequence,
                    'to_mmsi': to_mmsi,
                    'content': content,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 14 - Safety related
        # Broadcast Message:
        elif message == '14':
            # Content of message in ASCII (replace any " with ')
            content = bintoascii(bindata[40:1008]).replace('''"''',"'")
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'content': content,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 18 - Standard Class B CS
        # Position Report:
        elif message == '18':
            # Speed over ground in 1/10 knots
            sog = decimal.Decimal(int(bindata[46:56],2)) / 10
            if sog > decimal.Decimal("102.2"):
                sog = None # N/A
            # Position accuracy where 0=bad and 1=good/DGPS
            posacc = int(bindata[56],2)
            # Longitude in decimal degrees (DD)
            longitude = calclongitude(bindata[57:85])
            # Latitude in decimal degrees (DD)
            latitude = calclatitude(bindata[85:112])
            # Course over ground in 1/10 degrees between 0-359
            cog = decimal.Decimal(int(bindata[112:124],2)) / 10
            if cog > 360: # 360 and above means 360=N/A
                cog = None
            # Heading in whole degrees between 0-359 and 511=N/A
            heading = int(bindata[124:133],2)
            if heading > 359:
                heading = None # N/A
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'latitude': latitude,
                    'longitude': longitude,
                    'sog': sog,
                    'cog': cog,
                    'heading': heading,
                    'posacc': posacc,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 19 - Extended Class B
        # Equipment Position Report:
        elif message == '19':
            # Speed over ground in 1/10 knots
            sog = decimal.Decimal(int(bindata[46:56],2)) / 10
            if sog > decimal.Decimal("102.2"):
                sog = None # N/A
            # Position accuracy where 0=bad and 1=good/DGPS
            posacc = int(bindata[56],2)
            # Longitude in decimal degrees (DD)
            longitude = calclongitude(bindata[57:85])
            # Latitude in decimal degrees (DD)
            latitude = calclatitude(bindata[85:112])
            # Course over ground in 1/10 degrees between 0-359
            cog = decimal.Decimal(int(bindata[112:124],2)) / 10
            if cog > 360: # 360 and above means 360=N/A
                cog = None
            # Heading in whole degrees between 0-359 and 511=N/A
            heading = int(bindata[124:133],2)
            if heading > 359:
                heading = None # N/A
            # Name, removes the characters @, ' ' and "
            name = bintoascii(bindata[143:263]).strip('''@ ''').replace('''"''',"'")
            # Ship type, a two-digit code where 00=N/A
            type = int(bindata[263:271],2)
            if type == 0:
                type = None # N/A
            # Ship length calculated from antenna position
            length = (int(bindata[271:280],2) + int(bindata[280:289],2))
            # Ship width calculated from antenna position
            width = (int(bindata[289:295],2) + int(bindata[295:301],2))
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'latitude': latitude,
                    'longitude': longitude,
                    'sog': sog,
                    'cog': cog,
                    'heading': heading,
                    'posacc': posacc,
                    'name': name,
                    'type': type,
                    'length': length,
                    'width': width,
                    'time': timestamp,
                    'message': message}

        # If the sentence contains message 24 - Class B CS Static Data
        # Report:
        elif message == '24':
            # See if it is message part A or B
            if int(bindata[38:40]) == 0: # Part A
                # Name, removes the characters @, ' ' and "
                name = bintoascii(bindata[40:160]).strip('''@ ''').replace('''"''',"'")
                # Return a dictionary with descriptive keys
                return {'mmsi': mmsi,
                        'name': name,
                        'time': timestamp,
                        'message': message}
            else: # Part B
                # Ship type, a two-digit code where 00=N/A
                type = int(bindata[40:48],2)
                if type == 0:
                    type = None # N/A
                # Vendor ID, removes the characters @, ' ' and "
                vendor = bintoascii(bindata[48:90]).strip('''@ ''').replace('''"''',"'")
                # Callsign, removes the characters @, ' ' and "
                callsign = bintoascii(bindata[90:132]).strip('''@ ''').replace('''"''',"'")
                # Ship length calculated from antenna position
                length = (int(bindata[132:141],2) + int(bindata[141:150],2))
                # Ship width calculated from antenna position
                width = (int(bindata[150:156],2) + int(bindata[156:162],2))
                # Return a dictionary with descriptive keys
                return {'mmsi': mmsi,
                        'type': type,
                        'vendor': vendor,
                        'callsign': callsign,
                        'length': length,
                        'width': width,
                        'time': timestamp,
                        'message': message}

        else:
            # If we don't decode the message, at least return message type
            return {'mmsi': mmsi, 'time': timestamp, 'message': message, 'decoded': False}


    # If the sentence contains NMEA-compliant position data (from own GPS):
    if telegram[0] == '$GPGGA':
        # Check the checksum
        if not checksum(inputstring):
            return
        # Latitude
        degree = int(telegram[2][0:2])
        minutes = decimal.Decimal(telegram[2][2:9])
        if telegram[3] == 'N':
            latitude = degree + (minutes / 60)
        else:
            latitude = -(degree + (minutes / 60))
        latitude = latitude.quantize(decimal.Decimal('1E-6'))
        # Longitude
        degree = int(telegram[4][0:3])
        minutes = decimal.Decimal(telegram[4][3:10])
        if telegram[5] == 'E':
            longitude = degree + (minutes / 60)
        else:
            longitude = -(degree + (minutes / 60))
        longitude = longitude.quantize(decimal.Decimal('1E-6'))
        # Timestamp the message with local time
        timestamp = datetime.datetime.now()
        # Return a dictionary with descriptive keys
        return {'ownlatitude': latitude, 'ownlongitude': longitude, 'time': timestamp}


def binaryparser(dac,fi,data):
    # This function decodes known binary messages and returns the
    # interesting data as a dictionary where each key describes
    # the information of each message part.

    # For each value where we have a N/A-state None is returned

    # Initiate a return dict
    retdict = {}

    # If the message is IFM 0: free text message
    if dac == 1 and fi == 0:
        return {'text': bintoascii(data[12:]).strip('''@ ''').replace('''"''',"'")}

    # If the message is an IMO Meterology and Hydrology Message,
    # as specified in IMO SN/Circ. 236, Annex 2, Application 1:
    elif dac == 1 and fi == 11:
        # Latitude in decimal degrees (DD)
        retdict['latitude'] = calclatitude(data[0:24])
        # Longitude in decimal degrees (DD)
        retdict['longitude'] = calclongitude(data[24:49])
        # Bits 49-65 contains current station time in UTC (ddhhmm)
        # We use computer time as a baseline for year and month
        try:
            station_time = datetime.datetime.utcnow()
            station_time = station_time.replace(day=int(data[49:54],2),
                                                hour=int(data[54:59],2),
                                                minute=int(data[59:65],2),
                                                second=0, microsecond=0)
            retdict['station_time'] = station_time
        except ValueError:
            retdict['station_time'] = None # N/A
        # Average of wind speed values for the last ten minutes, knots
        retdict['average_wind_speed'] = standard_int_field(data[65:72])
        # Wind gust (maximum wind speed value) during the last ten
        # minutes, knots
        retdict['wind_gust'] = standard_int_field(data[72:79])
        # Wind direction in whole degrees
        retdict['wind_direction'] = standard_int_field(data[79:88])
        # Wind gust direction in whole degrees
        retdict['wind_gust_direction'] = standard_int_field(data[88:97])
        # Air temperature in 0.1 degrees Celsius from -60.0 to +60.0
        retdict['air_temperature'] = standard_decimal_tenth_signed_field(data[97:108])
        # Relative humidity in percent
        retdict['relative_humidity'] = standard_int_field(data[108:115])
        # Dew point in 0.1 degrees Celsius from -20.0 to +50.0
        retdict['dew_point'] = standard_decimal_tenth_signed_field(data[115:125])
        # Air pressure in whole hPa
        retdict['air_pressure'] = standard_int_field(data[125:134])
        # Air pressure tendency where 0=steady, 1=decreasing, 2=increasing
        retdict['air_pressure_tendency'] = standard_int_field(data[134:136])
        # Horizontal visibility in 0.1 NM steps
        retdict['horizontal_visibility'] = standard_decimal_tenth_field(data[136:144])
        # Water level including tide, deviation from local chart datum,
        # in 0.1 m from -10.0 to 30.0 m
        retdict['water_level_incl_tide'] = standard_decimal_tenth_signed_field(data[144:153])
        # Water level trend where 0=steady, 1=decreasing, 2=increasing
        retdict['water_level_trend'] = standard_int_field(data[153:155])
        # Surface current speed including tide in 0.1 kt steps
        retdict['surface_current_speed_incl_tide'] = standard_decimal_tenth_field(data[155:163])
        # Surface current direction in whole degrees
        retdict['surface_current_direction'] = standard_int_field(data[163:172])
        # Current speed #2, chosen below sea surface, in 0.1 kt steps
        retdict['current_speed_2'] = standard_decimal_tenth_field(data[172:180])
        # Current direction #2, chosen below sea surface in whole degrees
        retdict['current_direction_2'] = standard_int_field(data[180:189])
        # Current measuring level #2, whole meters below sea surface
        retdict['current_measuring_level_2'] = standard_int_field(data[189:194])
        # Current speed #3, chosen below sea surface, in 0.1 kt steps
        retdict['current_speed_3'] = standard_decimal_tenth_field(data[194:202])
        # Current direction #3, chosen below sea surface in whole degrees
        retdict['current_direction_3'] = standard_int_field(data[202:211])
        # Current measuring level #3, whole meters below sea surface
        retdict['current_measuring_level_3'] = standard_int_field(data[211:216])
        # Significant wave height in 0.1 m steps
        retdict['significant_wave_height'] = standard_decimal_tenth_field(data[216:224])
        # Wave period in whole seconds
        retdict['wave_period'] = standard_int_field(data[224:230])
        # Wave direction in whole degrees
        retdict['wave_direction'] = standard_int_field(data[230:239])
        # Swell height in 0.1 m steps
        retdict['swell_height'] = standard_decimal_tenth_field(data[239:247])
        # Swell period in whole seconds
        retdict['swell_period'] = standard_int_field(data[247:253])
        # Swell direction in whole degrees
        retdict['swell_direction'] = standard_int_field(data[253:262])
        # Sea state according to Beaufort scale (0-12)
        retdict['sea_state'] = standard_int_field(data[262:266])
        # Water temperature in 0.1 degrees Celsius from -10.0 to +50.0
        retdict['water_temperature'] = standard_decimal_tenth_signed_field(data[266:276])
        # Precipitation type according to WMO
        retdict['precipitation_type'] = standard_int_field(data[276:279])
        # Salinity in parts per thousand from 0.0 to 50.0
        retdict['salinity'] = standard_decimal_tenth_field(data[279:288])
        # Ice, Yes/No
        retdict['ice'] = standard_int_field(data[288:290])
        # Return a dictionary with descriptive keys
        return retdict

    # If we cannot decode the message, return None
    else:
        return None

def standard_int_field(data):
    # This function simplifies in checking for N/A-values
    # Check if just ones, then return N/A (Nonetype)
    if data.count('1') == len(data):
        return None
    else:
        return int(data,2)

def standard_int_signed_field(data):
    # This function simplifies in checking for N/A-values and signs
    # Check if just ones, then return N/A (Nonetype)
    if data.count('1') == len(data):
        return None
    else:
        # Return the signed integer
        if data[0]:
            # Positive
            return int(data[1:],2)
        else:
            # Negative
            return -int(data[1:],2)

def standard_decimal_tenth_field(data):
    # This function simplifies in checking for N/A-values
    # and returns a decimal.Decimal devided by 10
    # Check if just ones, then return N/A (Nonetype)
    if data.count('1') == len(data):
        return None
    else:
        return decimal.Decimal(int(data,2)) / 10

def standard_decimal_tenth_signed_field(data):
    # This function simplifies in checking for N/A-values and signs
    # and returns a decimal.Decimal devided by 10
    integer = standard_int_signed_field(data)
    if integer is None:
        return None
    else:
        return decimal.Decimal(integer) / 10

def tobin(x, count=8):
    # Convert the integer x to a binary representation where count is
    # the number of bits
    return "".join(map(lambda y:str((x>>y)&1), range(count-1, -1, -1)))

def makechecksum(s):
    # Calculate a checksum from sentence
    csum = 0
    i = 0
    s = s[1:s.rfind('*')] # Remove ! or $ and *xx in the sentence

    while (i < len(s)):
        inpt = binascii.b2a_hex(s[i])
        inpt = int(inpt,16)
        csum = csum ^ inpt #xor
        i += 1

    return csum

def checksum(s):
    # Create a checksum and compare it with the supplied checksum
    # If they are identical return 1, if not return 0
    try:
        # Create an integer of the two characters after the *, to the right
        supplied_csum = int(s[s.rfind('*')+1:s.rfind('*')+3], 16)
    except: return ''

    # Create the checksum
    csum = makechecksum(s)

    # Compare and return
    if csum == supplied_csum:
        return True
    else:
        return False

def sixtobin(encstring):
    # Converts encstring from coded 6-bit symbols to a binary string
    totalbin = ''
    for x in encstring[:]:
        # Loop over each symbol (x)
        # Convert x to the corresponding ASCII integer
        symbol = ord(x)
        # If the symbol does not exist in the character table, break loop
        if symbol < 48: break
        # If symbol match a certain table, subtract 48
        elif symbol < 88: symbol = symbol - 48
        # If the symbol does not exist in the character table, break loop
        elif symbol > 119: break
        # If symbol match a certain table, subtract 56
        else: symbol = symbol - 56
        # Add the bits from the integer symbol
        totalbin = totalbin + tobin(symbol, count=6)
    return totalbin

def bintoascii(binstring):
    # Converts binstring from binary integers to an ASCII string
    totalascii = ''
    inc = ''
    for x in binstring[:]:
        # Loop over each bit and add the bits until there are six of them
        inc = inc + x
        if len(inc) == 6:
            # Convert the six bits in inc to an integers
            symbol = int(inc,2)
            # If symbol is smaller than 32 add 64
            if symbol < 32: symbol = symbol + 64
            # Add the ASCII character to the string totalascii
            totalascii = totalascii + chr(symbol)
            inc = ''
    return totalascii

def calclatitude(binary_latitude):
    # Calculates latitude
    # First look at the signed bit
    sign = int(binary_latitude[0])
    latitude = int(binary_latitude[1:],2)
    # See how many bits we're looking at
    nr_bits = len(binary_latitude)
    if nr_bits == 24:
        factor = 60000 # 1000 * 60
        power = 23
    elif nr_bits == 27:
        factor = 600000 # 10000 * 60
        power = 26
    else:
        # Better to return None than a wrong value
        return None
    # See if the latitude are undefined (lat=91)
    if latitude == 91*factor:
        return None # N/A
    # Else, calculate the latitude
    if sign: # Negative == South
        latitude = pow(2,power) - latitude
        degree = -decimal.Decimal(latitude) / factor
    else: # Positive == North
        degree = decimal.Decimal(latitude) / factor
    # Return a value quantized to six decimal digits
    return degree.quantize(decimal.Decimal('1E-6'))

def calclongitude(binary_longitude):
    # Calculates longitude
    # First look at the signed bit
    sign = int(binary_longitude[0])
    longitude = int(binary_longitude[1:],2)
    # See how many bits we're looking at
    nr_bits = len(binary_longitude)
    if nr_bits == 25:
        factor = 60000 # 1000 * 60
        power = 24
    elif nr_bits == 28:
        factor = 600000 # 10000 * 60
        power = 27
    else:
        # Better to return None than a wrong value
        return None
    # See if the longitude are undefined (long=181)
    if longitude == 181*factor:
        return None # N/A
    # Else, calculate the longitude
    if sign: # Negative == West
        longitude = pow(2,power) - longitude
        degree = -decimal.Decimal(longitude) / factor
    else: # Positive == East
        degree = decimal.Decimal(longitude) / factor
    # Return a value quantized to six decimal digits
    return degree.quantize(decimal.Decimal('1E-6'))




class TestDecode(unittest.TestCase):
    def testaivdmposition(self):
        correct = {'rot': 0,
                   'posacc': 0,
                   'sog': decimal.Decimal("18.2"),
                   'mmsi': 265884000,
                   'longitude': decimal.Decimal("-76.362167"),
                   'cog': decimal.Decimal("156.4"),
                   'latitude': decimal.Decimal("38.436167"),
                   'navstatus': 0,
                   'heading': 157,
                   'message': 1}
        decoded = telegramparser('!AIVDM,1,1,,A,13uTAH002nJRLAHEwTi674rh04:8,0*2B')
        del decoded['time'] # Delete the time key
        self.assertEqual(decoded, correct)

    def testaivdmstaticdata(self):
        correct = {'name': 'WILSON LEITH',
                   'eta': '11170800',
                   'draught': decimal.Decimal("5.5"),
                   'mmsi': 249849000,
                   'destination': 'EMDEN',
                   'imo': 9150509,
                   'width': 13,
                   'length': 88,
                   'callsign': '9HII5',
                   'type': 70,
                   'message': 5}
        decoded = telegramparser("!AIVDM,1,1,,A,53fATb02;`2oTPTWF21LTi<tr0hDU@R2222222169`;676p`0=iCA1C`888888888888880,2*51")
        del decoded['time'] # Delete the time key
        self.assertEqual(decoded, correct)

    def testjointelegrams(self):
        correct = "!AIVDM,1,1,,,53u1V`01gnR5<DTn221>qB0thtJ222222222220l0pJ644b?e=kSlTRkl2CQp8888888880,0*4a"
        joined = jointelegrams("""!AIVDM,2,1,2,A,53u1V`01gnR5<DTn221>qB0thtJ222222222220l0pJ644b?e=kSlTRk,0*0E\n!AIVDM,2,2,2,A,l2CQp8888888880,2*22""")
        self.assertEqual(joined, correct)


if __name__ == '__main__':
    unittest.main()
