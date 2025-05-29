# pyRevit Script: Dimension All Walls in Current View (Overall Length)

from pyrevit import revit, DB, UI, forms, script

# --- Configuration ---
DEFAULT_OFFSET_MM = 1000  # Default offset for dimension line in millimeters
MIN_WALL_LENGTH_MM = 50  # Minimum wall length in mm to attempt dimensioning

# --- Helper Functions ---


def get_offset_distance_from_user(prompt_message, default_value_mm):
    """Asks user for an offset distance in millimeters and converts to internal units (feet)."""
    dist_str = forms.ask_for_string(
        default=str(default_value_mm), prompt=prompt_message, title="Dimension Offset"
    )
    if dist_str is None:  # User cancelled
        return None
    try:
        dist_mm = float(dist_str)
        if dist_mm <= 0:
            forms.alert(
                "Offset distance must be a positive number.", title="Input Error"
            )
            return None
        # Convert millimeters to Revit's internal units (typically feet)
        return DB.UnitUtils.ConvertToInternalUnits(dist_mm, DB.UnitTypeId.Millimeters)
    except ValueError:
        forms.alert(
            "Invalid input. Please enter a valid number for the offset.",
            title="Input Error",
        )
        return None


def get_wall_solid(wall, view_for_options):
    """Gets the solid geometry of a wall, considering the view context."""
    options = DB.Options()
    options.ComputeReferences = (
        True  # Crucial for getting valid references for dimensions
    )
    options.IncludeNonVisibleObjects = False  # Generally, dimension visible geometry
    options.View = (
        view_for_options  # Contextualize geometry to how it appears in the view
    )

    geom_element = wall.get_Geometry(options)
    if not geom_element:
        return None

    # Find the most significant solid (useful for complex walls, though we focus on simple ones)
    found_solid = None
    for geom_obj in geom_element:
        if (
            isinstance(geom_obj, DB.Solid)
            and geom_obj.Faces.Size > 0
            and geom_obj.Volume > 0.0001
        ):
            if found_solid is None or geom_obj.Volume > found_solid.Volume:
                found_solid = geom_obj
    return found_solid


def find_wall_end_face_references(wall, wall_solid, wall_location_curve):
    """
    Attempts to find two distinct face references on the wall solid that represent its ends,
    perpendicular to the wall's location curve direction.
    Returns a list of DB.Reference.
    """
    end_face_refs = []
    if not wall_solid or not isinstance(wall_location_curve, DB.Line):
        return end_face_refs  # Only supports straight walls for this logic

    wall_start_pt = wall_location_curve.GetEndPoint(0)
    wall_end_pt = wall_location_curve.GetEndPoint(1)
    wall_direction = (wall_end_pt - wall_start_pt).Normalize()

    candidate_faces = []
    for face in wall_solid.Faces:
        if isinstance(face, DB.PlanarFace):
            face_normal = face.FaceNormal
            # Check if face normal is parallel (or anti-parallel) to the wall_direction
            # This implies the face is perpendicular to the wall's run (i.e., an end cap)
            if face_normal.IsAlmostEqualTo(
                wall_direction
            ) or face_normal.IsAlmostEqualTo(-wall_direction):
                # Heuristic: Area should be small relative to main faces (wall_height * wall_thickness)
                # For simplicity, we'll rely on the normal and later sorting by projection.
                # A more robust check would compare area to wall.Width * (approximate height).
                candidate_faces.append(face.Reference)

    if not candidate_faces:
        return end_face_refs

    # Sort candidate faces by their projected position along the wall's location curve
    # to find the "first" and "last" end face.
    refs_with_projection = []
    for ref in candidate_faces:
        try:
            geom_face = wall.GetGeometryObjectFromReference(ref)
            if isinstance(geom_face, DB.Face):
                # Get a point on the face (e.g., center of its UV bounding box)
                uv_center = (
                    geom_face.GetBoundingBox().Min + geom_face.GetBoundingBox().Max
                ) / 2.0
                point_on_face = geom_face.Evaluate(uv_center)

                projection_result = wall_location_curve.Project(point_on_face)
                # Use distance from start or parameter; parameter is good if curve is normalized
                distance_from_start = projection_result.XYZPoint.DistanceTo(
                    wall_start_pt
                )
                refs_with_projection.append(
                    {
                        "ref": ref,
                        "dist": distance_from_start,
                        "stable": ref.ConvertToStableRepresentation(
                            revit.doc
                        ),  # For ensuring uniqueness
                    }
                )
        except Exception as ex_proj:
            print(
                "Error processing reference for sorting (Wall ID {}): {}".format(
                    wall.Id, ex_proj
                )
            )
            continue

    # Ensure uniqueness and sort
    unique_refs_map = {item["stable"]: item for item in refs_with_projection}
    sorted_unique_refs = sorted(unique_refs_map.values(), key=lambda x: x["dist"])

    if len(sorted_unique_refs) >= 2:
        # Found at least two distinct end faces
        end_face_refs.append(sorted_unique_refs[0]["ref"])  # Closest to wall start
        end_face_refs.append(
            sorted_unique_refs[-1]["ref"]
        )  # Furthest from wall start (closest to end)

    return end_face_refs


