# -*- coding: utf-8 -*-
"""
Deletes all dimension elements from the current active view.
"""

from pyrevit import revit, DB, UI
from pyrevit import script
from pyrevit import forms

# Get the current document and the active view
doc = revit.doc
active_view = doc.ActiveView

if not active_view:
    forms.alert("No active view found. Please run the script in a project view.", exitscript=True)

# Use a FilteredElementCollector to find all dimension elements in the current view
collector = DB.FilteredElementCollector(doc, active_view.Id)\
              .OfClass(DB.Dimension)

# Get the ElementIds of the dimensions to be deleted
dims_to_delete_ids = collector.ToElementIds()

# Check if any dimensions were found
if not dims_to_delete_ids or dims_to_delete_ids.Count == 0:
    forms.alert("No dimensions found in the current view.", exitscript=True)
else:
    # A transaction is required to modify the Revit model (e.g., delete elements)
    t = DB.Transaction(doc, "Delete All Dimensions in View")
    try:
        t.Start()
        
        # Delete the collected dimension elements
        doc.Delete(dims_to_delete_ids)
        
        t.Commit()
        
        # Notify the user of the successful deletion
        forms.alert("Successfully deleted {} dimension(s) from the current view.".format(dims_to_delete_ids.Count), 
                    title="Deletion Complete")

    except Exception as e:
        # If an error occurs, roll back the transaction to prevent partial changes
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        
        # Log the error and inform the user
        script.get_logger().error("Transaction Failed: {}".format(e))
        forms.alert("An error occurred and the transaction was rolled back.", title="Error")
        
    finally:
        # Always dispose of the transaction object to release memory
        if t is not None:
            t.Dispose()