import json
import os

import maya.cmds as cmds
import pyblish.api
import pyblish.util

from mgear.shifter import io


def setup_pyblish():
    pyblish.api.register_host("maya")
    plugin_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "plugins")
    pyblish.api.register_plugin_path(plugin_dir)


def run_validators():
    context = pyblish.util.publish()
    valid = generate_report(context)
    return valid


def generate_report(context):
    header_string = "{:<10}{:<40}{:<80}".format("Success", "Plug-in", "Instance")
    result_string = "{success:<10}{plugin.__name__:<40}{instance}"
    error_string = "{:<10} > error: {:<80}"
    valid = True

    results = []
    for result in context.data.get("results"):
        results.append(result_string.format(**result))
        r_error = result.get("error")
        if r_error is not None:
            valid = False
            results.append(error_string.format("", str(r_error)))
    results = "\n".join(results)
    report = "{header}\n{line}\n{results}"
    print(report.format(header=header_string, results=results, line="-" * 70))
    return valid


def execute_build_logic(json_data):
    """Execute the rig building logic based on the provided JSON data.

    Args:
        json_data (str): A JSON string containing the necessary data.
    """
    data = json.loads(json_data)
    data_rows = data.get("rows")
    if not data_rows:
        return

    for row in data_rows:
        file_path = row.get("file_path")
        print(f"running {file_path}")

        # Continue with the logic only if file_path is provided
        if not file_path:
            return

        io.build_from_file(file_path)

        output_folder = data.get("output_folder")
        if not output_folder:
            output_folder = os.path.dirname(file_path)

        output_name = row.get("output_name")
        maya_file_name = "{}.ma".format(output_name)
        maya_file_path = os.path.join(output_folder, maya_file_name)

        save_build = True
        valid = run_validators()
        if not valid:
            save_build = False
            print("Found errors, please fix and rebuild the rig.")

        cmds.file(rename=maya_file_path)
        cmds.file(save=save_build, type="mayaAscii")
        cmds.file(new=True, force=True)
