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


def try_ironpy_compile(
    code_string,
    ipy_executable=None,
):
    """
    Attempts to syntax-check a Python code string using a specified IronPython interpreter.
    The caller is responsible for ensuring 'ipy_executable' (or global 'ipy_path')
    points to the desired IronPython version (e.g., 2.7.12).

    Args:
        code_string (str): The Python code string to be syntax-checked.
        ipy_executable (str, optional): The path to the IronPython executable.
                                        If None, uses a globally defined 'ipy_path'.

    Returns:
        bool: True if the code is syntactically valid.
        str: An error message string if syntax issues are found or if the process
             itself encounters an error.
    """
    effective_ipy_executable = ipy_executable
    if effective_ipy_executable is None:
        try:
            # This relies on 'ipy_path' being a globally defined variable
            effective_ipy_executable = ipy_path
        except NameError:
            return "Error: 'ipy_executable' not provided and global 'ipy_path' is not defined."

    with tempfile.TemporaryDirectory() as temp_dir_path:
        temp_script_path = os.path.join(temp_dir_path, "temp_script_to_compile.py")

        try:
            with open(temp_script_path, "w", encoding="utf-8") as f:
                f.write(code_string)
        except IOError as e:
            return "Error: Failed to write temporary code file: {}".format(e)

        path_for_ipython_code = temp_script_path.replace("\\", "/")
        ironpython_code_to_execute = (
            f"source_code = open('{path_for_ipython_code}', 'r').read()\n"
            f"compile(source_code, '{path_for_ipython_code}', 'exec')\n"
        )
        command = [effective_ipy_executable, "-c", ironpython_code_to_execute]

        try:
            process_result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return "Error: The IronPython executable '{}' was not found. Ensure it is in PATH or provide the full path.".format(
                effective_ipy_executable
            )
        except OSError as e:
            return "Error: OS error while trying to run IronPython executable '{}': {}".format(
                effective_ipy_executable, e
            )
        except Exception as e:
            return "Error: An unexpected issue occurred while trying to run IronPython: {}".format(
                e
            )

        stderr_content = process_result.stderr.strip() if process_result.stderr else ""

        error_keywords = [
            "SyntaxError",
            "IndentationError",
            "Traceback (most recent call last):",
            "Sorry:",
        ]
        has_error_message_in_stderr = False
        if stderr_content:
            for keyword in error_keywords:
                if keyword in stderr_content:
                    has_error_message_in_stderr = True
                    break

        if has_error_message_in_stderr:
            return stderr_content
        elif process_result.returncode != 0:
            if stderr_content:
                return stderr_content
            else:
                return "Error: IronPython ('{}') failed with return code {} and no specific error message on stderr.".format(
                    effective_ipy_executable, process_result.returncode
                )
        else:  # process_result.returncode == 0 AND no error keywords found in stderr
            return True


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
