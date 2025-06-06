import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
from Autodesk.Revit import DB
from pyrevit import revit
from pyrevit import forms
from pyrevit import script

doc = revit.doc
view = doc.ActiveView

collector = DB.FilteredElementCollector(doc, view.Id)
dimensions = collector.OfClass(DB.Dimension).ToElementIds()

if dimensions:
    t = DB.Transaction(doc, "Delete All Dimensions in Active View")
    try:
        t.Start()
        doc.Delete(dimensions)
        t.Commit()
        forms.alert(
            "Deleted {} dimension(s) from the active view.".format(len(dimensions)),
            title="Dimensions Deleted",
            exitscript=True,
        )
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        script.get_logger().error("Transaction Failed: {}".format(e))
    finally:
        if t is not None:
            t.Dispose()
else:
    forms.alert(
        "No dimension tags found in the active view.",
        title="No Dimensions",
        exitscript=True,
    )
