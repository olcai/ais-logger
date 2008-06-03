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
        # If the sentence contains 02 - AIS Standard Position:
        if telegram[1] == '02':
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = int(telegram[2],16)
            # Rate of turn in degrees/minute from -127 to +127 where 128=N/A
            rateofturn = int(telegram[3], 16)
            if rateofturn >=0 and rateofturn <128: # Turning right
                rateofturn = rateofturn
            elif rateofturn >128 and rateofturn <=255: # Turning left
                rateofturn = 256 - rateofturn
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
            # Latitude in degrees and minutes, example: N57 23.8200
            latitude = saab_calclatitude(int(telegram[5],16))
            # Longitude in degrees and minutes, example: W115 20.3154
            longitude = saab_calclongitude(int(telegram[6],16))
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
            # Timestamp the message with local time
            timestamp = datetime.datetime.now()
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
                    'time': timestamp}

        # If the sentence contains 0E - Identification Data:
        elif telegram[1] == '0E':
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = int(telegram[2],16)
            # Name, removes the characters @, ' ' and "
            name = telegram[3].strip('''@ ''').replace('''"''',"'")
            # Callsign, removes the characters @, ' ' and "
            callsign = telegram[4].strip('''@ ''').replace('''"''',"'")
            # IMO number where 00000000=N/A
            imo = int(telegram[5],16)
            if imo == 0:
                imo = None
            # Built In Test where 0=OK, 1=error
            bit = int(telegram[6])
            # Tamper warning where 0=OK, 1=manipulated
            tamper = int(telegram[7])
            # Timestamp the message with local time
            timestamp = datetime.datetime.now()
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'name': name,
                    'callsign': callsign,
                    'imo': imo,
                    'bit': bit,
                    'tamper': tamper,
                    'time': timestamp}

        # If the sentence contains 0F - Vessel Data:
        elif telegram[1] == '0F':
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = int(telegram[2],16)
            # Ship type, a two-digit code where 00=N/A
            type = int(telegram[3],16)
            if type == 0:
                type = None # N/A
            # Draught in 1/10 meters
            draught = decimal.Decimal(int(telegram[4],16)) / 10
            # Calculate ship length in meters from the antenna position in hex
            # Convert hex->int->bits
            l_binnumber = tobin(int(telegram[5],16),count=30)
            # Add the integers from the two parts
            length = int(l_binnumber[12:21],2) + int(l_binnumber[21:30],2)
            # Calculate ship width in meters from the antenna position in hex
            # Convert hex->int->bits
            w_binnumber = tobin(int(telegram[5],16),count=30)
            # Add integers from the two parts
            width = int(w_binnumber[0:6],2) + int(w_binnumber[6:12],2)
            # Destination, removes the characters @, ' ' and "
            destination = telegram[6].strip('''@ ''').replace('''"''',"'")
            # Received estimated time of arrival in format
            # month-day-hour-minute: MMDDHHMM where 00000000=N/A
            eta = telegram[8]
            if eta == '00000000':
                eta = None
            # Timestamp the message with local time
            timestamp = datetime.datetime.now()
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi,
                    'type': type,
                    'draught': draught,
                    'length': length,
                    'width': width,
                    'destination': destination,
                    'eta': eta,
                    'time': timestamp}

        else:
            return ''


    # If the sentence follows the ITU-R M.1371 standard:
    if telegram[0] == '!AIVDM':
        # Convert the 6-bit string to a binary string and check the
        # message type
        bindata = sixtobin(telegram[5])

        # Extract the message type number
        message = int(bindata[0:6],2)

        # If the sentence contains message 1, 2 or 3 - Position Report:
        if message == 1 or message == 2 or message == 3:
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = int(bindata[8:38],2)
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
            # Timestamp the message with local time
            timestamp = datetime.datetime.now()
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
        if message == 4:
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = int(bindata[8:38],2)
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
            # Timestamp the message with local time
            timestamp = datetime.datetime.now()
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
        if message == 5 and int(bindata[38:40],2) == 0:
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = int(bindata[8:38],2)
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
            #  month-day-hour-minute: MMDDHHMM where 00000000=N/A
            eta = (str(int(bindata[274:278],2)).zfill(2) +
                  str(int(bindata[278:283],2)).zfill(2) +
                  str(int(bindata[283:288],2)).zfill(2) +
                  str(int(bindata[288:294],2)).zfill(2))
            if eta == '00000000':
                eta = None
            # Draught in 1/10 meters
            draught = decimal.Decimal(int(bindata[294:302],2)) / 10
            # Destination, removes the characters @, ' ' and "
            destination = bintoascii(bindata[302:422]).strip('''@ ''').replace('''"''',"'")
            # Timestamp the message with local time
            timestamp = datetime.datetime.now()
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

        # If the sentence contains message 9 - Special Position Report:
        if message == 9:
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = int(bindata[8:38],2)
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
            # Timestamp the message with local time
            timestamp = datetime.datetime.now()
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

        else:
            # If we don't decode the message, at least return message type
            return {'message': message}


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
        return 1
    else:
        return 0

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
    # See if the latitude are undefined
    if latitude == 54600000:
        return decimal.Decimal("91") # N/A
    # Else, calculate the latitude
    if sign: # Negative == South
        latitude = 67108864 - latitude
        degree = -decimal.Decimal(latitude) / 600000 # 10000 * 60
    else: # Positive == North
        degree = decimal.Decimal(latitude) / 600000 # 10000 * 60
    # Return a value quantized to six decimal digits
    return degree.quantize(decimal.Decimal('1E-6'))

