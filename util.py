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

def georef(lat,long):
    # Converts lat/long in DD format to GEOREF

    # Define GEOREF-letters
    letters = 'ABCDEFGHJKLMNPQRSTUVWXYZ'

    # Extract letters for longitude
    # Degrees E/W are converted to degrees 0-360
    # Big square = abs value, small square = the reminder
    if long > 0: longdegree = 180 + int(long)
    elif long < 0: longdegree = 179 + int(long)
    bigsqlong = letters[longdegree / 15]
    smallsqlong = letters[longdegree % 15]

    # Extract letters for latitude
    # Degrees N/S are converted to degrees 0-180
    # Big square = abs value, small square = the reminder
    if lat > 0: latdegree = 90 + int(lat)
    elif lat < 0: latdegree = 89 + int(lat)
    bigsqlat = letters[latdegree / 15]
    smallsqlat = letters[latdegree % 15]

    # Extract minutes from latitude and logitude
    # Take into account that minutes start from the zero
    # meridian and the equator - GEOREF start from the
    # international date line...
    longdecmin = abs(long - int(long))
    latdecmin = abs(lat - int(lat))
    if long > 0: # East
        longminute = longdecmin * 60
    elif long < 0: # West
        longminute = (1 - longdecmin) * 60
    if lat > 0: # North
        latminute = latdecmin * 60
    elif lat < 0: # South
        latminute = (1 - latdecmin) * 60
    minutes = str(int(longminute)).zfill(2) + str(int(latminute)).zfill(2)

    return bigsqlong + bigsqlat + smallsqlong + smallsqlat + ' ' + minutes



###############################################################################
#
# From WxPython demo file images.py

from wx import ImageFromStream, BitmapFromImage
import cStringIO

def getSmallUpArrowData():
    return \
'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\
\x00\x00\x00\x1f\xf3\xffa\x00\x00\x00\x04sBIT\x08\x08\x08\x08|\x08d\x88\x00\
\x00\x00<IDATx\x9ccddbf\xa0\x040Q\xa4{h\x18\xf0\xff\xdf\xdf\xffd\x1b\x00\xd3\
\x8c\xcf\x10\x9c\x06\xa0k\xc2e\x08m\xc2\x00\x97m\xd8\xc41\x0c \x14h\xe8\xf2\
\x8c\xa3)q\x10\x18\x00\x00R\xd8#\xec\x95{\xc4\x11\x00\x00\x00\x00IEND\xaeB`\
\x82'

def getSmallUpArrowBitmap():
    return BitmapFromImage(getSmallUpArrowImage())

def getSmallUpArrowImage():
    stream = cStringIO.StringIO(getSmallUpArrowData())
    return ImageFromStream(stream)

def getSmallDnArrowData():
    return \
"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\
\x00\x00\x00\x1f\xf3\xffa\x00\x00\x00\x04sBIT\x08\x08\x08\x08|\x08d\x88\x00\
\x00\x00HIDATx\x9ccddbf\xa0\x040Q\xa4{\xd4\x00\x06\x06\x06\x06\x06\x16t\x81\
\xff\xff\xfe\xfe'\xa4\x89\x91\x89\x99\x11\xa7\x0b\x90%\ti\xc6j\x00>C\xb0\x89\
\xd3.\x10\xd1m\xc3\xe5*\xbc.\x80i\xc2\x17.\x8c\xa3y\x81\x01\x00\xa1\x0e\x04e\
\x1d\xc4;\xb7\x00\x00\x00\x00IEND\xaeB`\x82"

def getSmallDnArrowBitmap():
    return BitmapFromImage(getSmallDnArrowImage())

def getSmallDnArrowImage():
    stream = cStringIO.StringIO(getSmallDnArrowData())
    return ImageFromStream(stream)
