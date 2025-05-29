# -*- coding: utf-8 -*-
from pyrevit import forms

# Ask for a string input
query = forms.ask_for_string(
    prompt="",
    title="Enter Command",
    default="",
)


def generate_code(query):
    # return "from pyrevit import forms\n\nforms.alert('you entered mama!')\nprint('this is a test!')\nprint('another test here!')"
    # return 'from pyrevit import revit, DB, script\nfrom pyrevit import forms\nimport clr\nclr.AddReference(\'RevitAPI\')\nclr.AddReference(\'RevitAPIUI\')\n\nlogger = script.get_logger()\ndoc = revit.doc\n\ntry:\n    warnings = doc.GetWarnings()\n    if not warnings:\n        forms.alert("No warnings found in the current document.", title="Warnings")\n    else:\n        warnings_list = []\n        for i, warning in enumerate(warnings, start=1):\n            warnings_list.append(str(i) + ". " + warning.GetDescriptionText())\n        warnings_text = "\\n\\n".join(warnings_list)\n        # Show warnings in modeless window to avoid long message box\n        forms.alert(warnings_text, title="Revit Warnings")\nexcept Exception as e:\n    logger.error(str(e))\n    forms.alert("Failed to retrieve warnings:\\n" + str(e), title="Error")'

    return 'from pyrevit import revit, DB, forms\nfrom pyrevit import script\nimport clr\nclr.AddReference(\'RevitAPI\')\nclr.AddReference(\'RevitAPIUI\')\n\ndoc = revit.doc\nlogger = script.get_logger()\n\ndims = DB.FilteredElementCollector(doc, doc.ActiveView.Id).OfClass(DB.Dimension).ToElements()\nlengths = []\n\ntry:\n    for dim in dims:\n        try:\n            value = None\n            # Try to get the dimension value(s)\n            if dim.Value is not None:\n                value = dim.Value\n            else:\n                # Try parameter BuiltInParameter.DIM_LENGTH\n                param = dim.get_Parameter(DB.BuiltInParameter.DIM_LENGTH)\n                if param and param.HasValue:\n                    value = param.AsDouble()\n\n            # If still no value, try geometry length\n            if value is None:\n                curve = dim.Curve\n                if curve is not None:\n                    value = curve.Length\n\n            if value is not None:\n                lengths.append(value)\n        except:\n            continue\n\n    if not lengths:\n        forms.alert("No dimension lengths found on active view.", exitscript=True)\n\n    min_length = min(lengths)\n    # Convert lengths (internal units feet) to millimeters (1 foot = 304.8 mm)\n    lengths_mm = [l * 304.8 for l in lengths]\n    min_length_mm = min_length * 304.8\n\n    output = script.get_output()\n    output.print_table(\n        [["Dimension #", "Length (mm)"]] +\n        [[str(i+1), "{0:.2f}".format(lengths_mm[i])] for i in range(len(lengths_mm))]\n    )\n    output.print_md("**Shortest dimension length on active view: {0:.2f} mm**".format(min_length_mm))\n\nexcept Exception as e:\n    forms.alert("Error occurred: {0}".format(str(e)), exitscript=True)\n'


def check_ai_code(code):
    if code:
        return ["safe", "valid"]


if query:
    ai_code = generate_code(query)
    ai_code_check = check_ai_code(ai_code)

    if "safe" in ai_code_check and "valid" in ai_code_check:
        exec(ai_code)

    else:
        forms.alert("Couldn't run the code: " + str(ai_code_check))

else:
    forms.alert("No text was entered.")
