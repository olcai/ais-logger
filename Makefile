# Simple makefile for AIS Logger

# Set release version number
VERSION = 0015
# Set resulting manual file
MANUAL_FILE = doc/manual.html


.PHONY: doc clean setversion build release

release: build clean

# Create a source distribution
build: doc setversion
	python setup.py sdist

# Copy originals and set version tags in code
setversion:
	cp aislogger/main.py aislogger/main.py.org
	cp setup.py setup.py.org
	sed 's#VERSION_TAG#${VERSION}#g' aislogger/main.py.org > aislogger/main.py
	sed 's#VERSION_TAG#${VERSION}#g' setup.py.org > setup.py

# Create manual from templates and markdown files
doc:
	sed 's#VERSION_TAG#${VERSION}#g' doc/header.html > ${MANUAL_FILE}
	markdown doc/introduction.md >> ${MANUAL_FILE}
	markdown doc/guidedtour.md >> ${MANUAL_FILE}
	markdown doc/alertsandremarks.md >> ${MANUAL_FILE}
	markdown doc/configuration.md >> ${MANUAL_FILE}
	markdown doc/logfileformat.md >> ${MANUAL_FILE}
	markdown doc/faq.md >> ${MANUAL_FILE}
	cat doc/footer.html >> ${MANUAL_FILE}

clean:
	rm -f doc/manual.html
	rm -f MANIFEST
	mv aislogger/main.py.org aislogger/main.py
	mv setup.py.org setup.py

