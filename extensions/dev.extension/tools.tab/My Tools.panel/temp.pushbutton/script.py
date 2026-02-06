# -*- coding: utf-8 -*-
"""
Finds all text notes with leaders and all wall tags in the project and 
displays them in a clickable table. Clicking on an element ID in the table 
will navigate to that element in a suitable view.

This version includes a fix for the AttributeError with certain tag types
like SpanDirectionSymbol.
"""

from pyrevit import revit, DB, UI
from pyrevit import script
from pyrevit import forms

import System
from System.Collections.Generic import List

# Get the current document and UI document
doc = revit.doc
uidoc = revit.uidoc

# Get the pyRevit output window
output = script.get_output()

# --- Helpers ---
def _transform_bbox_to_view_local(bb_model, inv_t):
    pts = []
    try:
        mn = bb_model.Min
        mx = bb_model.Max
        corners = [
            DB.XYZ(mn.X, mn.Y, mn.Z),
            DB.XYZ(mn.X, mn.Y, mx.Z),
            DB.XYZ(mn.X, mx.Y, mn.Z),
            DB.XYZ(mn.X, mx.Y, mx.Z),
            DB.XYZ(mx.X, mn.Y, mn.Z),
            DB.XYZ(mx.X, mn.Y, mx.Z),
            DB.XYZ(mx.X, mx.Y, mn.Z),
            DB.XYZ(mx.X, mx.Y, mx.Z),
        ]
        for p in corners:
            pts.append(inv_t.OfPoint(p))
    except Exception:
        return None

    vmin = DB.XYZ(min(p.X for p in pts), min(p.Y for p in pts), min(p.Z for p in pts))
    vmax = DB.XYZ(max(p.X for p in pts), max(p.Y for p in pts), max(p.Z for p in pts))
    return vmin, vmax

# --- Temp Logic: expand active elevation crop ---
def expand_active_elevation_crop_by_100ft():
    view = doc.ActiveView
    if not isinstance(view, DB.View):
        forms.alert("No active view found.", exitscript=True)
        return

    if view.ViewType not in (DB.ViewType.Elevation, DB.ViewType.Section, DB.ViewType.Detail):
        forms.alert("Active view is not an elevation/section/detail view.", exitscript=True)
        return

    cb = view.CropBox
    if cb is None:
        forms.alert("Active view has no crop box.", exitscript=True)
        return

    try:
        view.CropBoxActive = True
    except Exception:
        pass

    # Expand width/height by 100' total (50' each side) in view-local X/Y
    expand = 50.0
    new_cb = DB.BoundingBoxXYZ()
    new_cb.Transform = cb.Transform
    new_cb.Min = DB.XYZ(cb.Min.X - expand, cb.Min.Y - expand, cb.Min.Z)
    new_cb.Max = DB.XYZ(cb.Max.X + expand, cb.Max.Y + expand, cb.Max.Z)

    with revit.Transaction("Temp expand elevation crop by 100ft"):
        view.CropBox = new_cb

    output.print_md("Expanded crop for view '{}' by 100' width/height.".format(view.Name))
    list_floors_and_ceilings_in_active_view()


def list_floors_and_ceilings_in_active_view():
    view = doc.ActiveView
    if not isinstance(view, DB.View):
        forms.alert("No active view found.", exitscript=True)
        return

    floors = DB.FilteredElementCollector(doc, view.Id)\
        .OfCategory(DB.BuiltInCategory.OST_Floors)\
        .WhereElementIsNotElementType()\
        .ToElements()

    ceilings = DB.FilteredElementCollector(doc, view.Id)\
        .OfCategory(DB.BuiltInCategory.OST_Ceilings)\
        .WhereElementIsNotElementType()\
        .ToElements()

    inv_t = view.CropBox.Transform.Inverse if view.CropBox else None

    output.print_md("### Floors/Ceilings in Active View: {}".format(view.Name))
    output.print_md("* Floors: {}".format(len(floors)))
    output.print_md("* Ceilings: {}".format(len(ceilings)))

    if floors:
        output.print_md("#### Floors")
        for f in floors:
            z_info = ""
            if inv_t:
                bb = f.get_BoundingBox(None)
                vbb = _transform_bbox_to_view_local(bb, inv_t) if bb else None
                if vbb:
                    vmin, vmax = vbb
                    z_info = " | Z min {:.3f}, max {:.3f}".format(vmin.Z, vmax.Z)
            output.print_md("- {} (ID {}){}".format(f.Name, f.Id.IntegerValue, z_info))

    if ceilings:
        output.print_md("#### Ceilings")
        for c in ceilings:
            z_info = ""
            if inv_t:
                bb = c.get_BoundingBox(None)
                vbb = _transform_bbox_to_view_local(bb, inv_t) if bb else None
                if vbb:
                    vmin, vmax = vbb
                    z_info = " | Z min {:.3f}, max {:.3f}".format(vmin.Z, vmax.Z)
            output.print_md("- {} (ID {}){}".format(c.Name, c.Id.IntegerValue, z_info))


