## Alerts and Remarks

The _Set alerts and remarks_ window is a tool to view, sort and search
the identification database and to set alerts and remarks on specific
objects. It can also export the current list view to a CSV file for
further processing in a spreadsheet.


### Filtering

The list is a compilation of data from three distinct sources: the
identification database, current remarks and set alerts.

On top of the window, there is a box called _Filter_. To filter the
list so that only alerts or only remarks are visible, simply check the
corresponding check box. One can also filter by entering an expression
in the text box, by first selecting on what column the entered text
will filter. The list will update immediately when entering a
character in the box. The filter works within strings, and will thus
match any part of a string.


### Editing an object

To edit an object, just select it with mouse or keyboard. The selected
objects' data will be displayed in the _Selected object_ box. Changing
the remark or the alert is straightforward: edit the remark field box
or change the selected radio button. After editing an object, press
_Save object_ to apply the changes. This will __not__ save the changes
to file.

__NOTE:__ The last selected object will still be the active object in
the Selected object box when applying a filter. Therefore caution is
advised; you have to select a new object to edit even if there are
only one object in the list.  Otherwise you may end up editing another
object than the one in the list. Make sure that you have a selection
in the list before saving your changes.


### Inserting new alerts or remarks

To set an alert or a remark on an object that doesn't already exist in
the identification database, please press the _Insert new..._
button. A dialog will open asking the user for the MMSI number to
insert. The object will then be inserted in the list view.

Beware that if one edits an object that doesn't exist in the ID
database, makes the remark field blank and put the alert box to no,
the object will be deleted. This is because there will no longer be an
association with the ID database, a remark or an alert.


### Exporting the list

To ease analysis of remarks, alerts and entries in the ID database, it
is possible to export the current view. Just press _Export list..._
and choose the file name to save the list to. The current list (with
filters applied) is saved in a simple comma separated format
(CSV). This is useful for manipulating data further in a spreadsheet
software such as MS Excel.

