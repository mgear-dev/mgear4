"""Import Facial Rigger 3.0 Configuration custom step template.

Template for building facial rigs (eyes, lips and brows) from Facial Rigger
3.0 configuration files. Eye Rigger 2.1 ``.eyes``, and Lips and Brow Rigger
1.0 ``.lips`` and ``.brows`` files load too.
"""

TEMPLATE = r'''import mgear.shifter.custom_step as cstp
from mgear.rigbits.facial_rigger3 import files


class CustomShifterStep(cstp.customShifterMainStep):
    """Build facial rigs from Facial Rigger 3.0 configuration files.

    Each file builds one rig, for example a left and a right eye. Run it as
    a post custom step, once the joints the rigs use exist.
    """

    def setup(self):
        """Set up the custom step name and the configuration files."""
        self.name = "{stepName}"

        # Configure the configuration file paths, one rig per file
        # Option 1: Hardcode the paths
        # self.config_paths = [
        #     "path/to/eye_L.eyes",
        #     "path/to/eye_R.eyes",
        #     "path/to/lips.lips",
        #     "path/to/brow_L.brows",
        # ]

        # Option 2: Use paths relative to this script
        # import os
        # script_dir = os.path.dirname(__file__)
        # self.config_paths = [os.path.join(script_dir, "eye_L.eyes")]

        # Option 3: Leave empty to pick the files at runtime
        self.config_paths = []

    def run(self):
        """Build a rig from each configuration file.

        If config_paths is empty, a file dialog will be shown to select
        the configuration files.
        """
        paths = list(self.config_paths)
        if not paths:
            from maya import cmds

            paths = cmds.fileDialog2(
                caption="Select Facial Rigger Configurations",
                fileMode=4,
                fileFilter=files.FILE_FILTER,
            ) or []
            if not paths:
                self.log("Import cancelled.", level="warning")
                return

        for path in paths:
            try:
                root = files.rig_from_file(path)
            except Exception as e:
                self.log(
                    "Failed to build the facial rig of {{}}: {{}}".format(path, e),
                    level="error",
                )
                raise
            if root is None:
                raise RuntimeError(
                    "The facial rig of {{}} was not built".format(path)
                )
            self.log("Facial rig {{}} built from: {{}}".format(root, path))'''
