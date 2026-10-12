"""Settings form: a Qt form generated from a settings schema.

Builds one widget per :class:`mgear.core.settings_schema.Param`, grouped in
boxes, and reads or writes all values as a settings dict. String settings
with a ``kind`` get a "<<" button that fills them from the Maya selection
and a button that selects what they hold.

Example:
    >>> from mgear.core import settings_form
    >>> form = settings_form.SettingsForm(
    ...     SCHEMA, groups=[("Geometry", ["eyeMesh", "edgeLoop"])]
    ... )
    >>> form.set_settings({"eyeMesh": "eye_L_geo"})
    >>> form.get_settings()["eyeMesh"]
    'eye_L_geo'
"""

from maya import cmds

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtWidgets

from mgear.core import meshNavigation
from mgear.core import settings_schema

SPIN_RANGE = 1000000


def value_from_selection(kind):
    """Get a setting value from the Maya selection.

    Args:
        kind (str): "mesh", "node", "set", "edges", "vertices" or "vertex".

    Returns:
        str: The value, or "" when the selection doesn't fit.
    """
    if kind in ("edges", "vertices"):
        return meshNavigation.components_from_selection(
            "edge" if kind == "edges" else "vertex"
        )
    if kind == "vertex":
        text = meshNavigation.components_from_selection("vertex")
        mesh, _, indices = meshNavigation.parse_component_string(text)
        if len(indices) != 1:
            return ""
        return meshNavigation.format_component_string(mesh, "vertex", indices)
    if kind == "set":
        sets = cmds.ls(selection=True, type="objectSet") or []
        return sets[0] if sets else ""
    selection = cmds.ls(selection=True, objectsOnly=True) or []
    if not selection:
        return ""
    if kind == "mesh":
        shapes = cmds.listRelatives(selection[0], shapes=True, type="mesh")
        if not shapes and cmds.nodeType(selection[0]) != "mesh":
            return ""
    return selection[0]


def select_value(value):
    """Select the nodes or components a setting value holds.

    Args:
        value (str): Node name or component string.
    """
    items = [item for item in value.replace(" ", ",").split(",") if item]
    items = [item for item in items if cmds.objExists(item)]
    if items:
        cmds.select(items)


class SettingsForm(QtWidgets.QWidget):
    """Form editing the settings of a schema, starting at their defaults.

    Args:
        schema (list): Schema params.
        groups (list, optional): (title, [keys]) boxes to show. Defaults to
            one box with every param.
        parent (QtWidgets.QWidget, optional): Parent widget.
    """

    valueChanged = QtCore.Signal(str, object)

    def __init__(self, schema, groups=None, parent=None):
        super(SettingsForm, self).__init__(parent)
        self.schema = {param.key: param for param in schema}
        self.groups = groups or [("", [param.key for param in schema])]
        self.fields = {}
        self.rows = {}
        self._build()
        self.set_settings(settings_schema.defaults(schema))

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for title, keys in self.groups:
            box = QtWidgets.QGroupBox(title)
            form = QtWidgets.QFormLayout(box)
            form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
            for key in keys:
                param = self.schema[key]
                field, row = self._create_field(param)
                label = QtWidgets.QLabel(param.label)
                if param.tooltip:
                    label.setToolTip(param.tooltip)
                    field.setToolTip(param.tooltip)
                form.addRow(label, row)
                self.fields[key] = field
                self.rows[key] = (label, row)
            layout.addWidget(box)
        layout.addStretch()

    def _create_field(self, param):
        """Create the widget of a param.

        Returns:
            tuple: (value widget, row widget holding it)
        """
        key = param.key
        if param.value_type == "bool":
            field = QtWidgets.QCheckBox()
            field.toggled.connect(lambda value: self._changed(key))
            return field, field
        if param.value_type == "enum":
            field = QtWidgets.QComboBox()
            field.addItems([choice.title() for choice in param.choices])
            field.currentIndexChanged.connect(lambda value: self._changed(key))
            return field, field
        if param.value_type in ("long", "double"):
            if param.value_type == "long":
                field = QtWidgets.QSpinBox()
            else:
                field = QtWidgets.QDoubleSpinBox()
                field.setDecimals(3)
                field.setSingleStep(0.01)
            minimum = param.minimum if param.minimum is not None else -SPIN_RANGE
            maximum = param.maximum if param.maximum is not None else SPIN_RANGE
            field.setRange(minimum, maximum)
            field.valueChanged.connect(lambda value: self._changed(key))
            return field, field
        field = QtWidgets.QLineEdit()
        field.textChanged.connect(lambda value: self._changed(key))
        if not param.kind:
            return field, field
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(field)
        fill = QtWidgets.QPushButton("<<")
        fill.setToolTip("Fill from the selection")
        fill.setFixedWidth(30)
        fill.clicked.connect(lambda: self.fill_from_selection(key))
        row_layout.addWidget(fill)
        select = QtWidgets.QPushButton("Sel")
        select.setToolTip("Select in the scene")
        select.setFixedWidth(34)
        select.clicked.connect(lambda: select_value(field.text()))
        row_layout.addWidget(select)
        return field, row

    def _changed(self, key):
        self.valueChanged.emit(key, self.value(key))

    def value(self, key):
        """Get the value of a setting.

        Args:
            key (str): Setting key.

        Returns:
            object: The value.
        """
        field = self.fields[key]
        param = self.schema[key]
        if param.value_type == "bool":
            return field.isChecked()
        if param.value_type == "enum":
            return field.currentIndex()
        if param.value_type in ("long", "double"):
            return field.value()
        return field.text()

    def set_value(self, key, value):
        """Set the value of a setting.

        Args:
            key (str): Setting key.
            value (object): The value.
        """
        field = self.fields[key]
        param = self.schema[key]
        if param.value_type == "bool":
            field.setChecked(bool(value))
        elif param.value_type == "enum":
            field.setCurrentIndex(int(value))
        elif param.value_type in ("long", "double"):
            field.setValue(value)
        else:
            field.setText(value or "")

    def get_settings(self):
        """Get the values of all the form settings.

        Returns:
            dict: {key: value}
        """
        return {key: self.value(key) for key in self.fields}

    def set_settings(self, settings):
        """Set the values of the form settings found in a dict.

        A bulk set doesn't emit ``valueChanged``.

        Args:
            settings (dict): Settings, other keys are ignored.
        """
        blocked = self.blockSignals(True)
        try:
            for key, value in settings.items():
                if key in self.fields:
                    self.set_value(key, value)
        finally:
            self.blockSignals(blocked)

    def set_row_visible(self, key, visible):
        """Show or hide the row of a setting.

        Args:
            key (str): Setting key.
            visible (bool): Visibility.
        """
        for widget in self.rows[key]:
            widget.setVisible(visible)

    def fill_from_selection(self, key):
        """Fill a string setting from the Maya selection.

        Args:
            key (str): Setting key.

        Returns:
            bool: True if the selection fit the setting.
        """
        value = value_from_selection(self.schema[key].kind)
        if not value:
            cmds.warning(
                "Select a {} for {}".format(
                    self.schema[key].kind, self.schema[key].label
                )
            )
            return False
        self.set_value(key, value)
        return True
