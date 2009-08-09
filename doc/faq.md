## FAQ and Troubleshooting

### What the heck is this AIS thing you keep talking talking about?

AIS stands for Automatic Identification System and is a fairly
close-range transponder system used primarily for tracking ships. Each
station (or ship) transmits information on a regular basis such as
position, speed, heading and name. AIS Logger is a program that
decodes this information, given that you have access to a special VHF
receiver that can receive these radio transmissions.

### Does AIS Logger work with any AIS receiver?

If the receiver conforms to the standard and uses NMEA AIVDM
sentences, the answer is yes. It also works with transponders from
SAAB TransponderTech and their proprietary format. If I were to
recommend a receiver, I would probably recommend the SR-161 or the
SR-162 from Smart Radio. They are two great receivers for a low cost.

### Why are there no country code in the nation column on some objects?

The country codes are mapped from a file called mid.lst in the data
directory. Some objects have MMSI numbers that doesn't map to a entry
in the mid.lst file. There are also some MID codes that are mapped to
an entity (see the Detail Window for the full entity name) but lacks a
two-letter ISO country code. And finally there are a grey-zone
consisting of islands which are self-governed. It is not always easy
to know if such an island consider themselves as a supreme country or
not. In all of these cases, the nation column will be left blank.

### Why are the alert/remark file encoded in cp-1252? I thought we all were in the unicode age by now! 

Well, most of us are, but the old Windows Notepad is not. I like to be
able to edit the alert/remark file by hand. I also happen to use
Nordic characters in my remarks, and well, Notepad is not UTF-8
friendly exactly... Or rather was. I think that MS fixed that in XP or
something.

### The program starts but exits/crashes almost instantly! What's going on?

Well, I don't know. Take a look in the file except.log if you got
one. There you can see all errors and exceptions that the program
creates. You could also try renaming your config.ini file to something
with a different suffix. The program then will start with default
settings. You can then create a new config file by editing the
settings. If it still refuses to start, there is something wrong with
the program. Please send in a bug report if needed.

### Why are all objects grey in the list?

There is no input to the program. Take a look in the "Raw data"
window. If nothing is happening there, start checking your input
sources. By design, having no input will also result in that objects
won't get deleted until new data is read. Personally, I think this is
a feature. You will easily see at what time something happened.

### I've got funny characters in the settings window!

This is probably an encoding problem. You've used some non-ascii
characters in your paths, right? Everything should work anyway, it's
just in the GUI things look funny. If the program seems to behave
strangely because of this, send in a bug report.

### The program is using up all my CPU cycles! Help!

Oh, this is NOT by design... It is probably a bug. And most of the time
it is related to input. Try to close the program normally and have a
look in except.log. If something looks strange at the end of the file,
contact me and we'll see if we can fix it.