def auto_fit_active_view_to_floor_and_ceiling(pad_ft=0.10):
    view = doc.ActiveView
    if not isinstance(view, DB.View):
        forms.alert("No active view found.", exitscript=True)
        return

    if view.ViewType not in (DB.ViewType.Elevation, DB.ViewType.Section, DB.ViewType.Detail):
        forms.alert("Active view is not an elevation/section/detail view.", exitscript=True)
        return

    cb = view.CropBox
    if cb is None:
        forms.alert("Active view has no crop box.", exitscript=True)
        return

    try:
        view.CropBoxActive = True
    except Exception:
        pass

    inv_t = cb.Transform.Inverse
    crop_min = cb.Min
    crop_max = cb.Max

    # Collect from the full model, then filter by view-local X/Z so crop height doesn't matter.
    floors = DB.FilteredElementCollector(doc)\
        .OfCategory(DB.BuiltInCategory.OST_Floors)\
        .WhereElementIsNotElementType()\
        .ToElements()

    ceilings = DB.FilteredElementCollector(doc)\
        .OfCategory(DB.BuiltInCategory.OST_Ceilings)\
        .WhereElementIsNotElementType()\
        .ToElements()

    # For elevation/section views, view-local Y is the vertical axis.
    max_thickness_ft = 5.0
    center_x = (crop_min.X + crop_max.X) / 2.0
    center_z = (crop_min.Z + crop_max.Z) / 2.0
    all_floor_cands = []
    all_ceil_cands = []

    for f in floors:
        bb = f.get_BoundingBox(None)
        vbb = _transform_bbox_to_view_local(bb, inv_t) if bb else None
        if not vbb:
            continue
        vmin, vmax = vbb
        if vmax.X < crop_min.X or vmin.X > crop_max.X:
            continue
        if vmax.Z < crop_min.Z or vmin.Z > crop_max.Z:
            continue
        thickness = abs(vmax.Y - vmin.Y)
        cx = (vmin.X + vmax.X) / 2.0
        cz = (vmin.Z + vmax.Z) / 2.0
        dist = ((cx - center_x) ** 2 + (cz - center_z) ** 2) ** 0.5
        all_floor_cands.append({
            "top_y": vmax.Y,
            "dist": dist,
            "thickness": thickness,
            "id": f.Id.IntegerValue,
            "name": f.Name,
        })

    for c in ceilings:
        bb = c.get_BoundingBox(None)
        vbb = _transform_bbox_to_view_local(bb, inv_t) if bb else None
        if not vbb:
            continue
        vmin, vmax = vbb
        if vmax.X < crop_min.X or vmin.X > crop_max.X:
            continue
        if vmax.Z < crop_min.Z or vmin.Z > crop_max.Z:
            continue
        thickness = abs(vmax.Y - vmin.Y)
        cx = (vmin.X + vmax.X) / 2.0
        cz = (vmin.Z + vmax.Z) / 2.0
        dist = ((cx - center_x) ** 2 + (cz - center_z) ** 2) ** 0.5
        all_ceil_cands.append({
            "bot_y": vmin.Y,
            "dist": dist,
            "thickness": thickness,
            "id": c.Id.IntegerValue,
            "name": c.Name,
        })

    floor_cands = [c for c in all_floor_cands if c["thickness"] <= max_thickness_ft]
    ceil_cands = [c for c in all_ceil_cands if c["thickness"] <= max_thickness_ft]
    if not floor_cands:
        floor_cands = all_floor_cands
    if not ceil_cands:
        ceil_cands = all_ceil_cands

    if not floor_cands and not ceil_cands:
        forms.alert("No floor or ceiling bounds found in this view.", exitscript=True)
        return

    # Pick floor closest to view center (then highest if tie).
    best_floor = None
    if floor_cands:
        floor_cands.sort(key=lambda x: (x["dist"], -x["top_y"]))
        best_floor = floor_cands[0]

    # Pick ceiling closest to view center (then lowest if tie).
    best_ceil = None
    if ceil_cands:
        ceil_cands.sort(key=lambda x: (x["dist"], x["bot_y"]))
        best_ceil = ceil_cands[0]

    # If we have a floor, prefer a ceiling above it.
    if best_floor and ceil_cands:
        above = [c for c in ceil_cands if c["bot_y"] > best_floor["top_y"] + 1e-6]
        if above:
            above.sort(key=lambda x: (x["dist"], x["bot_y"]))
            best_ceil = above[0]

    best_floor_y = best_floor["top_y"] if best_floor else None
    best_ceil_y = best_ceil["bot_y"] if best_ceil else None

    if best_floor_y is not None:
        best_floor_y -= pad_ft
    if best_ceil_y is not None:
        best_ceil_y += pad_ft

    new_min_y = cb.Min.Y if best_floor_y is None else best_floor_y
    new_max_y = cb.Max.Y if best_ceil_y is None else best_ceil_y

    if new_max_y <= new_min_y:
        output.print_md("Computed crop invalid: min {:.3f}, max {:.3f}".format(new_min_y, new_max_y))
        output.print_md("Crop Y before: min {:.3f}, max {:.3f}".format(crop_min.Y, crop_max.Y))
        output.print_md("Floor candidates: {}".format(", ".join(
            "#{} {:.3f}".format(c["id"], c["top_y"]) for c in floor_cands)))
        output.print_md("Ceiling candidates: {}".format(", ".join(
            "#{} {:.3f}".format(c["id"], c["bot_y"]) for c in ceil_cands)))
        forms.alert("Computed crop bounds invalid; no changes applied.", exitscript=True)
        return

    new_cb = DB.BoundingBoxXYZ()
    new_cb.Transform = cb.Transform
    new_cb.Min = DB.XYZ(cb.Min.X, new_min_y, cb.Min.Z)
    new_cb.Max = DB.XYZ(cb.Max.X, new_max_y, cb.Max.Z)

    with revit.Transaction("Auto-fit elevation to floor/ceiling (temp)"):
        view.CropBox = new_cb

    if best_floor:
        output.print_md("Selected floor: {} (ID {})".format(best_floor["name"], best_floor["id"]))
    if best_ceil:
        output.print_md("Selected ceiling: {} (ID {})".format(best_ceil["name"], best_ceil["id"]))
    output.print_md("Auto-fit crop for view '{}': Y min {:.3f}, Y max {:.3f}.".format(
        view.Name, new_min_y, new_max_y))

