import subprocess
import tempfile
import os

from dotenv import load_dotenv

load_dotenv()
ipy_path = os.getenv("IPY_PATH")


import subprocess
import tempfile
import os

# If you intend to use the default for 'ipy_executable', ensure 'ipy_path' is
# defined in the global scope before this function is defined.
# Example:
# ipy_path = r"C:\path\to\your\IronPython.2.7.12\net45\ipy.exe"


def clean_code(code_string):
    """
    Args:
        code_string (str): The string potentially containing AI-generated text
                           and a Markdown code block.

    Returns:
        str: The extracted code content, stripped of leading/trailing whitespace.
             If no block is extracted, returns the original string stripped
             of leading/trailing whitespace.
    """
    s = code_string

    python_marker = "```python"
    py_marker_idx = s.find(python_marker)
    block_marker = "```"

    if py_marker_idx != -1:
        code_start_offset = len(python_marker)
        if (py_marker_idx + code_start_offset < len(s)) and (
            s[py_marker_idx + code_start_offset] == "\n"
        ):
            code_start_offset += 1
        actual_code_start_index = py_marker_idx + code_start_offset
        closing_marker_idx = s.find(block_marker, actual_code_start_index)

        if closing_marker_idx != -1:
            return s[actual_code_start_index:closing_marker_idx].strip()
        else:
            return s[actual_code_start_index:].strip()

    generic_marker_idx = s.find(block_marker)
    if generic_marker_idx != -1:
        code_start_offset = len(block_marker)
        if (generic_marker_idx + code_start_offset < len(s)) and (
            s[generic_marker_idx + code_start_offset] == "\n"
        ):
            code_start_offset += 1
        actual_code_start_index = generic_marker_idx + code_start_offset
        closing_marker_idx = s.find(block_marker, actual_code_start_index)

        if closing_marker_idx != -1:
            return s[actual_code_start_index:closing_marker_idx].strip()
        else:
            return s[actual_code_start_index:].strip()
    return s.strip()


def check_syntax(code_str):
    try:
        compile(code_str, "<string>", "exec")
        return True
    except SyntaxError as e:
        return str(e)


if __name__ == "__main__":
    valid_code = """
import sys
def greet(name):
    print "Hello, " + name + "!" # Python 2 syntax for IronPython 2.7
greet("IronPython User")
a = 1 + 2
"""

    invalid_code_syntax = """
def my_function(
    print "This has a syntax error"
"""

    invalid_code_indent = """
def another_function():
print "This has an indentation error" # Python 2 syntax, but indent error
"""
    print(try_ironpy_compile(invalid_code_syntax))
    # print(check_syntax(invalid_code_syntax))