def saab_calclatitude(latitude):
    # Special calculations for SAAB latitude
    if latitude >=0 and latitude <=2147483647: # North
        degree = decimal.Decimal(latitude) / 600000 # 10000 * 60
    elif latitude >=2147483648 and latitude <=4294967295: # South
        latitude = 4294967296 - latitude
        degree = -decimal.Decimal(latitude) / 600000 # 10000 * 60
    else:
        return decimal.Decimal("91") # N/A
    # Return a value quantized to six decimal digits
    return degree.quantize(decimal.Decimal('1E-6'))

def calclongitude(binary_longitude):
    # Calculates longitude
    # First look at the signed bit
    sign = int(binary_longitude[0])
    longitude = int(binary_longitude[1:],2)
    # See if the longitude are undefined
    if longitude == 108600000:
        return decimal.Decimal("181") # N/A
    # Else, calculate the longitude
    if sign: # Negative == West
        longitude = 134217728 - longitude
        degree = -decimal.Decimal(longitude) / 600000 # 10000 * 60
    else: # Positive == East
        degree = decimal.Decimal(longitude) / 600000 # 10000 * 60
    # Return a value quantized to six decimal digits
    return degree.quantize(decimal.Decimal('1E-6'))

def saab_calclongitude(longitude):
    # Special calculations for SAAB longitude
    if longitude >=0 and longitude <=2147483647: # East
        degree = decimal.Decimal(longitude) / 600000 # 10000 * 60
    elif longitude >=2147483648 and longitude <=4294967295: # West
        longitude = 4294967296 - longitude
        degree = -decimal.Decimal(longitude) / 600000 # 10000 * 60
    else:
        return decimal.Decimal("181") # N/A
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
                   'heading': 157}
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
                   'type': 70}
        decoded = telegramparser("!AIVDM,1,1,,A,53fATb02;`2oTPTWF21LTi<tr0hDU@R2222222169`;676p`0=iCA1C`888888888888880,2*51")
        del decoded['time'] # Delete the time key
        self.assertEqual(decoded, correct)

    def testjointelegrams(self):
        correct = "!AIVDM,1,1,,,53u1V`01gnR5<DTn221>qB0thtJ222222222220l0pJ644b?e=kSlTRkl2CQp8888888880,0*4a"
        joined = jointelegrams("""!AIVDM,2,1,2,A,53u1V`01gnR5<DTn221>qB0thtJ222222222220l0pJ644b?e=kSlTRk,0*0E\n!AIVDM,2,2,2,A,l2CQp8888888880,2*22""")
        self.assertEqual(joined, correct)


if __name__ == '__main__':
    unittest.main()
