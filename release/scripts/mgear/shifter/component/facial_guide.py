"""Shared guide parts of the facial components (eyelid, lips).

A facial component stores the shared settings of its rig schema
(:mod:`mgear.core.facial`) as guide params, edits them with a settings form
generated from the schema, and imports and exports the configuration files
of the matching Facial Rigger tool.
"""

import os
from functools import partial

from maya import cmds

import mgear
from mgear.core import config_io
from mgear.core import meshNavigation
from mgear.core import pyqt
from mgear.core import settings_form
from mgear.core import settings_schema

from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQDockWidget

from . import guide


def shared_params(schema, decided=()):
    """Get the shared settings of a schema stored on a guide.

    Args:
        schema (list): Schema params.
        decided (tuple, optional): Keys the guide locators or the connector
            decide, left out.

    Returns:
        list: Shared schema params.
    """
    return [
        param
        for param in schema
        if param.scope == "shared" and param.key not in decided
    ]


def rig_settings(schema, values, overrides=None):
    """Get complete rig settings from guide values.

    Args:
        schema (list): Schema params.
        values (dict): Guide settings.
        overrides (dict, optional): Settings the component decides.

    Returns:
        dict: Coerced settings.
    """
    settings = settings_schema.defaults(schema)
    for key in settings:
        if key in values:
            settings[key] = values[key]
    settings.update(overrides or {})
    return settings_schema.coerce(settings, schema)


def add_params(component_guide, params, defaults=None):
    """Add schema params to a component guide.

    Args:
        component_guide (ComponentGuide): The guide.
        params (list): Schema params.
        defaults (dict, optional): Guide defaults replacing the schema ones.
    """
    defaults = defaults or {}
    for param in params:
        default = defaults.get(param.key, param.default)
        if param.value_type == "enum":
            component_guide.addEnumParam(param.key, list(param.choices), default)
        else:
            component_guide.addParam(
                param.key, param.value_type, default, param.minimum, param.maximum
            )


def mirror_index_params(component_guide, keys):
    """Mirror the mesh component params of a guide on its mesh.

    Params whose mesh is missing, or with indices without a mirror, are kept
    and a warning is logged.

    Args:
        component_guide (ComponentGuide): The guide, already mirrored.
        keys (tuple): Params holding component strings.
    """
    for key in keys:
        value = component_guide.values[key]
        if not value:
            continue
        mesh = meshNavigation.parse_component_string(value)[0]
        if not cmds.objExists(mesh):
            mgear.log(
                "{}: can't mirror {}, the mesh {} doesn't exist".format(
                    component_guide.fullName, key, mesh
                ),
                mgear.sev_warning,
            )
            continue
        mirrored, missing = meshNavigation.mirror_component_string(value)
        if missing:
            mgear.log(
                "{}: {} has no mirror for indices {}, kept as it is".format(
                    component_guide.fullName, key, missing
                ),
                mgear.sev_warning,
            )
            continue
        component_guide.setParamDefValue(key, mirrored)


class FacialSettingsTab(QtWidgets.QWidget):
    """Settings form of a facial component, generated from its schema.

    Args:
        schema (module): Rig schema module, with FORM_GROUPS, ROW_KEYS and
            row_visibility.
        params (list): Params stored on the guide.
        buttons (list, optional): Buttons shown above the form.
        extra_groups (tuple, optional): (title, keys) form groups of the
            component's own params, after the schema groups.
        parent (QtWidgets.QWidget, optional): Parent widget.
    """

    def __init__(self, schema, params, buttons=None, extra_groups=(), parent=None):
        super(FacialSettingsTab, self).__init__(parent)
        keys = set(param.key for param in params)
        groups = []
        for title, group_keys in tuple(schema.FORM_GROUPS) + tuple(extra_groups):
            group_keys = [key for key in group_keys if key in keys]
            if group_keys:
                groups.append((title, group_keys))
        self.form = settings_form.SettingsForm(params, groups)
        self.form.set_visibility_rule(schema.row_visibility, schema.ROW_KEYS)
        self.import_button = QtWidgets.QPushButton("Import Config")
        self.export_button = QtWidgets.QPushButton("Export Config")

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        file_buttons = QtWidgets.QHBoxLayout()
        file_buttons.addWidget(self.import_button)
        file_buttons.addWidget(self.export_button)
        layout = QtWidgets.QVBoxLayout(self)
        for button in buttons or []:
            layout.addWidget(button)
        layout.addWidget(scroll)
        layout.addLayout(file_buttons)


