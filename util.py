#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# util.py (part of "AIS Logger")
# This file contains code snippets
#
# FOR LICENSE DETAILS, SEE EACH RELEVANT SECTION OF THIS FILE


###############################################################################
#
# The following code is from geopy and distance.py (slightly modified)
# For more information see http://exogen.case.edu/projects/geopy/
#
# Copyright (c) 2006 Brian Beck
# Copyright (c) 2006 Erik I.J. Olsson <olcai@users.sourceforge.net>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of 
# this software and associated documentation files (the "Software"), to deal in 
# the Software without restriction, including without limitation the rights to 
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
# of the Software, and to permit persons to whom the Software is furnished to do 
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
# SOFTWARE.

from math import *

#             model             major (km)   minor (km)     flattening
ELLIPSOIDS = {'WGS-84':        (6378.137,    6356.7523142,  1 / 298.257223563),
              'GRS-80':        (6378.137,    6356.7523141,  1 / 298.257222101),
              'Airy (1830)':   (6377.563396, 6356.256909,   1 / 299.3249646),
              'Intl 1924':     (6378.388,    6356.911946,   1 / 297.0),
              'Clarke (1880)': (6378.249145, 6356.51486955, 1 / 293.465),
              'GRS-67':        (6378.1600,   6356.774719,   1 / 298.25),
              }

class VincentyDistance(object):
    """Calculate the geodesic distance between two points using the formula
    devised by Thaddeus Vincenty, with an accurate ellipsoidal model of the
    earth.
    
    The class attribute ``ELLIPSOID`` indicates which ellipsoidal model of the
    earth to use. If it is a string, it is looked up in the ELLIPSOIDS
    dictionary to obtain the major and minor semiaxes and the flattening.
    Otherwise, it should be a tuple with those values. The most globally
    accurate model is WGS-84. See the comments above the ELLIPSOIDS dictionary
    for more information.
    """


    def __init__(self, a, b):
        """Initialize a Distance whose length is the distance between the two
        geodesic points ``a`` and ``b``, using the ``calculate`` method to
        determine this distance.
        """
        
        self.a = a
        self.b = b
        
        if a and b:
            self.calculate()


    ELLIPSOID = ELLIPSOIDS['WGS-84']
    
    def calculate(self):
        lat1, lng1 = map(radians, self.a)
        lat2, lng2 = map(radians, self.b)
        
        if isinstance(self.ELLIPSOID, basestring):
            major, minor, f = ELLIPSOIDS[self.ELLIPSOID]
        else:
            major, minor, f = self.ELLIPSOID
        
        delta_lng = lng2 - lng1
        
        reduced_lat1 = atan((1 - f) * tan(lat1))
        reduced_lat2 = atan((1 - f) * tan(lat2))
        
        sin_reduced1, cos_reduced1 = sin(reduced_lat1), cos(reduced_lat1)
        sin_reduced2, cos_reduced2 = sin(reduced_lat2), cos(reduced_lat2)
        
        lambda_lng = delta_lng
        lambda_prime = 2 * pi
        
        iter_limit = 20
        
        while abs(lambda_lng - lambda_prime) > 10e-12 and iter_limit > 0:
            sin_lambda_lng, cos_lambda_lng = sin(lambda_lng), cos(lambda_lng)
            
            sin_sigma = sqrt((cos_reduced2 * sin_lambda_lng) ** 2 +
                             (cos_reduced1 * sin_reduced2 - sin_reduced1 *
                              cos_reduced2 * cos_lambda_lng) ** 2)
            
            if sin_sigma == 0:
                return 0 # Coincident points
            
            cos_sigma = (sin_reduced1 * sin_reduced2 +
                         cos_reduced1 * cos_reduced2 * cos_lambda_lng)
            
            sigma = atan2(sin_sigma, cos_sigma)
            
            sin_alpha = cos_reduced1 * cos_reduced2 * sin_lambda_lng / sin_sigma
            cos_sq_alpha = 1 - sin_alpha ** 2
            
            if cos_sq_alpha != 0:
                cos2_sigma_m = cos_sigma - 2 * (sin_reduced1 * sin_reduced2 /
                                                cos_sq_alpha)
            else:
                cos2_sigma_m = 0.0 # Equatorial line
            
            C = f / 16. * cos_sq_alpha * (4 + f * (4 - 3 * cos_sq_alpha))
            
            lambda_prime = lambda_lng
            lambda_lng = (delta_lng + (1 - C) * f * sin_alpha *
                          (sigma + C * sin_sigma *
                           (cos2_sigma_m + C * cos_sigma * 
                            (-1 + 2 * cos2_sigma_m ** 2))))
            iter_limit -= 1
            
        if iter_limit == 0:
            raise ValueError("Vincenty formula failed to converge!")
        
        u_sq = cos_sq_alpha * (major ** 2 - minor ** 2) / minor ** 2
        
        A = 1 + u_sq / 16384. * (4096 + u_sq * (-768 + u_sq *
                                                (320 - 175 * u_sq)))
        
        B = u_sq / 1024. * (256 + u_sq * (-128 + u_sq * (74 - 47 * u_sq)))
        
        delta_sigma = (B * sin_sigma *
                       (cos2_sigma_m + B / 4. *
                        (cos_sigma * (-1 + 2 * cos2_sigma_m ** 2) -
                         B / 6. * cos2_sigma_m * (-3 + 4 * sin_sigma ** 2) *
                         (-3 + 4 * cos2_sigma_m ** 2))))
        
        s = minor * A * (sigma - delta_sigma)
        
        sin_lambda, cos_lambda = sin(lambda_lng), cos(lambda_lng)
        
        alpha_1 = atan2(cos_reduced2 * sin_lambda,
                        cos_reduced1 * sin_reduced2 -
                        sin_reduced1 * cos_reduced2 * cos_lambda)
        
        alpha_2 = atan2(cos_reduced1 * sin_lambda,
                        cos_reduced1 * sin_reduced2 * cos_lambda -
                        sin_reduced1 * cos_reduced2)
        
        self._kilometers = s
        self._nautical = s / 1.852
        self.initial_bearing = (360 + degrees(alpha_1)) % 360
        self.final_bearing = (360 + degrees(alpha_2)) % 360

    @property
    def kilometers(self):
        return self._kilometers

    @property
    def nautical(self):
        return self._nautical

    @property
    def forward_azimuth(self):
        return self.initial_bearing

    @property
    def all(self):
        return {'bearing': self.initial_bearing, 'km': self._kilometers, 'nm': self._nautical}