# --- Main Script Logic ---
def dimension_walls_in_current_view():
    doc = revit.doc
    uidoc = revit.uidoc
    if not uidoc:  # Should not happen in a regular pyRevit script
        forms.alert("No active UI document found.", title="Error")
        return

    active_view = doc.ActiveView
    if not active_view:
        forms.alert("No active Revit view found.", title="Error")
        return

    # Check if the view type is suitable for placing dimensions
    allowed_view_types = [
        DB.ViewType.FloorPlan,
        DB.ViewType.CeilingPlan,
        DB.ViewType.Elevation,
        DB.ViewType.Section,
        DB.ViewType.Detail,
    ]
    if active_view.ViewType not in allowed_view_types:
        forms.alert(
            "Dimensions can typically be placed in Plan, Ceiling Plan, Elevation, Section, or Detail views.",
            title="View Not Suitable",
        )
        return

    # Get offset distance from user
    offset_internal_units = get_offset_distance_from_user(
        "Enter offset for dimension line (in millimeters):", DEFAULT_OFFSET_MM
    )
    if offset_internal_units is None:  # User cancelled or invalid input
        script.exit()

    # Collect walls visible in the current view
    walls_to_dimension = (
        DB.FilteredElementCollector(doc, active_view.Id)
        .OfCategory(DB.BuiltInCategory.OST_Walls)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    if not walls_to_dimension:
        forms.alert("No walls found in the current view.", title="No Walls Found")
        return

    created_dimensions_count = 0
    failed_walls_count = 0
    min_wall_length_internal = DB.UnitUtils.ConvertToInternalUnits(
        MIN_WALL_LENGTH_MM, DB.UnitTypeId.Millimeters
    )

    with DB.Transaction(doc, "Dimension Walls in Current View") as t:
        t.Start()
        for wall in walls_to_dimension:
            try:
                location_curve = wall.Location.Curve
                if not location_curve or not location_curve.IsBound:
                    failed_walls_count += 1
                    continue

                # This script primarily targets straight walls for overall length dimensions
                if not isinstance(location_curve, DB.Line):
                    print(
                        "Skipping non-linear wall (ID: {}). Only straight walls are currently supported for overall length.".format(
                            wall.Id
                        )
                    )
                    failed_walls_count += 1
                    continue

                if location_curve.Length < min_wall_length_internal:
                    print(
                        "Skipping very short wall (ID: {}). Length: {:.2f}mm".format(
                            wall.Id,
                            DB.UnitUtils.ConvertFromInternalUnits(
                                location_curve.Length, DB.UnitTypeId.Millimeters
                            ),
                        )
                    )
                    failed_walls_count += 1
                    continue

                p1 = location_curve.GetEndPoint(0)
                p2 = location_curve.GetEndPoint(1)
                wall_direction_3d = (p2 - p1).Normalize()  # 3D direction of the wall

                # Determine offset vector in the view plane, perpendicular to the wall's projection
                view_normal = active_view.ViewDirection

                # Project wall direction onto view plane (direction of dimension string in view)
                wall_dir_in_view = (
                    wall_direction_3d
                    - wall_direction_3d.DotProduct(view_normal) * view_normal
                )
                if wall_dir_in_view.IsAlmostEqualTo(
                    DB.XYZ.Zero
                ):  # Wall is perpendicular to view plane
                    print(
                        "Skipping wall (ID: {}) as it's perpendicular to the view plane.".format(
                            wall.Id
                        )
                    )
                    failed_walls_count += 1
                    continue
                wall_dir_in_view = wall_dir_in_view.Normalize()

                # Offset vector is perpendicular to both wall_dir_in_view and view_normal
                offset_vector_in_view = wall_dir_in_view.CrossProduct(
                    view_normal
                ).Normalize()
                if offset_vector_in_view.IsAlmostEqualTo(
                    DB.XYZ.Zero
                ):  # Should only happen if wall_dir_in_view was zero
                    # Fallback (e.g. if wall parallel to view direction in an odd way)
                    offset_vector_in_view = (
                        active_view.UpDirection
                        if abs(wall_dir_in_view.DotProduct(active_view.RightDirection))
                        < 0.5
                        else active_view.RightDirection
                    )
                    offset_vector_in_view = (
                        offset_vector_in_view
                        - offset_vector_in_view.DotProduct(view_normal) * view_normal
                    )  # re-project to view plane
                    offset_vector_in_view = offset_vector_in_view.Normalize()

                # Create the dimension line geometry (parallel to the wall's 3D location line)
                # The offset is applied in the calculated view plane direction
                dim_line_p1 = p1 + offset_vector_in_view * offset_internal_units
                dim_line_p2 = p2 + offset_vector_in_view * offset_internal_units
                dimension_placement_line = DB.Line.CreateBound(dim_line_p1, dim_line_p2)

                # Get references for dimensioning (overall wall length using end faces)
                references_array = DB.ReferenceArray()
                wall_solid = get_wall_solid(wall, active_view)

                if wall_solid:
                    end_face_refs = find_wall_end_face_references(
                        wall, wall_solid, location_curve
                    )
                    if len(end_face_refs) == 2:
                        references_array.Append(end_face_refs[0])
                        references_array.Append(end_face_refs[1])
                    else:
                        print(
                            "Wall ID {}: Found {} end face refs, expected 2. Skipping.".format(
                                wall.Id, len(end_face_refs)
                            )
                        )
                else:
                    print("Wall ID {}: No valid solid found. Skipping.".format(wall.Id))

                if references_array.Size == 2:
                    # Ensure references are not identical (can happen with complex geometry)
                    ref1_stable = references_array.get_Item(
                        0
                    ).ConvertToStableRepresentation(doc)
                    ref2_stable = references_array.get_Item(
                        1
                    ).ConvertToStableRepresentation(doc)

                    if ref1_stable != ref2_stable:
                        doc.Create.NewDimension(
                            active_view, dimension_placement_line, references_array
                        )
                        created_dimensions_count += 1
                    else:
                        print(
                            "Skipping dimension for wall {} due to identical end references.".format(
                                wall.Id
                            )
                        )
                        failed_walls_count += 1
                elif wall_solid:  # Only count as fail if we processed a solid
                    failed_walls_count += 1

            except Exception as ex:
                failed_walls_count += 1
                print("Error dimensioning wall (ID: {}): {}".format(wall.Id, ex))

        if created_dimensions_count > 0:
            t.Commit()
            forms.alert(
                "Successfully created {} overall dimension(s).\n"
                "{} wall(s) could not be dimensioned or were skipped.".format(
                    created_dimensions_count, failed_walls_count
                ),
                title="Dimensioning Complete",
            )
        else:
            t.RollBack()
            forms.alert(
                "No dimensions were created.\n"
                "{} wall(s) were processed but failed or were skipped.".format(
                    failed_walls_count
                ),
                title="Dimensioning Failed",
            )


# --- Script Execution ---
if __name__ == "__main__":
    # Ensure the script is run within Revit and a document is active
    if revit.doc:
        dimension_walls_in_current_view()
    else:
        forms.alert(
            "No active Revit document found. Please open a project.", title="Error"
        )
