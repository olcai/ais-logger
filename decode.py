#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# decode.py (part of "AIS Logger")
# Simple AIS sentence parsing
#
# This parser has support for both standard !AIVDM type messages and for
# $PAIS type messages received from SAAB TransponderTech transponders
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

import binascii
import datetime
import math
import unittest

def jointelegrams(inputstring):
    # Creates an AIVDM-message combined of several sentences with a row break between each sentence
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
    # Combine the sentence and the checksum and create a single AIVDM-message
    fullphrase = fullphrase + csum[2:]
    return fullphrase

def telegramparser(inputstring):
    # This function decodes certain types of messages from the receiver and returns the interesting data as a dictionary where each key describes the information of each message part

    # Convert the raw input string to a list of separated values
    telegram = inputstring.split(',')

    # Depending on what sentence the list contains, extract the information and create a dictionary with the MMSI number as key and a value which contain another dictionary with the actual data

    # If the sentence follows the SAAB TransponderTech standard:
    if telegram[0] == '$PAIS':
        # If the sentence contains 02 - AIS Standard Position:
        if telegram[1] == '02':
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = str(int(telegram[2],16))
            # Rate of turn in degrees/minute from -127 to +127 where 128=N/A
            rateofturn = calcrateofturn(telegram[3])
            # Navigation status on a scale between 0-5 where 0=N/A
            navstatus = telegram[4]
            if navstatus == '1': navstatus = 'Under Way'
            elif navstatus == '2': navstatus = 'Not Under Command'
            elif navstatus == '3': navstatus = 'Restricted Manoeuvrability'
            elif navstatus == '4': navstatus = 'At Anchor'
            elif navstatus == '5': navstatus = 'MAYDAY'
            else: navstatus = 'N/A'
            # Latitude in degrees and minutes, example: N57 23.8200
            latitude = calclatitude(int(telegram[5],16))
            # Longitude in degrees and minutes, example: W115 20.3154
            longitude = calclongitude(int(telegram[6],16))
            # Speed over ground in 1/10 knots
            sog = str(float(int(telegram[7],16)) / 10).zfill(4)
            # Course over ground in 1/10 degrees where 0=360
            cog = str(float(int(telegram[8],16)) / 10).zfill(5)
            if cog == '0.0':
                cog = '360'
            # Heading in whole degrees where 0=360 and 511=N/A
            heading = str(int(telegram[9],16))
            if heading == '0':
                heading = '360'
            elif heading == '511':
                heading = ''
            # Position accuracy where 0=bad and 1=good/DGPS
            posacc = telegram[11]
            # Timestamp the message with local time
            timestamp = datetime.datetime.now().isoformat()[:19]
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi, 'rateofturn': rateofturn, 'navstatus': navstatus, 'latitude': latitude, 'longitude': longitude, 'sog': sog, 'cog': cog, 'heading': heading, 'posacc': posacc, 'time': timestamp}

        # If the sentence contains 0E - Identification Data:
        elif telegram[1] == '0E':
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = str(int(telegram[2],16))
            # Name, removes the characters @, ' ' and "
            name = telegram[3].strip('''@ ''').replace('''"''',"'")
            # Callsign, removes the characters @, ' ' and "
            callsign = telegram[4].strip('''@ ''').replace('''"''',"'")
            # IMO number where 00000000=N/A
            imo = str(int(telegram[5],16))
            if imo == '00000000':
                imo = ''
            # Built In Test where 0=OK, 1=error
            bit = telegram[6]
            # Tamper warning where 0=OK, 1=manipulated
            tamper = telegram[7]
            # Timestamp the message with local time
            timestamp = datetime.datetime.now().isoformat()[:19]
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi, 'name': name, 'callsign': callsign, 'imo': imo, 'bit': bit, 'tamper': tamper, 'time': timestamp}

        # If the sentence contains 0F - Vessel Data:
        elif telegram[1] == '0F':
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = str(int(telegram[2],16))
            # Ship type, a two-digit code where 00=N/A
            type = str(int(telegram[3],16))
            if type == '00':
                type = ''
            # Draught in 1/10 meters
            draught = str(float(int(telegram[4],16)) / 10)
            # Ship length calculated from antenna position
            length = str(calclength(telegram[5]))
            # Ship width calculated from antenna position
            width = str(calcwidth(telegram[5]))
            # Destination, removes the characters @, ' ' and "
            destination = telegram[6].strip('''@ ''').replace('''"''',"'")
            # Received estimated time of arrival in format month-day-hour-minute: MMDDHHMM where 00000000=N/A
            eta = telegram[8]
            if eta == '00000000':
                eta = ''
            # Timestamp the message with local time
            timestamp = datetime.datetime.now().isoformat()[:19]
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi, 'type': type, 'draught': draught, 'length': length, 'width': width, 'destination': destination, 'eta': eta, 'time': timestamp}

        else:
            return ''


    # If the sentence follows the ITU-R M.1371 standard:
    if telegram[0] == '!AIVDM':
        # Convert the 6-bit string to a binary string and check the message type
        bindata = sixtobin(telegram[5])

        # If the sentence contains message 1, 2 or 3 - Position report:
        if int(bindata[0:6],2) == 1 or int(bindata[0:6],2) == 2 or int(bindata[0:6],2) == 3:
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = str(int(bindata[8:38],2))
            # Navigation status on a scale between 0-8 where 0=N/A
            navstatus = str(int(bindata[38:42],2))
            if navstatus == '0': navstatus = 'Under Way'
            elif navstatus == '1': navstatus = 'At Anchor'
            elif navstatus == '2': navstatus = 'Not Under Command'
            elif navstatus == '3': navstatus = 'Restricted Manoeuvrability'
            elif navstatus == '4': navstatus = 'Constrained by her draught'
            elif navstatus == '5': navstatus = 'Moored'
            elif navstatus == '6': navstatus = 'Aground'
            elif navstatus == '7': navstatus = 'Engaged in Fishing'
            elif navstatus == '8': navstatus = 'Under way sailing'
            else: navstatus = 'N/A'
            # Rate of turn in degrees/minute from -127 to +127 where 128=N/A
            rateofturn = int(bindata[42:50],2)
            if rateofturn >0 and rateofturn <127:
                rateofturn = '+' + str(int(math.pow((rateofturn/4.733), 2))) # Convert between ROTais and ROTind
            elif rateofturn > 126 and rateofturn < 130:
                rateofturn = ''
            elif rateofturn >129 and rateofturn <=255:
                rateofturn = 256 - rateofturn
                rateofturn = '-' + str(int(math.pow((rateofturn/4.733), 2))) # Convert between ROTais and ROTind
            else:
                rateofturn = str(rateofturn)
            # Speed over ground in 1/10 knots
            sog = str(float(int(bindata[50:60],2)) / 10).zfill(4)
            # Position accuracy where 0=bad and 1=good/DGPS
            posacc = str(int(bindata[60],2))
            # Longitude in degrees and minutes, example: W115 20.3154
            longitude = calclongitude(int(bindata[61:89],2))
            # Latitude in degrees and minutes, example: N57 23.8200
            latitude = calclatitude(int(bindata[89:116],2))
            # Course over ground in 1/10 degrees where 0=360
            cog = str(float(int(bindata[116:128],2)) / 10).zfill(5)
            if cog == '0.0':
                cog = '360'
            # Heading in whole degrees where 0=360 and 511=N/A
            heading = str(int(bindata[128:137],2))
            if heading == '0':
                heading = '360'
            elif heading == '511':
                heading = ''
            # Timestamp the message with local time
            timestamp = datetime.datetime.now().isoformat()[:19]
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi, 'rateofturn': rateofturn, 'navstatus': navstatus, 'latitude': latitude, 'longitude': longitude, 'sog': sog, 'cog': cog, 'heading': heading, 'posacc': posacc, 'time': timestamp}
        
        # If the sentence contains message 5 - Ship Static and Voyage related data:
        if int(bindata[0:6],2) == 5 and int(bindata[38:40],2) == 0:
            # Check the checksum
            if not checksum(inputstring):
                return
            # MMSI number
            mmsi = str(int(bindata[8:38],2))
            # IMO number where 00000000=N/A
            imo = str(int(bindata[40:70],2))
            if imo == '00000000':
                imo = ''
            # Callsign, removes the characters @, ' ' and "
            callsign = bintoascii(bindata[70:112]).strip('''@ ''').replace('''"''',"'")
            # Name, removes the characters @, ' ' and "
            name = bintoascii(bindata[112:232]).strip('''@ ''').replace('''"''',"'")
            # Ship type, a two-digit code where 00=N/A
            type = str(int(bindata[232:240],2))
            if type == '00':
                type = ''
            # Ship length calculated from antenna position
            length = str((int(bindata[240:249],2) + int(bindata[249:258],2)))
            # Ship width calculated from antenna position
            width = str((int(bindata[258:264],2) + int(bindata[264:270],2)))
            # Received estimated time of arrival in format month-day-hour-minute: MMDDHHMM where 00000000=N/A
            eta = str(int(bindata[274:278],2)).zfill(2) + str(int(bindata[278:283],2)).zfill(2) + str(int(bindata[283:288],2)).zfill(2) + str(int(bindata[288:294],2)).zfill(2)
            if eta == '00000000':
                eta = ''
            # Draught in 1/10 meters
            draught = str(float(int(bindata[294:302],2)) / 10)
            # Destination, removes the characters @, ' ' and "
            destination = bintoascii(bindata[302:422]).strip('''@ ''').replace('''"''',"'")
            # Timestamp the message with local time
            timestamp = datetime.datetime.now().isoformat()[:19]
            # Return a dictionary with descriptive keys
            return {'mmsi': mmsi, 'imo': imo, 'callsign': callsign, 'name': name, 'type': type, 'length': length, 'width': width, 'eta': eta, 'destination': destination, 'draught': draught, 'time': timestamp}

        else:
            return ''


    # If the sentence contains NMEA-compliant position data (from own GPS):
    if telegram[0] == '$GPGGA':
        # Check the checksum
        if not checksum(inputstring):
            return
        # Latitude
        latitude = telegram[3] + telegram[2][0:4] + telegram[2][5:9]
        # Longitude
        longitude = telegram[5] + telegram[4][0:5] + telegram[4][6:10] 
        # Timestamp the message with local time
        timestamp = datetime.datetime.now().isoformat()[:19]
        # Return a dictionary with descriptive keys
        return {'ownlatitude': latitude, 'ownlongitude': longitude, 'time': timestamp}