###############################################################################
#
# The following code is from the ASPN Python Cookbook (slightly modified)
# For more information see
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/496799
#
# The code has been modified to also provide an "executemany" case and
# logging in case of error.
#
# Copyright (c) 2006 Wim Schut
# Copyright (c) 2007 Erik I.J. Olsson <olcai@users.sourceforge.net>
# All Rights Reserved.
#
# This is the Python license. In short, you can use this product in
# commercial and non-commercial applications, modify it, redistribute it.
# A notification to the author when you use and/or modify it is welcome.
#
# TERMS AND CONDITIONS FOR ACCESSING OR OTHERWISE USING THIS SOFTWARE
# ===================================================================
#
# LICENSE AGREEMENT
# -----------------
#
# 1. This LICENSE AGREEMENT is between the copyright holder of this
# product, and the Individual or Organization ("Licensee") accessing
# and otherwise using this product in source or binary form and its
# associated documentation.
#
# 2. Subject to the terms and conditions of this License Agreement,
# the copyright holder hereby grants Licensee a nonexclusive,
# royalty-free, world-wide license to reproduce, analyze, test,
# perform and/or display publicly, prepare derivative works, distribute,
# and otherwise use this product alone or in any derivative version,
# provided, however, that copyright holders License Agreement and
# copyright holders notice of copyright are retained in this product
# alone or in any derivative version prepared by Licensee.
#
# 3. In the event Licensee prepares a derivative work that is based on
# or incorporates this product or any part thereof, and wants to make
# the derivative work available to others as provided herein, then
# Licensee hereby agrees to include in any such work a brief summary of
# the changes made to this product.
#
# 4. The copyright holder is making this product available to Licensee on
# an "AS IS" basis. THE COPYRIGHT HOLDER MAKES NO REPRESENTATIONS OR
# WARRANTIES, EXPRESS OR IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION,
# THE COPYRIGHT HOLDER MAKES NO AND DISCLAIMS ANY REPRESENTATION OR
# WARRANTY OF MERCHANTABILITY OR FITNESS FOR ANY PARTICULAR PURPOSE OR
# THAT THE USE OF THIS PRODUCT WILL NOT INFRINGE ANY THIRD PARTY RIGHTS.
#
# 5. THE COPYRIGHT HOLDER SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER
# USERS OF THIS PRODUCT FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL
# DAMAGES OR LOSS AS A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE
# USING THIS PRODUCT, OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE
# POSSIBILITY THEREOF.
#
# 6. This License Agreement will automatically terminate upon a material
# breach of its terms and conditions.
#
# 7. Nothing in this License Agreement shall be deemed to create any
# relationship of agency, partnership, or joint venture between the
# copyright holder and Licensee. This License Agreement does not grant
# permission to use trademarks or trade names from the copyright holder
# in a trademark sense to endorse or promote products or services of
# Licensee, or any third party.
#
# 8. By copying, installing or otherwise using this product, Licensee
# agrees to be bound by the terms and conditions of this License
# Agreement.

