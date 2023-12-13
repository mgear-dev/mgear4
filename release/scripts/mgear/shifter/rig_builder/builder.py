import json
import os

import maya.cmds as cmds
import pyblish.api
import pyblish.util

import pyblish_lite.app

from mgear.vendor.Qt import QtCore
from mgear.shifter import io


def setup_pyblish():
    pyblish.api.register_host("maya")
    pyblish.api.register_gui("pyblish_lite")
    print(pyblish.api.registered_guis())
    plugin_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "plugins")
    pyblish.api.register_plugin_path(plugin_dir)


def run_validators(output_name):
    print("Validating rig '{}'...\n".format(output_name))
    context = pyblish.util.collect()
    pyblish.util.validate(context)
    context, report = generate_instance_report(context, output_name)
    passed_validation = context.data.get("valid")
    return context, passed_validation, report


def format_report_header():
    header_string = "{:<10}{:<40}{:<80}".format("Success", "Plug-in", "Instance")
    header = "{}\n{}\n".format(header_string, "-" * 70)
    return header


def generate_instance_report(context, output_name):
    result_string = "{success:<10}{plugin.__name__:<40}{instance} - {name}"
    error_string = "{:<10} > error: {:<80}"
    context.data["valid"] = True

    results = []
    for result in context.data.get("results"):
        result["name"] = output_name
        results.append(result_string.format(**result))
        r_error = result.get("error")
        if r_error is not None:
            context.data["valid"] = False
            results.append(error_string.format("", str(r_error)))
    results = "\n".join(results)

    return context, results


def execute_build_logic(json_data, validate=True):
    """Execute the rig building logic based on the provided JSON data.

    Args:
        json_data (str): A JSON string containing the necessary data.
    """
    data = json.loads(json_data)
    report_string = format_report_header()

    data_rows = data.get("rows")
    if not data_rows:
        return
    for row in data_rows:
        # Continue with the logic only if file_path is provided
        file_path = row.get("file_path")
        if not file_path:
            return

        output_folder = data.get("output_folder")
        if not output_folder:
            output_folder = os.path.dirname(file_path)

        output_name = row.get("output_name")
        maya_file_name = "{}.ma".format(output_name)
        maya_file_path = os.path.join(output_folder, maya_file_name)

        print("Building rig '{}'...".format(output_name))
        io.build_from_file(file_path)

        save_build = True
        if validate:
            # window.on_about_to_process(QtCore.Qt.DirectConnection)
            # window.publish()
            # window.on_was_published()
            context, passed_validation, report = run_validators(output_name)
            window = pyblish_lite.show()
            ctrl = window.controller
            ctrl.context = context
            window.on_was_published()
            # window.on_was_processed(report)
            # window.data.models["plugins"].update_with_result(report)
            # window.data.models["instances"].update_with_result(report)
            # window.data.models["terminal"].update_with_result(report)
            report_string += "{}\n".format(report)
            if not passed_validation:
                save_build = False
                print("Found errors, please fix and rebuild the rig.")
            report_string += "{}\n".format(" -" * 35)

        cmds.file(rename=maya_file_path)
        cmds.file(save=save_build, type="mayaAscii")
        # cmds.file(new=True, force=True)

    print(report_string)
