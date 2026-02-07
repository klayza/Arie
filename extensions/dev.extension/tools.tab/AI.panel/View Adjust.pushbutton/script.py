# -*- coding: utf-8 -*-
# pyRevit script: apply a chosen view template to elevation views
# referenced by selected elevation markers (or selected elevation views).

from pyrevit import revit, DB, forms, script

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()


def _is_elev_view(v):
    try:
        return v.ViewType in (DB.ViewType.Elevation, DB.ViewType.Section, DB.ViewType.Detail)
    except Exception:
        return False


def _pick_view_template():
    all_views = DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements()
    templates = [v for v in all_views if v.IsTemplate]
    if not templates:
        forms.alert("No view templates found in this project.", exitscript=True)
        return None

    display = []
    map_back = {}
    for v in templates:
        name = u"{}  ({})".format(v.Name, str(v.ViewType))
        display.append(name)
        map_back[name] = v

    chosen = forms.SelectFromList.show(
        sorted(display),
        multiselect=False,
        title="Pick a View Template",
        button_name="Use Template"
    )
    if not chosen:
        script.exit()
    return map_back[chosen]


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


def _auto_fit_view_to_floor_and_ceiling(view, floors, ceilings, pad_ft=0.10):
    cb = view.CropBox
    if cb is None:
        output.print_md("View '{}' has no CropBox; skipping auto-fit.".format(view.Name))
        return False

    try:
        view.CropBoxActive = True
    except Exception:
        pass

    inv_t = cb.Transform.Inverse
    crop_min = cb.Min
    crop_max = cb.Max

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
        output.print_md("No floor/ceiling candidates found for view '{}'.".format(view.Name))
        return False

    best_floor = None
    if floor_cands:
        floor_cands.sort(key=lambda x: (x["dist"], -x["top_y"]))
        best_floor = floor_cands[0]

    best_ceil = None
    if ceil_cands:
        ceil_cands.sort(key=lambda x: (x["dist"], x["bot_y"]))
        best_ceil = ceil_cands[0]

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
        output.print_md("Computed crop invalid for view '{}'.".format(view.Name))
        return False

    new_cb = DB.BoundingBoxXYZ()
    new_cb.Transform = cb.Transform
    new_cb.Min = DB.XYZ(cb.Min.X, new_min_y, cb.Min.Z)
    new_cb.Max = DB.XYZ(cb.Max.X, new_max_y, cb.Max.Z)

    try:
        view.CropBox = new_cb
    except Exception as e:
        output.print_md("Failed to set CropBox for view '{}': {}".format(view.Name, e))
        return False

    if best_floor:
        output.print_md("Selected floor for '{}': {} (ID {})".format(view.Name, best_floor["name"], best_floor["id"]))
    if best_ceil:
        output.print_md("Selected ceiling for '{}': {} (ID {})".format(view.Name, best_ceil["name"], best_ceil["id"]))
    return True


def _get_selected_markers_and_views():
    markers = []
    views = []
    sel_ids = list(uidoc.Selection.GetElementIds())
    for eid in sel_ids:
        el = doc.GetElement(eid)
        if isinstance(el, DB.ElevationMarker):
            markers.append(el)
        elif isinstance(el, DB.View) and _is_elev_view(el) and (not el.IsTemplate):
            views.append(el)
    return markers, views


def _views_from_markers(markers):
    views = []
    seen = set()
    for marker in markers:
        # Elevation markers can have up to 4 views (sometimes more depending on type).
        for idx in range(0, 8):
            try:
                vid = marker.GetViewId(idx)
            except Exception:
                continue
            if not vid or vid == DB.ElementId.InvalidElementId:
                continue
            if vid.IntegerValue in seen:
                continue
            seen.add(vid.IntegerValue)
            v = doc.GetElement(vid)
            if isinstance(v, DB.View) and _is_elev_view(v) and (not v.IsTemplate):
                views.append(v)
    return views


def apply_template_to_selected_elevations():
    markers, direct_views = _get_selected_markers_and_views()
    if not markers and not direct_views:
        forms.alert("Select one or more elevation markers (or elevation views) and run again.", exitscript=True)
        return

    views = _views_from_markers(markers)
    # include directly-selected views
    by_id = {v.Id.IntegerValue: v for v in views}
    for v in direct_views:
        by_id[v.Id.IntegerValue] = v
    views = list(by_id.values())

    if not views:
        forms.alert("No elevation views found from the selected markers.", exitscript=True)
        return

    template = _pick_view_template()
    if not template:
        return

    floors = DB.FilteredElementCollector(doc)\
        .OfCategory(DB.BuiltInCategory.OST_Floors)\
        .WhereElementIsNotElementType()\
        .ToElements()
    ceilings = DB.FilteredElementCollector(doc)\
        .OfCategory(DB.BuiltInCategory.OST_Ceilings)\
        .WhereElementIsNotElementType()\
        .ToElements()

    applied = 0
    adjusted = 0
    with revit.Transaction("Apply view template to elevations"):
        for v in views:
            try:
                v.ViewTemplateId = template.Id
                applied += 1
            except Exception as e:
                output.print_md("Template apply failed for view '{}': {}".format(v.Name, e))
                continue
            if _auto_fit_view_to_floor_and_ceiling(v, floors, ceilings, pad_ft=0.10):
                adjusted += 1

    output.print_md("Applied template '{}' to {} view(s).".format(template.Name, applied))
    output.print_md("Adjusted crop for {} view(s).".format(adjusted))


if __name__ == "__main__":
    apply_template_to_selected_elevations()
