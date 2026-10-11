"""Import Mirror Config custom step template.

Template for applying the mirror pose flags of a Mirror Config .smc file.
"""

TEMPLATE = r'''import mgear.shifter.custom_step as cstp
from mgear.core import mirror_config


class CustomShifterStep(cstp.customShifterMainStep):
    """Import Mirror Config.

    This custom step sets the mirror pose inversion flags (invTx ... invSz)
    of the rig controls from a .smc file exported by the Mirror Config tool
    (mGear > Shifter > Mirror Config). Only the stored flags are applied,
    no analysis is done during the build.
    """

    def setup(self):
        """Set up the custom step name and import options."""
        self.name = "{stepName}"

        # Configure the mirror config file path
        # Option 1: Hardcode the path
        # self.config_path = "path/to/your/mirror_config.smc"

        # Option 2: Use a path relative to this script
        # import os
        # script_dir = os.path.dirname(__file__)
        # self.config_path = os.path.join(script_dir, "mirror_config.smc")

        # Option 3: Leave as None to show file dialog at runtime
        self.config_path = None

        # Namespace of the rig controls. None for no namespace
        self.namespace = None

        # Add the inv attributes to the controls that don't have them
        self.create_missing = True

    def run(self):
        """Apply the mirror config.

        If config_path is None, a file dialog will be shown
        to select the configuration file.
        """
        self.log("Importing mirror config...")

        file_path = self.config_path

        # Show file dialog if no path is configured
        if not file_path:
            from maya import cmds

            file_path = cmds.fileDialog2(
                caption="Import Mirror Config",
                fileMode=1,
                fileFilter=mirror_config.FILE_FILTER,
            )
            if not file_path:
                self.log("Import cancelled.", level="warning")
                return
            file_path = file_path[0]

        # Apply the mirror config
        try:
            result = mirror_config.import_config(
                file_path,
                namespace=self.namespace,
                create_missing=self.create_missing,
            )
            self.log(
                "Mirror config from {{}}: {{}}".format(
                    file_path, mirror_config.format_apply_result(result)
                )
            )
        except Exception as e:
            self.log(
                "Failed to import mirror config: {{}}".format(e),
                level="error",
            )
            raise'''
