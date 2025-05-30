# -*- coding: UTF-8 -*-
"""
Deletes all dimension tags in the current active view.
Ensures Python list is converted to .NET collection for API calls.
"""

# Import necessary Revit API modules
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    Transaction,
    ElementId,
)
from Autodesk.Revit.UI import TaskDialog

# Import .NET collection types
import System
from System.Collections.Generic import List  # Pronounced "List of T"

# Get the current Revit document and UI document
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

# Get the active view
active_view = doc.ActiveView

if not active_view:
    TaskDialog.Show("Error", "No active view found. Please open a view and try again.")
else:
    # Start a new transaction
    # Transactions are required to make any changes to the Revit model
    t = Transaction(doc, "Delete Dimensions in View")
    try:
        t.Start()

        # Create a filtered element collector to get all dimension elements in the active view
        # Dimensions belong to the BuiltInCategory.OST_Dimensions
        dimension_collector = (
            FilteredElementCollector(doc, active_view.Id)
            .OfCategory(BuiltInCategory.OST_Dimensions)
            .WhereElementIsNotElementType()
            .ToElements()
        )

        python_list_of_ids = []
        if dimension_collector:
            for dim in dimension_collector:
                # Add the ID of each dimension to a Python list
                python_list_of_ids.append(dim.Id)

            if python_list_of_ids:
                # Convert the Python list of ElementIds to a .NET List<ElementId>
                # This is good practice for API calls expecting .NET collections.
                net_list_of_ids = List[ElementId](python_list_of_ids)

                # Delete all collected dimensions using the .NET collection
                deleted_count = net_list_of_ids.Count  # Use .Count for .NET collections
                doc.Delete(net_list_of_ids)

                TaskDialog.Show(
                    "Success",
                    "Successfully deleted {} dimension(s) from the current view: '{}'.".format(
                        deleted_count, active_view.Name
                    ),
                )
            else:
                TaskDialog.Show(
                    "Info",
                    "No dimensions found in the current view: '{}'.".format(
                        active_view.Name
                    ),
                )
        else:
            TaskDialog.Show(
                "Info",
                "No dimensions found in the current view: '{}'.".format(
                    active_view.Name
                ),
            )

        # Commit the transaction
        t.Commit()

    except Exception as e:
        # If an error occurs, roll back the transaction
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        TaskDialog.Show("Error", "An error occurred: {}".format(str(e)))

    finally:
        # Dispose of the transaction object
        if t is not None:
            t.Dispose()
