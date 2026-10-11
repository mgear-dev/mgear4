"""Import Gimmick Joints Configuration custom step template.

Template for rebuilding blend and support gimmick joints from a Gimmick
Joints .gst file.
"""

TEMPLATE = r'''import mgear.shifter.custom_step as cstp
from mgear.rigbits.gimmick_tool import core


class CustomShifterStep(cstp.customShifterMainStep):
    """Import Gimmick Joints configuration.

    This custom step rebuilds the blend and support joints of a .gst file
    exported by the Gimmick Joints tool (mGear > Rigbits > Gimmick Joints):
    blend joints on their source joints with their blend value, and support
    joints with their local transforms. Run it as a post custom step, once
    the rig joints exist.
    """

    def setup(self):
        """Set up the custom step name and import options."""
        self.name = "{stepName}"

        # Configure the gimmick joints file path
        # Option 1: Hardcode the path
        # self.gimmick_path = "path/to/your/gimmick_joints.gst"

        # Option 2: Use a path relative to this script
        # import os
        # script_dir = os.path.dirname(__file__)
        # self.gimmick_path = os.path.join(script_dir, "gimmick_joints.gst")

        # Option 3: Leave as None to show file dialog at runtime
        self.gimmick_path = None

        # Delete gimmick joints with the same names before rebuilding them
        self.replace = True

    def run(self):
        """Import the gimmick joints configuration.

        If gimmick_path is None, a file dialog will be shown
        to select the configuration file.
        """
        self.log("Importing gimmick joints configuration...")

        file_path = self.gimmick_path

        # Show file dialog if no path is configured
        if not file_path:
            from maya import cmds

            file_path = cmds.fileDialog2(
                caption="Import Gimmick Joints Configuration",
                fileMode=1,
                fileFilter=core.FILE_FILTER,
            )
            if not file_path:
                self.log("Import cancelled.", level="warning")
                return
            file_path = file_path[0]

        # Import the gimmick joints
        try:
            created = core.import_file(file_path, replace=self.replace)
            self.log(
                "Imported {{}} gimmick joint(s) from: {{}}".format(
                    len(created), file_path
                )
            )
        except Exception as e:
            self.log(
                "Failed to import gimmick joints configuration: {{}}".format(e),
                level="error",
            )
            raise'''