def tobin(x, count=8):
    # Convert the integer x to a binary representation where count is the number of bits
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
        supplied_csum = int(s[s.rfind('*')+1:s.rfind('*')+3], 16) # Create an integer of the two characters after the *, to the right
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
        symbol = ord(x) # Convert x to the corresponding ASCII integer
        if symbol < 48: break # If the symbol does not exist in the character table, break loop
        elif symbol < 88: symbol = symbol - 48 # If symbol match a certain table, subtract 48
        elif symbol > 119: break # If the symbol does not exist in the character table, break loop
        else: symbol = symbol - 56 # If symbol match a certain table, subtract 56 
        totalbin = totalbin + tobin(symbol, count=6) # Add the bits from the integer symbol
    return totalbin

def bintoascii(binstring):
    # Converts binstring from binary integers to an ASCII string
    totalascii = ''
    inc = ''
    for x in binstring[:]:
        # Loop over each bit and add the bits until there are six of them
        inc = inc + x
        if len(inc) == 6:
            symbol = int(inc,2) # Convert the six bits in inc to an integer
            if symbol < 32: symbol = symbol + 64 # If symbol is smaller than 32 add 64
            totalascii = totalascii + chr(symbol) # Add the ASCII character to the string totalascii
            inc = '' 
    return totalascii

