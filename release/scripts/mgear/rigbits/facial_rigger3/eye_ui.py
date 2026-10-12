"""Eye Rigger 3.0 tab of the Facial Rigger window."""

import os

from mgear.vendor.Qt import QtWidgets

from mgear.core import config_io
from mgear.core import settings_form
from mgear.core.facial import eyelid_schema

from maya import cmds

from . import eye

GROUPS = (
    (
        "Geometry",
        [
            "eyeMesh",
            "loopType",
            "edgeLoop",
            "vertexLoop",
            "customCorner",
            "intCorner",
            "extCorner",
            "sideRange",
        ],
    ),
    ("Naming", ["namePrefix", "ctlName"]),
    (
        "Rig",
        [
            "headJnt",
            "aim_controller",
            "parent_node",
            "deformers_group",
            "ctlSet",
            "defSet",
        ],
    ),
    ("Controls", ["offset", "ctl_size", "simplified", "mirrorBehavior"]),
    (
        "Tracking",
        ["upperVTrack", "upperHTrack", "lowerVTrack", "lowerHTrack"],
    ),
    (
        "Joints",
        ["everyNVertex", "fixedJoints", "fixedJointsNumber"],
    ),
    ("Skin", ["doSkin", "rigidLoops", "falloffLoops"]),
)

FILE_FILTER = "Eye Rigger Configuration (*{})".format(eyelid_schema.FILE_EXT)


class EyeRiggerTab(QtWidgets.QWidget):
    """Settings form and actions of Eye Rigger 3.0.

    Args:
        parent (QtWidgets.QWidget, optional): Parent widget.
    """

    def __init__(self, parent=None):
        super(EyeRiggerTab, self).__init__(parent)
        self.last_path = ""
        self.form = settings_form.SettingsForm(eyelid_schema.SCHEMA, GROUPS)
        self.build_button = QtWidgets.QPushButton("Build Eye Rig")
        self.import_button = QtWidgets.QPushButton("Import Config")
        self.export_button = QtWidgets.QPushButton("Export Config")
        self.create_layout()
        self.create_connections()
        self.update_rows()

    def create_layout(self):
        """Lay out the form in a scroll area above the buttons."""
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.import_button)
        buttons.addWidget(self.export_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addLayout(buttons)
        layout.addWidget(self.build_button)

    def create_connections(self):
        """Connect the buttons and the rows depending on other settings."""
        self.form.valueChanged.connect(self.update_rows)
        self.build_button.clicked.connect(self.build)
        self.import_button.clicked.connect(self.import_settings)
        self.export_button.clicked.connect(self.export_settings)

    def update_rows(self, *args):
        """Show the rows that apply to the current settings."""
        vertex = eyelid_schema.LOOP_TYPES[self.form.value("loopType")] == "vertex"
        self.form.set_row_visible("edgeLoop", not vertex)
        self.form.set_row_visible("vertexLoop", vertex)
        custom = self.form.value("customCorner")
        self.form.set_row_visible("intCorner", custom)
        self.form.set_row_visible("extCorner", custom)
        fixed = self.form.value("fixedJoints")
        self.form.set_row_visible("everyNVertex", not fixed)
        self.form.set_row_visible("fixedJointsNumber", fixed)
        skin = self.form.value("doSkin")
        self.form.set_row_visible("rigidLoops", skin)
        self.form.set_row_visible("falloffLoops", skin)

    def build(self):
        """Build the eye rig from the form settings."""
        return eye.rig(**self.form.get_settings())

    def _start_dir(self):
        if self.last_path:
            return os.path.dirname(self.last_path)
        return cmds.workspace(query=True, rootDirectory=True)

    def import_settings(self, path=None):
        """Load a ``.eyes`` file into the form.

        Args:
            path (str, optional): File path. Asks for one when None.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Import Eye Rigger Configuration", self._start_dir(), FILE_FILTER
            )
        if not path:
            return
        try:
            settings = eye.load_settings(path)
        except ValueError as error:
            cmds.warning(str(error))
            return
        self.last_path = path
        self.form.set_settings(settings)
        self.update_rows()

    def export_settings(self, path=None):
        """Save the form settings to a ``.eyes`` file.

        Args:
            path (str, optional): File path. Asks for one when None.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export Eye Rigger Configuration", self._start_dir(), FILE_FILTER
            )
        if not path:
            return
        path = config_io.file_path(path, eyelid_schema.FILE_EXT)
        eye.save_settings(path, self.form.get_settings())
        self.last_path = path
