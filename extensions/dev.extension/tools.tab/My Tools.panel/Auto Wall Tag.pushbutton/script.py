# -*- coding: UTF-8 -*-
"""
Auto-tags walls in the current view if their Wall Type name meets criteria.
Extracts a label (e.g., "A1" from "SS TYPE A1...") from the Wall Type name,
sets it as the 'Type Mark', and then places a Wall Tag with a leader,
offset 200mm from the wall.
"""

from pyrevit import revit, DB, UI
from pyrevit import script
from pyrevit import forms

# Import Revit Exceptions for specific error handling
from Autodesk.Revit import Exceptions as RevitExceptions

# Get current document, UIDocument, and active view
doc = revit.doc
uidoc = revit.uidoc
view = revit.active_view

if not view:
    forms.alert(
        "No active view found. Please run the script in a view.", exitscript=True
    )

output = script.get_output()

# --- Constants ---
MM_TO_FEET = 1.0 / 304.8
TAG_OFFSET_MM = 200.0
TAG_OFFSET_FEET = TAG_OFFSET_MM * MM_TO_FEET


def get_wall_tag_type(document):
    """Finds the first available Wall Tag type (FamilySymbol) in the document."""
    collector = (
        DB.FilteredElementCollector(document)
        .OfCategory(DB.BuiltInCategory.OST_WallTags)
        .WhereElementIsElementType()
        .ToElements()
    )
    if collector:
        return collector[0]
    return None


