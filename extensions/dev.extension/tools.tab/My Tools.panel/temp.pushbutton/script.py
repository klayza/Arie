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
    find_and_display_elements()