def calclength(antpos):
    # Calculates ship length in meters from the antenna position in hex
    antposdec = int(antpos, 16) # Convert hex to an integer
    binnumber = tobin(antposdec,count=30) # Convert integer to bits
    return int(binnumber[12:21],2) + int(binnumber[21:30],2) # Add the integers from the two parts

def calcwidth(antpos):
    # Calculates ship width in meters from the antenna position in hex
    antposdec = int(antpos, 16) # Convert hex to an integer
    binnumber = tobin(antposdec,count=30) # Convert integer to bits
    return int(binnumber[0:6],2) + int(binnumber[6:12],2) # Add integers from the two parts

def calcrateofturn(rateofturn):
    # Calculates rate of turn in degrees/minute from -127 to +127 where 128=N/A
    rateofturn = int(rateofturn, 16)
    if rateofturn >0 and rateofturn <128:
        return '+' + str(rateofturn)
    elif rateofturn == 128:
        return ''
    elif rateofturn >128 and rateofturn <=255:
        return '-' + str(256-rateofturn)
    else:
        return str(rateofturn)

def calclatitude(latitude):
    # Calculates latitude
    if latitude >=0 and latitude <=2147483647:
        degree = abs(latitude/(10000*60))
        minute = (latitude - degree*60*10000)
        degree = str(degree).zfill(2)
        minute = str(minute).zfill(6)
        return 'N' + degree + minute
    elif latitude >=2147483648 and latitude <=4294967295:
        latitude = 4294967296 - latitude
        degree = abs(latitude/(10000*60))
        minute = (latitude - degree*60*10000)
        degree = str(degree).zfill(2)
        minute = str(minute).zfill(6)
        return 'S' + degree + minute

