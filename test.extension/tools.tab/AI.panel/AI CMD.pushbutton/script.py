# -*- coding: utf-8 -*-
import requests
from pyrevit import forms
import traceback

# Ask for a string input
query = forms.ask_for_string(
    prompt="",
    title="Enter Command",
    default="",
)


def get_code(query):
    response = requests.get(
        "http://localhost:5000/generate_code?input=" + query.replace(" ", "%20")
    )
    print(response)
    # When there is an error
    if response.status_code != 200:
        forms.alert(
            str(response.status_code)
            + ": There was a problem connecting to the coding sweatshop"
        )
        return

    # Otherwise return the code
    data = response.json()
    code = data["code"]
    return code


if query:
    ai_code = get_code(query)
    if ai_code: 
        exec(ai_code)

else:
    forms.alert("No text was entered.")
