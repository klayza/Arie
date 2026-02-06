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
_debug_records = []


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
        return None, None, {"error": "View has no crop box."}

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

    debug_info = {
        "crop_min_z": crop_min.Z,
        "crop_max_z": crop_max.Z,
        "floor_candidates": [],
        "ceiling_candidates": [],
        "floor_source": None,
        "ceiling_source": None,
        "notes": [],
        "padding_ft": pad_ft,
    }

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

        overlaps = _overlaps_2d(vmin, vmax, crop_min, crop_max)
        debug_info["floor_candidates"].append({
            "element_id": f.Id.IntegerValue,
            "top_z": vmax.Z,
            "overlaps_crop": overlaps,
        })
        if not overlaps:
            continue

        # floor "top" in view-local Z is vmax.Z
        f_top = vmax.Z
        if f_top <= z0 + 1e-6:
            if best_floor_z is None or f_top > best_floor_z:
                best_floor_z = f_top
                debug_info["floor_source"] = "floor-element"

    # scan ceilings
    for c in ceilings:
        bbm = _safe_bbox(c)
        if not bbm:
            continue
        vbb = _transform_bbox_to_view_local(bbm, inv_t)
        if not vbb:
            continue
        vmin, vmax = vbb

        overlaps = _overlaps_2d(vmin, vmax, crop_min, crop_max)
        debug_info["ceiling_candidates"].append({
            "element_id": c.Id.IntegerValue,
            "bottom_z": vmin.Z,
            "overlaps_crop": overlaps,
        })
        if not overlaps:
            continue

        # ceiling "bottom" in view-local Z is vmin.Z
        c_bot = vmin.Z
        if c_bot >= z0 - 1e-6:
            if best_ceil_z is None or c_bot < best_ceil_z:
                best_ceil_z = c_bot
                debug_info["ceiling_source"] = "ceiling-element"

    # fallback to levels if nothing found
    if best_floor_z is None or best_ceil_z is None:
        fb_floor, fb_ceil = _nearest_levels_fallback(view, z0)
        if fb_floor is not None and best_floor_z is None:
            best_floor_z = fb_floor
            debug_info["floor_source"] = "level-fallback"
        if fb_ceil is not None and best_ceil_z is None:
            best_ceil_z = fb_ceil
            debug_info["ceiling_source"] = "level-fallback"

    if best_floor_z is None and best_ceil_z is None:
        debug_info["notes"].append("No floor, ceiling, or level bounds detected.")
        return None, None, debug_info

    # apply padding if we found values
    if best_floor_z is not None:
        best_floor_z = best_floor_z - pad_ft
        debug_info["notes"].append("Applied floor padding of {:.3f} ft.".format(pad_ft))
    if best_ceil_z is not None:
        best_ceil_z = best_ceil_z + pad_ft
        debug_info["notes"].append("Applied ceiling padding of {:.3f} ft.".format(pad_ft))

    return best_floor_z, best_ceil_z, debug_info


