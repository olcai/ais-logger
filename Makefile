# Simple makefile for AIS Logger
# Sets version with some help from sed

VERSION = 0014

setversion:
	sed 's#VERSION_TAG#${VERSION}#g' aislogger/main.py > aislogger/main2.py
	sed 's#VERSION_TAG#${VERSION}#g' setup.py > setup2.py
	mv aislogger/main2.py aislogger/main.py
	mv setup2.py setup.py