# --- Main Logic ---
def find_and_display_elements():
    """
    Finds all TextNote elements with leaders and all Wall Tags,
    and displays them in a markdown table.
    """
    found_elements = []

    # 1. Find all TextNotes with leaders
    text_note_collector = DB.FilteredElementCollector(doc)\
                            .OfClass(DB.TextNote)\
                            .WhereElementIsNotElementType()

    for text_note in text_note_collector:
        if text_note.LeaderCount > 0:
            view = doc.GetElement(text_note.OwnerViewId)
            view_name = view.Name if view else "N/A (View Not Found)"
            
            text_content = text_note.Text.replace('\r\n', ' ').replace('\n', ' ')
            if len(text_content) > 60:
                text_content = text_content[:57] + "..."

            found_elements.append({
                'type': 'Text Note',
                'id': text_note.Id,
                'text': text_content,
                'view_name': view_name
            })

    # 2. Find all Wall Tags
    tag_collector = DB.FilteredElementCollector(doc)\
                      .OfClass(DB.IndependentTag)\
                      .WhereElementIsNotElementType()

    for tag in tag_collector:
        # CORRECTED: Safely check if the tag has the 'TaggedLocalElementId' property
        # This prevents errors with types like SpanDirectionSymbol
        if hasattr(tag, 'TaggedLocalElementId'):
            tagged_element_id = tag.TaggedLocalElementId
            if tagged_element_id is not None and tagged_element_id != DB.ElementId.InvalidElementId:
                tagged_element = doc.GetElement(tagged_element_id)
                # Check if the tagged element is a Wall
                if tagged_element and tagged_element.Category:
                    if tagged_element.Category.Id.IntegerValue == int(DB.BuiltInCategory.OST_Walls):
                        view = doc.GetElement(tag.OwnerViewId)
                        view_name = view.Name if view else "N/A (View Not Found)"
                        
                        found_elements.append({
                            'type': 'Wall Tag',
                            'id': tag.Id,
                            'text': tag.TagText,
                            'view_name': view_name
                        })

    # Check if any elements were found
    if not found_elements:
        forms.alert("No text notes with leaders or wall tags found in the project.", exitscript=True)
        return

    # Sort the results by type, then by view name for better organization
    found_elements.sort(key=lambda x: (x['type'], x['view_name']))

    # Print the results to the output window in a markdown table
    output.print_md("### Found Elements ({})".format(len(found_elements)))
    
    # Print table header
    output.print_md("| Type | Element ID | Text / Value | View Name |")
    output.print_md("|:---|:---|:---|:---|")

    # Print table rows
    for info in found_elements:
        # output.linkify creates a clickable link that navigates to the element
        element_id_link = output.linkify(info['id'])
        
        # Format and print the row
        output.print_md("| {} | {} | {} | {} |".format(
            info['type'],
            element_id_link,
            info['text'],
            info['view_name']
        ))

# --- Script Execution ---
if __name__ == "__main__":
    auto_fit_active_view_to_floor_and_ceiling()
