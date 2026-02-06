# -*- coding: utf-8 -*-
# pyRevit script: apply a chosen view template and auto-crop elevation/section views
# so their top/bottom snap to the nearest ceiling/floor found within the view crop region.
#
# How to use:
# 1) Select one or more Elevation/Section views (in Project Browser), or run while an elevation/section is active.
# 2) Run the tool, pick a view template, and it will apply the template + adjust crop height.

from __future__ import print_function

from pyrevit import revit, DB, forms, script

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()


def _is_elev_or_section(v):
    try:
        vt = v.ViewType
        return vt in (DB.ViewType.Elevation, DB.ViewType.Section, DB.ViewType.Detail)
    except Exception:
        return False


def _get_selected_views_or_active():
    views = []
    sel_ids = list(uidoc.Selection.GetElementIds())
    if sel_ids:
        for eid in sel_ids:
            el = doc.GetElement(eid)
            if isinstance(el, DB.View) and (not el.IsTemplate) and _is_elev_or_section(el):
                views.append(el)

    if not views:
        av = doc.ActiveView
        if isinstance(av, DB.View) and (not av.IsTemplate) and _is_elev_or_section(av):
            views = [av]

    return views


def _pick_view_template():
    all_views = DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements()
    templates = [v for v in all_views if v.IsTemplate]
    if not templates:
        forms.alert("No view templates found in this project.", exitscript=True)

    # show name + type to reduce ambiguity
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


def _safe_bbox(el):
    # Using model bbox is more consistent than view-specific bbox for ceilings/floors.
    try:
        return el.get_BoundingBox(None)
    except Exception:
        return None


def _overlaps_2d(a_min, a_max, b_min, b_max):
    # 2D overlap in X and Y (view-local coords)
    if a_max.X < b_min.X or a_min.X > b_max.X:
        return False
    if a_max.Y < b_min.Y or a_min.Y > b_max.Y:
        return False
    return True


def _transform_bbox_to_view_local(bb_model, inv_t):
    # Convert model bbox corners into view-local coords by transforming 8 corners.
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


def _nearest_levels_fallback(view, z0):
    # Fallback: if no floor/ceiling elements are found, use nearest levels by elevation.
    lvls = list(DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements())
    if not lvls:
        return None, None

    # z0 is in view-local coords, but for typical elevation/section views, view-local Z matches world Z only
    # if the view is vertical and not rotated around X/Y. Since this is a fallback, we use world elevation.
    # We get a world Z reference by transforming the crop-box center back to model coords.
    try:
        cb = view.CropBox
        t = cb.Transform
        center_local = DB.XYZ((cb.Min.X + cb.Max.X) / 2.0, (cb.Min.Y + cb.Max.Y) / 2.0, z0)
        center_world = t.OfPoint(center_local)
        world_z0 = center_world.Z
    except Exception:
        world_z0 = None

    if world_z0 is None:
        return None, None

    above = [lvl.Elevation for lvl in lvls if lvl.Elevation >= world_z0]
    below = [lvl.Elevation for lvl in lvls if lvl.Elevation <= world_z0]
    if not above or not below:
        return None, None

    nearest_above = min(above)
    nearest_below = max(below)

    # Convert those world elevations back into view-local Z
    try:
        inv = view.CropBox.Transform.Inverse
        # pick a point on the view plane with that Z; X/Y don't matter much for Z extraction after inverse
        p_above_world = DB.XYZ(center_world.X, center_world.Y, nearest_above)
        p_below_world = DB.XYZ(center_world.X, center_world.Y, nearest_below)
        z_above_local = inv.OfPoint(p_above_world).Z
        z_below_local = inv.OfPoint(p_below_world).Z
        return z_below_local, z_above_local
    except Exception:
        return None, None


