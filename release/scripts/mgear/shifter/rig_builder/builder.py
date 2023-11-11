from mgear.shifter import io
import maya.cmds as cmds
import os
import json


def execute_build_logic(json_data):
    """Execute the rig building logic based on the provided JSON data.

    Args:
        json_data (str): A JSON string containing the necessary data.
    """
    data = json.loads(json_data)
    output_folder = data["output_folder"]

    for row in data["rows"]:
        file_path = row["file_path"]
        output_name = row["output_name"]

        # Continue with the logic only if file_path is provided
        if file_path:
            io.build_from_file(file_path)

            if not output_folder:
                output_folder = os.path.dirname(file_path)

            maya_file_name = "{}.ma".format(output_name)
            maya_file_path = os.path.join(output_folder, maya_file_name)

            cmds.file(rename=maya_file_path)
            cmds.file(save=True, type="mayaAscii")
            cmds.file(new=True, force=True)