def main():
    wall_tag_type = get_wall_tag_type(doc)
    if not wall_tag_type:
        forms.alert(
            "No Wall Tag families (types) loaded. "
            "Please load a Wall Tag family whose label reads 'Type Mark'.",
            exitscript=True,
        )

    output.print_md(
        "Using Wall Tag Type: **{}**".format(revit.query.get_name(wall_tag_type))
    )

    walls_in_view = (
        DB.FilteredElementCollector(doc, view.Id)
        .OfCategory(DB.BuiltInCategory.OST_Walls)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    if not walls_in_view:
        forms.alert("No walls found in the current view.", exitscript=True)

    output.print_md(
        "Found **{}** walls. Processing for tagging...".format(len(walls_in_view))
    )

    with DB.Transaction(doc, "Auto Tag Walls Conditionally") as t:
        t.Start()

        processed_wall_type_details = (
            {}
        )  # Stores {ElementId_WallType: bool_is_taggable}
        tags_created_count = 0
        warnings_count = 0
        processed_msg_shown_for_type = (
            set()
        )  # To avoid repetitive messages for same type

        for wall in walls_in_view:
            wall_type = doc.GetElement(wall.GetTypeId())
            if not wall_type:
                warnings_count += 1
                continue

            is_taggable_type = processed_wall_type_details.get(wall_type.Id)

            if is_taggable_type is None:  # Not processed yet, determine if taggable
                current_type_is_taggable = False  # Default for this type
                type_name_param = wall_type.get_Parameter(
                    DB.BuiltInParameter.SYMBOL_NAME_PARAM
                )
                type_name = ""

                if type_name_param:
                    type_name = type_name_param.AsString()

                if type_name and "TYPE" in type_name.upper():
                    name_parts = type_name.split(" ")
                    if len(name_parts) >= 3:
                        extracted_label = name_parts[
                            2
                        ]  # e.g., "A1" from "SS TYPE A1 ..."

                        type_mark_param = wall_type.LookupParameter(
                            "Type Mark"
                        ) or wall_type.get_Parameter(
                            DB.BuiltInParameter.ALL_MODEL_TYPE_MARK
                        )

                        if type_mark_param and not type_mark_param.IsReadOnly:
                            try:
                                current_tm_value = type_mark_param.AsString()
                                if current_tm_value != extracted_label:
                                    type_mark_param.Set(extracted_label)
                                    if wall_type.Id not in processed_msg_shown_for_type:
                                        output.print_md(
                                            "- Updated Type Mark for Wall Type '{}' to '{}'".format(
                                                type_name, extracted_label
                                            )
                                        )
                                current_type_is_taggable = (
                                    True  # Successfully set/verified Type Mark
                                )
                            except Exception as e_set:
                                if wall_type.Id not in processed_msg_shown_for_type:
                                    output.print_md(
                                        "**WARNING:** Wall Type '{}': Failed to set Type Mark to '{}'. Error: {}".format(
                                            type_name, extracted_label, e_set
                                        )
                                    )
                                warnings_count += 1
                        else:
                            if wall_type.Id not in processed_msg_shown_for_type:
                                output.print_md(
                                    "**WARNING:** Wall Type '{}': 'Type Mark' parameter not found or is read-only.".format(
                                        type_name
                                    )
                                )
                            warnings_count += 1
                    else:  # Name has "TYPE" but not enough parts
                        if wall_type.Id not in processed_msg_shown_for_type:
                            output.print_md(
                                "**WARNING:** Wall Type '{}': Contains 'TYPE' but name parts < 3 (expected '... TYPE LABEL ...').".format(
                                    type_name
                                )
                            )
                        warnings_count += 1
                else:  # Name does not contain "TYPE" or is empty
                    if (
                        type_name and wall_type.Id not in processed_msg_shown_for_type
                    ):  # Only message if name exists
                        output.print_md(
                            "- Wall Type '{}': Name does not contain 'TYPE', skipping.".format(
                                type_name
                            )
                        )
                    # warnings_count +=1 # Not strictly a warning if it's just a skip condition

                processed_wall_type_details[wall_type.Id] = current_type_is_taggable
                is_taggable_type = current_type_is_taggable
                processed_msg_shown_for_type.add(wall_type.Id)

            if is_taggable_type:  # Proceed to tag this wall instance
                try:
                    location_curve = wall.Location
                    if isinstance(location_curve, DB.LocationCurve):
                        curve = location_curve.Curve
                        mid_point_on_curve = curve.Evaluate(0.5, True)

                        tangent = curve.ComputeDerivatives(0.5, True).BasisX.Normalize()

                        # Offset direction perpendicular to tangent in XY plane (for plan views)
                        offset_dir = tangent.CrossProduct(DB.XYZ.BasisZ).Normalize()
                        if (
                            offset_dir.IsZeroLength()
                        ):  # If tangent is vertical (wall line is vertical in plan)
                            offset_dir = DB.XYZ.BasisX  # Default offset along X

                        tag_head_position = (
                            mid_point_on_curve + offset_dir * TAG_OFFSET_FEET
                        )

                        DB.IndependentTag.Create(
                            doc,
                            wall_tag_type.Id,
                            view.Id,
                            DB.Reference(wall),
                            True,  # Add Leader
                            DB.TagOrientation.Horizontal,
                            tag_head_position,
                        )
                        tags_created_count += 1
                    else:
                        output.print_md(
                            "**WARNING:** Wall ID {}: No LocationCurve found. Cannot place tag.".format(
                                wall.Id.ToString()
                            )
                        )
                        warnings_count += 1
                except RevitExceptions.InvalidOperationException:
                    output.print_md(
                        "**WARNING:** Wall ID {}: Curve cannot be evaluated (e.g., unbound). Cannot place tag.".format(
                            wall.Id.ToString()
                        )
                    )
                    warnings_count += 1
                except Exception as e_tag:
                    output.print_md(
                        "**ERROR:** Failed to tag Wall ID {}: {}".format(
                            wall.Id.ToString(), e_tag
                        )
                    )
                    warnings_count += 1

        # --- Transaction Commit/Rollback Logic ---
        if tags_created_count > 0:
            t.Commit()
            message = "Successfully created {} wall tag(s).".format(tags_created_count)
            if warnings_count > 0:
                message += "\nEncountered {} warning(s)/error(s). Check output for details.".format(
                    warnings_count
                )
            forms.alert(message, title="Tagging Complete")
        else:
            t.RollBack()
            message = "No tags were created."
            if warnings_count > 0:
                message += "\nEncountered {} warning(s)/error(s). Check output for details.".format(
                    warnings_count
                )
            else:
                message += " Ensure walls meet criteria (TYPE in name, correct format) and a Wall Tag family is loaded."
            forms.alert(message, title="Tagging Result")


if __name__ == "__main__":
    main()