def _find_nearest_floor_and_ceiling_z(view, pad_ft=0.10):
    # Works in the view's crop-box local coordinate system.
    cb = view.CropBox
    if cb is None:
        return None

    # Make sure crop box is active so changes stick.
    try:
        view.CropBoxActive = True
    except Exception:
        pass

    inv_t = cb.Transform.Inverse

    crop_min = cb.Min
    crop_max = cb.Max
    z0 = (crop_min.Z + crop_max.Z) / 2.0

    floors = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Floors)\
        .WhereElementIsNotElementType().ToElements()
    ceilings = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Ceilings)\
        .WhereElementIsNotElementType().ToElements()

    best_floor_z = None   # highest below
    best_ceil_z = None    # lowest above

    # scan floors
    for f in floors:
        bbm = _safe_bbox(f)
        if not bbm:
            continue
        vbb = _transform_bbox_to_view_local(bbm, inv_t)
        if not vbb:
            continue
        vmin, vmax = vbb

        # require overlap with crop region in X/Y to avoid grabbing unrelated floors
        if not _overlaps_2d(vmin, vmax, crop_min, crop_max):
            continue

        # floor "top" in view-local Z is vmax.Z
        f_top = vmax.Z
        if f_top <= z0 + 1e-6:
            if best_floor_z is None or f_top > best_floor_z:
                best_floor_z = f_top

    # scan ceilings
    for c in ceilings:
        bbm = _safe_bbox(c)
        if not bbm:
            continue
        vbb = _transform_bbox_to_view_local(bbm, inv_t)
        if not vbb:
            continue
        vmin, vmax = vbb

        if not _overlaps_2d(vmin, vmax, crop_min, crop_max):
            continue

        # ceiling "bottom" in view-local Z is vmin.Z
        c_bot = vmin.Z
        if c_bot >= z0 - 1e-6:
            if best_ceil_z is None or c_bot < best_ceil_z:
                best_ceil_z = c_bot

    # fallback to levels if nothing found
    if best_floor_z is None or best_ceil_z is None:
        fb_floor, fb_ceil = _nearest_levels_fallback(view, z0)
        if best_floor_z is None:
            best_floor_z = fb_floor
        if best_ceil_z is None:
            best_ceil_z = fb_ceil

    if best_floor_z is None and best_ceil_z is None:
        return None

    # apply padding if we found values
    if best_floor_z is not None:
        best_floor_z = best_floor_z - pad_ft
    if best_ceil_z is not None:
        best_ceil_z = best_ceil_z + pad_ft

    return best_floor_z, best_ceil_z


def _apply_template_and_crop(view, template_view, pad_ft=0.10):
    # Apply template
    try:
        view.ViewTemplateId = template_view.Id
    except Exception as e:
        output.print_md("Template apply failed for view '{}': {}".format(view.Name, e))

    # Crop height to nearest floor/ceiling
    cb = view.CropBox
    if cb is None:
        output.print_md("View '{}' has no CropBox; skipping crop adjustment.".format(view.Name))
        return

    res = _find_nearest_floor_and_ceiling_z(view, pad_ft=pad_ft)
    if not res:
        output.print_md("No floor/ceiling/level bounds found for view '{}'; leaving crop unchanged.".format(view.Name))
        return

    floor_z, ceil_z = res
    # If only one bound was found, keep the other side as-is.
    new_min_z = cb.Min.Z if floor_z is None else floor_z
    new_max_z = cb.Max.Z if ceil_z is None else ceil_z

    # sanity: don't invert
    if new_max_z <= new_min_z:
        output.print_md("Crop bounds invalid for view '{}'; leaving crop unchanged.".format(view.Name))
        return

    new_cb = DB.BoundingBoxXYZ()
    new_cb.Transform = cb.Transform
    new_cb.Min = DB.XYZ(cb.Min.X, cb.Min.Y, new_min_z)
    new_cb.Max = DB.XYZ(cb.Max.X, cb.Max.Y, new_max_z)

    try:
        view.CropBoxActive = True
    except Exception:
        pass
    try:
        view.CropBox = new_cb
    except Exception as e:
        output.print_md("Failed to set CropBox for view '{}': {}".format(view.Name, e))


def main():
    views = _get_selected_views_or_active()
    if not views:
        forms.alert("Select one or more Elevation/Section views (or activate one) and run again.", exitscript=True)

    template = _pick_view_template()

    # small, predictable padding (~1.2 inches) unless your office wants something else
    pad_ft = 0.10

    with revit.Transaction("Auto-crop elevations to floor/ceiling + apply template"):
        for v in views:
            _apply_template_and_crop(v, template, pad_ft=pad_ft)

    forms.alert("Done. Updated {} view(s).".format(len(views)), title="pyRevit")


if __name__ == "__main__":
    main()