def _apply_template_and_crop(view, template_view, pad_ft=0.10):
    # Apply template
    record = {
        "view_name": view.Name,
        "view_id": view.Id.IntegerValue,
        "template_name": template_view.Name if template_view else None,
        "initial_crop_min_z": None,
        "initial_crop_max_z": None,
        "new_crop_min_z": None,
        "new_crop_max_z": None,
        "find_debug": None,
        "messages": [],
    }
    _debug_records.append(record)
    try:
        view.ViewTemplateId = template_view.Id
        record["messages"].append("Applied template '{}'.".format(template_view.Name))
    except Exception as e:
        output.print_md("Template apply failed for view '{}': {}".format(view.Name, e))
        record["messages"].append("Template apply failed: {}".format(e))

    # Crop height to nearest floor/ceiling
    cb = view.CropBox
    if cb is None:
        output.print_md("View '{}' has no CropBox; skipping crop adjustment.".format(view.Name))
        record["messages"].append("No crop box found; skipped crop adjustment.")
        return

    record["initial_crop_min_z"] = cb.Min.Z
    record["initial_crop_max_z"] = cb.Max.Z

    floor_z, ceil_z, find_debug = _find_nearest_floor_and_ceiling_z(view, pad_ft=pad_ft)
    record["find_debug"] = find_debug
    if floor_z is None and ceil_z is None:
        output.print_md("No floor/ceiling/level bounds found for view '{}'; leaving crop unchanged.".format(view.Name))
        record["messages"].append("No usable bounds detected; crop left unchanged.")
        return

    # If only one bound was found, keep the other side as-is.
    new_min_z = cb.Min.Z if floor_z is None else floor_z
    new_max_z = cb.Max.Z if ceil_z is None else ceil_z

    # sanity: don't invert
    if new_max_z <= new_min_z:
        output.print_md("Crop bounds invalid for view '{}'; leaving crop unchanged.".format(view.Name))
        record["messages"].append("Computed crop bounds invalid (max <= min); skipped update.")
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
        record["new_crop_min_z"] = new_min_z
        record["new_crop_max_z"] = new_max_z
        record["messages"].append("Crop updated successfully.")
    except Exception as e:
        output.print_md("Failed to set CropBox for view '{}': {}".format(view.Name, e))
        record["messages"].append("Failed to set crop box: {}".format(e))


def _print_debug_report(records):
    if not records:
        output.print_md("No debug data recorded.")
        return

    output.print_md("### Debug Report")
    for rec in records:
        output.print_md("**View:** {} (ID {})".format(rec["view_name"], rec["view_id"]))
        output.print_md("* Template: {}".format(rec["template_name"] or "none"))
        if rec["initial_crop_min_z"] is not None and rec["initial_crop_max_z"] is not None:
            output.print_md("* Crop Z before: min {:.3f} ft, max {:.3f} ft".format(
                rec["initial_crop_min_z"], rec["initial_crop_max_z"]))
        else:
            output.print_md("* Crop Z before: unknown")

        if rec["new_crop_min_z"] is not None or rec["new_crop_max_z"] is not None:
            output.print_md("* Crop Z after: min {} ft, max {} ft".format(
                "{:.3f}".format(rec["new_crop_min_z"]) if rec["new_crop_min_z"] is not None else "unchanged",
                "{:.3f}".format(rec["new_crop_max_z"]) if rec["new_crop_max_z"] is not None else "unchanged"))
        else:
            output.print_md("* Crop Z after: unchanged")

        find_debug = rec.get("find_debug") or {}
        if find_debug.get("error"):
            output.print_md("* Detection error: {}".format(find_debug["error"]))
        else:
            output.print_md("* Floor source: {}".format(find_debug.get("floor_source") or "none"))
            output.print_md("* Ceiling source: {}".format(find_debug.get("ceiling_source") or "none"))

            floor_cands = find_debug.get("floor_candidates") or []
            if floor_cands:
                output.print_md("    - Floor candidates: {}".format(
                    ", ".join("#{} top {:.3f} ({})".format(
                        c["element_id"], c.get("top_z", 0.0),
                        "overlap" if c.get("overlaps_crop") else "no overlap") for c in floor_cands)))

            ceil_cands = find_debug.get("ceiling_candidates") or []
            if ceil_cands:
                output.print_md("    - Ceiling candidates: {}".format(
                    ", ".join("#{} bottom {:.3f} ({})".format(
                        c["element_id"], c.get("bottom_z", 0.0),
                        "overlap" if c.get("overlaps_crop") else "no overlap") for c in ceil_cands)))

            if find_debug.get("notes"):
                for note in find_debug.get("notes"):
                    output.print_md("    - Note: {}".format(note))

        if rec["messages"]:
            for msg in rec["messages"]:
                output.print_md("    - Message: {}".format(msg))

        output.print_md("\n")


def main():
    _debug_records[:] = []
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
    _print_debug_report(_debug_records)


if __name__ == "__main__":
    main()
