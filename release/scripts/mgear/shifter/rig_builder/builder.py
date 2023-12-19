import json
import os

import maya.cmds as cmds
import pyblish.api
import pyblish.util

from mgear.shifter import io


def setup_pyblish():
    pyblish.api.register_host("maya")
    pyblish.api.register_gui("pyblish_lite")
    plugin_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "plugins")
    pyblish.api.register_plugin_path(plugin_dir)


class RigBuilder(object):
    def __init__(self):
        self.results_dict = {}

    def run_validators(self):
        context = pyblish.util.collect()
        pyblish.util.validate(context)
        return context

    def build_results_dict(self, output_name, context):
        self.results_dict[output_name] = {}
        results = context.data.get("results")

        for result in results:
            check_name = result.get("plugin").__name__
            instance = result.get("instance")
            success = result.get("success")
            error = result.get("error")
            self.results_dict[output_name][check_name] = {
                "instance": instance,
                "success": success,
                "error": error,
            }

    def get_results_dict(self):
        return self.results_dict

    def format_report_header(self):
        header_string = "{:<10}{:<40}{:<80}".format("Success", "Plug-in", "Instance")
        header = "{}\n{}\n".format(header_string, "-" * 70)
        return header

    def generate_instance_report(self, output_name):
        result_string = "{success:<10}{check_name:<40}{instance} - {output_name}"
        error_string = "{:<10} > error: {:<80}"
        valid = True

        results = []
        checks_dict = self.results_dict.get(output_name)
        for check_name, check_data in checks_dict.items():
            results.append(
                result_string.format(
                    **check_data, check_name=check_name, output_name=output_name
                )
            )
            r_error = check_data.get("error")
            if r_error is not None:
                valid = False
                results.append(error_string.format("", str(r_error)))

        report_string = "\n".join(results)
        return valid, report_string

    def execute_build_logic(self, json_data, validate=True, passed_only=False):
        """Execute the rig building logic based on the provided JSON data.

        Args:
            json_data (str): A JSON string containing the necessary data
            validate (bool): Option to run Pyblish validators
            passed_only (bool): Option to publish only rigs that pass validation
        """
        data = json.loads(json_data)
        report_string = self.format_report_header()

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
            context = None
            if validate:
                print("Validating rig '{}'...\n".format(output_name))
                context = self.run_validators()
                self.build_results_dict(output_name, context)
                valid, report = self.generate_instance_report(output_name)

                report_string += "{}\n".format(report)
                if passed_only and not valid:
                    save_build = False
                    print("Found errors, please fix and rebuild the rig.")

                report_string += "{}\n".format(" -" * 35)

            cmds.file(rename=maya_file_path)
            cmds.file(save=save_build, type="mayaAscii")
            cmds.file(new=True, force=True)

        print(report_string)
        return self.results_dict
