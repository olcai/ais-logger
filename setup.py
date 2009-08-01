#!/usr/bin/env python
from distutils.core import setup

version = ['0013']

# Set version tag in main.py
f = open("aislogger/main.py", 'r+')
d = f.read().replace("VERSION_TAG", ".".join(version))
f.truncate(0)
f.seek(0)
f.write(d)
f.close()

setup (name='aislogger',
       version='.'.join(version),
       description='Simple AIS logging and display software',
       author='Erik I.J. Olsson',
       author_email='olcai@users.sourceforge.net',
       url='http://sourceforge.net/projects/aislogger/',
       license='MIT',
       scripts=['bin/aislogger'],
       packages=['aislogger', 'aislogger.external'],
       package_dir = {'aislogger.external': 'external'},
       package_data={'aislogger': ['data/*']}
)