def calclongitude(longitude):
    # Calculates longitude
    if longitude >=0 and longitude <=2147483647:
        degree = abs(longitude/(10000*60))
        minute = (longitude - degree*60*10000)
        degree = str(degree).zfill(3)
        minute = str(minute).zfill(6)
        return 'E' + degree + minute
    elif longitude >=2147483648 and longitude <=4294967295:
        longitude = 4294967296 - longitude
        degree = abs(longitude/(10000*60))
        minute = (longitude - degree*60*10000)
        degree = str(degree).zfill(3)
        minute = str(minute).zfill(6)
        return 'W' + degree + minute


class TestDecode(unittest.TestCase):
    def testaivdmposition(self):
        correct = {'rateofturn': '0', 'posacc': '0', 'sog': '18.2', 'mmsi': '265884000', 'longitude': 'E371018156', 'cog': '156.4', 'latitude': 'N38261700', 'navstatus': 'Under Way', 'heading': '157'}
        decoded = telegramparser('!AIVDM,1,1,,A,13uTAH002nJRLAHEwTi674rh04:8,0*2B')
        del decoded['time'] # Delete the time key
        self.assertEqual(decoded, correct)

    def testaivdmstaticdata(self):
        correct = {'name': 'WILSON LEITH', 'eta': '11170800', 'draught': '5.5', 'mmsi': '249849000', 'destination': 'EMDEN', 'imo': '9150509', 'width': '13', 'length': '88', 'callsign': '9HII5', 'type': '70'}
        decoded = telegramparser("!AIVDM,1,1,,A,53fATb02;`2oTPTWF21LTi<tr0hDU@R2222222169`;676p`0=iCA1C`888888888888880,2*51")
        del decoded['time'] # Delete the time key
        self.assertEqual(decoded, correct)

    def testjointelegrams(self):
        correct = "!AIVDM,1,1,,,53u1V`01gnR5<DTn221>qB0thtJ222222222220l0pJ644b?e=kSlTRkl2CQp8888888880,0*4a"
        joined = jointelegrams("""!AIVDM,2,1,2,A,53u1V`01gnR5<DTn221>qB0thtJ222222222220l0pJ644b?e=kSlTRk,0*0E\n!AIVDM,2,2,2,A,l2CQp8888888880,2*22""")
        self.assertEqual(joined, correct)


if __name__ == '__main__':
    unittest.main()