class FacialComponentSettings(MayaQWidgetDockableMixin, guide.componentMainSettings):
    """Settings window of a facial component.

    Subclasses set the class attributes, and add buttons with
    :meth:`create_extra_buttons`.

    Attributes:
        toolName (str): Component type.
        connectors (list): Component connectors.
        schema (module): Rig schema module, with SCHEMA, FILE_FILTER,
            FILE_EXT, load_settings and save_settings.
        params (list): Params stored on the guide: the shared schema
            params and the component's own ones.
        extra_groups (tuple): (title, keys) form groups of the component's
            own params.
        title (str): Tool name for the dialogs, e.g. "Eye Rigger".
    """

    toolName = None
    connectors = []
    schema = None
    params = []
    extra_groups = ()
    title = ""

    def __init__(self, parent=None):
        # Delete old instances of the componet settings window.
        pyqt.deleteInstances(self, MayaQDockWidget)

        super(FacialComponentSettings, self).__init__(parent=parent)
        self.settingsTab = FacialSettingsTab(
            self.schema, self.params, self.create_extra_buttons(), self.extra_groups
        )
        self.last_path = ""

        self.setup_componentSettingWindow()
        self.create_componentControls()
        self.populate_componentControls()
        self.create_componentLayout()
        self.create_componentConnections()

    def create_extra_buttons(self):
        """Create the component's own buttons, shown above the form.

        Returns:
            list: QPushButton widgets.
        """
        return []

    def setup_componentSettingWindow(self):
        self.mayaMainWindow = pyqt.maya_main_window()

        self.setObjectName(self.toolName)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle(self.toolName)
        self.resize(380, 700)

    def create_componentControls(self):
        return

    def populate_componentControls(self):
        """Populate the controls from the guide attributes."""
        self.tabs.insertTab(1, self.settingsTab, "Component Settings")
        self.settingsTab.form.set_settings(self.guide_settings())

        # populate connections in main settings
        cBox = self.mainSettingsTab.connector_comboBox
        for cnx in self.connectors:
            cBox.addItem(cnx)
        self.connector_items = [cBox.itemText(i) for i in range(cBox.count())]
        currentConnector = self.root.attr("connector").get()
        if currentConnector not in self.connector_items:
            cBox.addItem(currentConnector)
            self.connector_items.append(currentConnector)
        cBox.setCurrentIndex(self.connector_items.index(currentConnector))

    def create_componentLayout(self):
        self.settings_layout = QtWidgets.QVBoxLayout()
        self.settings_layout.addWidget(self.tabs)
        self.settings_layout.addWidget(self.close_button)
        self.setLayout(self.settings_layout)

    def create_componentConnections(self):
        tab = self.settingsTab
        self.mainSettingsTab.connector_comboBox.currentIndexChanged.connect(
            partial(
                self.updateConnector,
                self.mainSettingsTab.connector_comboBox,
                self.connector_items,
            )
        )
        tab.form.valueChanged.connect(self.set_guide_value)
        tab.import_button.clicked.connect(partial(self.import_settings, None))
        tab.export_button.clicked.connect(partial(self.export_settings, None))

    def guide_settings(self):
        """Get the rig settings stored on the guide.

        Returns:
            dict: {key: value}
        """
        return {param.key: self.root.attr(param.key).get() for param in self.params}

    def set_guide_value(self, key, value):
        """Store a setting on the guide.

        Args:
            key (str): Setting key.
            value (object): Setting value.
        """
        self.root.attr(key).set(value)

    def _shared(self, settings):
        """Keep the settings shared by the tool and the guide.

        The component's own params never go to or come from tool files,
        even with a tool setting of the same name.
        """
        keys = set(param.key for param in self.params)
        shared = settings_schema.filter_scope(settings, self.schema.SCHEMA, "shared")
        return {key: value for key, value in shared.items() if key in keys}

    def _start_dir(self):
        if self.last_path:
            return os.path.dirname(self.last_path)
        return cmds.workspace(query=True, rootDirectory=True)

    def import_settings(self, path=None):
        """Load the guide settings from a configuration file of the tool.

        Tool-only settings are ignored.

        Args:
            path (str, optional): File path. Asks for one when None.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Import {} Configuration".format(self.title),
                self._start_dir(),
                self.schema.FILE_FILTER,
            )
        if not path:
            return
        try:
            settings, warnings = self.schema.load_settings(path)
        except ValueError as error:
            cmds.warning(str(error))
            return
        for warning in warnings:
            cmds.warning("{}: {}".format(self.title, warning))
        self.last_path = path
        settings = self._shared(settings)
        for key, value in settings.items():
            self.root.attr(key).set(value)
        self.settingsTab.form.set_settings(settings)

    def export_settings(self, path=None):
        """Save the guide settings to a configuration file of the tool.

        Args:
            path (str, optional): File path. Asks for one when None.
        """
        if not path:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export {} Configuration".format(self.title),
                self._start_dir(),
                self.schema.FILE_FILTER,
            )
        if not path:
            return
        path = config_io.file_path(path, self.schema.FILE_EXT)
        settings = settings_schema.defaults(self.schema.SCHEMA)
        settings.update(self._shared(self.guide_settings()))
        self.schema.save_settings(path, settings)
        self.last_path = path

    def dockCloseEventTriggered(self):
        pyqt.deleteInstances(self, MayaQDockWidget)