import pysqlite2.dbapi2 as sqlite
import Queue, time, thread, os, logging
from threading import Thread

_threadex = thread.allocate_lock()
qthreads = 0
sqlqueue = Queue.Queue()

ConnectCmd = "connect"
SqlCmd = "SQL"
SqlManyCmd = "SQLmany"
StopCmd = "stop"
class DbCmd:
    def __init__(self, cmd, params=[]):
        self.cmd = cmd
        self.params = params

class DbWrapper(Thread):
    def __init__(self, path, nr):
        Thread.__init__(self)
        self.path = path
        self.nr = nr
    def run(self):
        global qthreads
        con = sqlite.connect(self.path)
        cur = con.cursor()
        while True:
            s = sqlqueue.get()
            #print "Conn %d -> %s -> %s" % (self.nr, s.cmd, s.params)
            if s.cmd == SqlCmd or s.cmd == SqlManyCmd:
                commitneeded = False
                res = []
#               s.params is a list to bundle statements into a "transaction"
                for sql in s.params:
                    try:
                        if s.cmd == SqlCmd: cur.execute(sql[0],sql[1])
                    except:
                        logging.warning("SQL-command failed, statements: " + str(sql[0]) + str(sql[1]), exc_info=True)
                    if s.cmd == SqlManyCmd: cur.executemany(sql[0],sql[1])
                    if not sql[0].upper().startswith("SELECT"): 
                        commitneeded = True
                    for row in cur.fetchall(): res.append(row)
                if commitneeded: con.commit()
                s.resultqueue.put(res)
            else:
                _threadex.acquire()
                qthreads -= 1
                _threadex.release()
#               allow other threads to stop
                sqlqueue.put(s)
                s.resultqueue.put(None)
                break

def execSQL(s):
    if s.cmd == ConnectCmd:
        global qthreads
        _threadex.acquire()
        qthreads += 1
        _threadex.release()
        wrap = DbWrapper(s.params, qthreads)
        wrap.start()
    elif s.cmd == StopCmd:
        s.resultqueue = Queue.Queue()
        sqlqueue.put(s)
#       sleep until all threads are stopped
        while qthreads > 0: time.sleep(0.1)
    else:
        s.resultqueue = Queue.Queue()
        sqlqueue.put(s)
        return s.resultqueue.get()



###############################################################################
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

def georef(lat,long):
    # Konverterar lat/long i DM-format till GEOREF

    # Definiera GEOREF-bokstäver
    letters = 'ABCDEFGHJKLMNPQRSTUVWXYZ'

    # Ta fram bokstavsruta för longituden
    # Grader E/W konverteras till grader 0-360
    # Storrutan = absolutvärdet, lillrutan = resten
    if long[0] == 'E': longdegree = 180 + int(long[1:4])
    elif long[0] == 'W': longdegree = 179 - int(long[1:4])
    bigsqlong = letters[longdegree / 15]
    smallsqlong = letters[longdegree % 15]

    # Ta fram bokstavsruta för latituden
    # Grader N/S konverteras till grader 0-180
    # Storrutan = absolutvärdet, lillrutan = resten
    if lat[0] == 'N': latdegree = 90 + int(lat[1:3])
    elif lat[0] == 'S': latdegree = 89 - int(lat[1:3])
    bigsqlat = letters[latdegree / 15]
    smallsqlat = letters[latdegree % 15]

    # Extrahera minuter ur longituden och latituden
    # Ta hänsyn till att minuter utgår från nollmeridianen och
    # ekvatorn - GEOREF utgår ju från datumgränsen... 
    if long[0] == 'E' and lat[0] == 'N':
        minutes = long[4:6] + lat[3:5]
    elif long[0] == 'E' and lat [0] == 'S':
        minutes = long[4:6] + str(59 - int(lat[3:5]))
    elif long[0] == 'W' and lat[0] == 'N':
        minutes = str(59 - int(long[4:6])) + lat[3:5]
    elif long[0] == 'W' and lat[0] == 'S':
        minutes = str(59 - int(long[4:6])) + str(59 - int(lat[3:5]))

    return bigsqlong + bigsqlat + smallsqlong + smallsqlat + ' ' + minutes


