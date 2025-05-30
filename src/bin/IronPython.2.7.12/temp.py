from pyrevit import revit, DB, forms, script
import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

doc = revit.doc
uidoc = revit.uidoc
logger = script.get_logger()

active_view = doc.ActiveView
collector = DB.FilteredElementCollector(doc, active_view.Id)
walls = (
    collector.OfCategory(DB.Category.OST_Walls)
    .WhereElementIsNotElementType()
    .ToElements()
)
wall_count = len(walls)
forms.alert("Number of Walls in active view: {0}".format(wall_count))
