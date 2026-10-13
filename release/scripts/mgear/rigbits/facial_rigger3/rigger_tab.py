"""Base tab of the Facial Rigger window: a settings form and its actions."""

import os

from mgear.vendor.Qt import QtWidgets

from mgear.core import config_io
from mgear.core import settings_form

from maya import cmds


class RiggerTab(QtWidgets.QWidget):
    """Settings form of one rigger, with Build, Import and Export.

    Args:
        schema (module): Settings schema module, with SCHEMA, FORM_GROUPS,
            ROW_KEYS, row_visibility, FILE_FILTER and FILE_EXT.
        rigger (module): Rig module, with rig, load_settings and
            save_settings.
        title (str): Rig name for the buttons and dialogs, e.g. "Eye".
        parent (QtWidgets.QWidget, optional): Parent widget.
    """

    def __init__(self, schema, rigger, title, parent=None):
        super(RiggerTab, self).__init__(parent)
        self.schema = schema
        self.rigger = rigger
        self.title = title
        self.last_path = ""
        self.form = settings_form.SettingsForm(schema.SCHEMA, schema.FORM_GROUPS)
        self.build_button = QtWidgets.QPushButton("Build {} Rig".format(title))
        self.import_button = QtWidgets.QPushButton("Import Config")
        self.export_button = QtWidgets.QPushButton("Export Config")
        self.extra_buttons = self.create_extra_buttons()
        self.create_layout()
        self.create_connections()
        self.form.set_visibility_rule(schema.row_visibility, schema.ROW_KEYS)

    def create_extra_buttons(self):
        """Create the rigger's own buttons, shown before Import and Export.

        Returns:
            list: QPushButton widgets.
        """
        return []

    def create_layout(self):
        """Lay out the form in a scroll area above the buttons."""
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        buttons = QtWidgets.QHBoxLayout()
        for button in self.extra_buttons + [self.import_button, self.export_button]:
            buttons.addWidget(button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addLayout(buttons)
        layout.addWidget(self.build_button)

    def create_connections(self):
        """Connect the buttons."""
        self.build_button.clicked.connect(self.build)
        self.import_button.clicked.connect(self.import_settings)
        self.export_button.clicked.connect(self.export_settings)

    def build(self):
        """Build the rig from the form settings."""
        return self.rigger.rig(**self.form.get_settings())

    def _start_dir(self):
        if self.last_path:
            return os.path.dirname(self.last_path)
        return cmds.workspace(query=True, rootDirectory=True)

    def import_settings(self, path=None):
        """Load a configuration file into the form.

        Args:
            path (str, optional): File path. Asks for one when None.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Import {} Rigger Configuration".format(self.title),
                self._start_dir(),
                self.schema.FILE_FILTER,
            )
        if not path:
            return
        try:
            settings = self.rigger.load_settings(path)
        except ValueError as error:
            cmds.warning(str(error))
            return
        self.last_path = path
        self.form.set_settings(settings)

    def export_settings(self, path=None):
        """Save the form settings to a configuration file.

        Args:
            path (str, optional): File path. Asks for one when None.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export {} Rigger Configuration".format(self.title),
                self._start_dir(),
                self.schema.FILE_FILTER,
            )
        if not path:
            return
        path = config_io.file_path(path, self.schema.FILE_EXT)
        self.rigger.save_settings(path, self.form.get_settings())
        self.last_path = path
