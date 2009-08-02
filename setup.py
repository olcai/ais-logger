#!/usr/bin/env python
from distutils.core import setup
import sys

version = ['0013']

# Set no data files
data_files = []

# See if we are running py2exe
for entry in sys.argv:
    if entry.find('py2exe') != -1:
        import py2exe
        # Set data files for py2exe
        data_files = [('data',['aislogger/data/mid.lst',
                               'aislogger/data/typecode.lst',
                               'aislogger/data/typecode_sv.lst',
                               'aislogger/data/world.dat'])]
# Main setup
setup (name='aislogger',
       version='.'.join(version),
       description='Simple AIS logging and display software',
       author='Erik I.J. Olsson',
       author_email='olcai@users.sourceforge.net',
       url='http://sourceforge.net/projects/aislogger/',
       license='MIT',
       scripts=['bin/aislogger'],
       packages=['aislogger', 'aislogger.external'],
       package_dir={'aislogger.external': 'external'},
       package_data={'aislogger': ['data/*']},

       # Options for py2exe
       windows=['bin/aislogger'],
       zipfile=None,
       data_files=data_files,
       options={'py2exe': {
                          'excludes': ['Tkconstants', 'Tkinter', 'tcl'],
                          'dll_excludes': ['MSVCP90.DLL']}}
)
