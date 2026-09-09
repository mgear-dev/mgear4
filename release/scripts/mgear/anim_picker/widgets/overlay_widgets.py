# python
import os

# dcc
import maya.cmds as cmds

# mgear
import mgear
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtWidgets
from mgear.core import string

# module
from mgear.anim_picker import picker_node
from mgear.anim_picker.widgets import basic
from mgear.anim_picker.handlers import file_handlers

# constants -------------------------------------------------------------------
_LAST_USED_DIRECTORY = None

# Autosave preference keys (stored in QSettings("mgear", "anim_picker"))
AUTOSAVE_ENABLED_KEY = "autosave_enabled"
AUTOSAVE_INTERVAL_KEY = "autosave_interval"
AUTOSAVE_DEFAULT_INTERVAL = 10


def _settings_bool(settings, key, default=False):
    """Read a boolean from QSettings, coercing string-stored values.

    Args:
        settings (QtCore.QSettings): The settings store to read from.
        key (str): The setting key.
        default (bool, optional): Value returned when the key is missing.

    Returns:
        bool: The stored boolean value.
    """
    value = settings.value(key, default)
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes")
    return bool(value)


class OverlayWidget(QtWidgets.QWidget):
    """
    Transparent overlay type widget

    add resize to parent resetEvent to resize this event window as:
    """

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        self.set_default_background_color()
        self.setup()

    def set_default_background_color(self):
        palette = self.parent().palette()
        color = palette.color(QtGui.QPalette.Window)
        self.set_overlay_background(color)

    def set_overlay_background(self, color=QtGui.QColor(20, 20, 20, 90)):
        palette = QtGui.QPalette(self.parent().palette())
        palette.setColor(QtGui.QPalette.Window, color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

    def setup(self):
        # Add default layout
        self.layout = QtWidgets.QVBoxLayout(self)

        # Hide by default
        self.hide()


class SaveOverlayWidget(OverlayWidget):
    """Save options overlay widget"""

    def __init__(self, parent):
        OverlayWidget.__init__(self, parent=parent)

    def setup(self):
        OverlayWidget.setup(self)

        # Context message shown above the options when the overlay is opened as
        # a prompt (autosave reminder / unsaved changes on close). Hidden for a
        # normal manual save.
        self.header_label = QtWidgets.QLabel()
        self.header_label.setWordWrap(True)
        self.header_label.setStyleSheet("font-weight: bold; color: #f0c040;")
        self.header_label.hide()
        self.layout.addWidget(self.header_label)

        # Add options group box
        group_box = QtWidgets.QGroupBox()
        group_box.setTitle("Save options")
        self.option_layout = QtWidgets.QVBoxLayout(group_box)
        self.layout.addWidget(group_box)

        # Add options
        self.add_node_save_options()
        self.add_file_save_options()
        self.add_autosave_options()

        # Add action buttons
        self.add_confirmation_buttons()

        # Add vertical spacer
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.layout.addItem(spacer)

        self.data_node = None

        # Callback fired after the user resolves the overlay when it is shown
        # as a prompt (autosave / save-on-close). Receives the outcome string
        # ("saved", "discard" or "cancel"). None during normal manual save.
        self._on_finished = None

    def add_node_save_options(self):
        """Save data to node option"""
        self.node_option_cb = QtWidgets.QCheckBox()
        self.node_option_cb.setText("Save data to node")

        self.option_layout.addWidget(self.node_option_cb)

    def add_file_save_options(self):
        """Add save to file options"""
        self.file_option_cb = QtWidgets.QCheckBox()
        self.file_option_cb.setText("Save data to file")

        self.option_layout.addWidget(self.file_option_cb)

        file_layout = QtWidgets.QHBoxLayout()

        self.file_path_le = QtWidgets.QLineEdit()
        file_layout.addWidget(self.file_path_le)

        file_btn = basic.CallbackButton(callback=self.select_file_event)
        file_btn.setText("Select File")
        file_layout.addWidget(file_btn)

        self.option_layout.addLayout(file_layout)

    def add_autosave_options(self):
        """Add autosave enable + interval options"""
        autosave_layout = QtWidgets.QHBoxLayout()

        self.autosave_cb = QtWidgets.QCheckBox()
        self.autosave_cb.setText("Enable autosave")
        self.autosave_cb.setToolTip(
            "Periodically prompt to save the picker "
            "(never saves in background)"
        )
        autosave_layout.addWidget(self.autosave_cb)

        self.autosave_interval_sb = QtWidgets.QSpinBox()
        self.autosave_interval_sb.setMinimum(1)
        self.autosave_interval_sb.setMaximum(240)
        self.autosave_interval_sb.setValue(AUTOSAVE_DEFAULT_INTERVAL)
        self.autosave_interval_sb.setSuffix(" min")
        autosave_layout.addWidget(self.autosave_interval_sb)

        self.option_layout.addLayout(autosave_layout)

        # Persist and re-apply the timer whenever the settings change
        self.autosave_cb.stateChanged.connect(
            self._autosave_settings_changed
        )
        self.autosave_interval_sb.valueChanged.connect(
            self._autosave_settings_changed
        )

    def _autosave_settings(self):
        """Return the QSettings store for anim picker preferences"""
        return QtCore.QSettings("mgear", "anim_picker")

    def get_autosave_enabled(self):
        """Return the persisted autosave enabled state"""
        return _settings_bool(
            self._autosave_settings(), AUTOSAVE_ENABLED_KEY, False
        )

    def get_autosave_interval(self):
        """Return the persisted autosave interval in minutes"""
        settings = self._autosave_settings()
        try:
            interval = int(
                settings.value(
                    AUTOSAVE_INTERVAL_KEY, AUTOSAVE_DEFAULT_INTERVAL
                )
            )
        except (TypeError, ValueError):
            interval = AUTOSAVE_DEFAULT_INTERVAL
        return max(1, interval)

    def _load_autosave_settings(self):
        """Restore the autosave controls from persisted preferences"""
        self.autosave_cb.blockSignals(True)
        self.autosave_interval_sb.blockSignals(True)
        self.autosave_cb.setChecked(self.get_autosave_enabled())
        self.autosave_interval_sb.setValue(self.get_autosave_interval())
        self.autosave_cb.blockSignals(False)
        self.autosave_interval_sb.blockSignals(False)

    def _autosave_settings_changed(self, *args):
        """Persist autosave settings and (re)start the parent timer"""
        settings = self._autosave_settings()
        settings.setValue(
            AUTOSAVE_ENABLED_KEY, self.autosave_cb.isChecked()
        )
        settings.setValue(
            AUTOSAVE_INTERVAL_KEY, self.autosave_interval_sb.value()
        )
        apply_settings = getattr(
            self.parent(), "apply_autosave_settings", None
        )
        if callable(apply_settings):
            apply_settings()

    def add_confirmation_buttons(self):
        """Add save confirmation buttons to overlay"""
        btn_layout = QtWidgets.QHBoxLayout()

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum,
        )
        btn_layout.addItem(spacer)

        close_btn = basic.CallbackButton(callback=self.cancel_event)
        close_btn.setText("Cancel")
        btn_layout.addWidget(close_btn)

        # Only shown when the overlay is opened as a prompt (save-on-close), so
        # the user can close without saving. Hidden during normal manual save.
        self.discard_btn = basic.CallbackButton(callback=self.discard_event)
        self.discard_btn.setText("Don't Save")
        self.discard_btn.hide()
        btn_layout.addWidget(self.discard_btn)

        save_btn = basic.CallbackButton(callback=self.save_event)
        save_btn.setText("Save")
        btn_layout.addWidget(save_btn)

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum,
        )
        btn_layout.addItem(spacer)

        self.layout.addLayout(btn_layout)

    def _set_message(self, message):
        """Show or clear the context header message"""
        if message:
            self.header_label.setText(message)
            self.header_label.show()
        else:
            self.header_label.clear()
            self.header_label.hide()

    def show(self, message=None):
        """Update fields for current data node on show (manual/autosave).

        Args:
            message (str, optional): Context header shown above the options
                (e.g. an autosave reminder). Cleared when not provided.
        """
        self._on_finished = None
        self.discard_btn.hide()
        self._set_message(message)
        self.update_fields()
        OverlayWidget.show(self)

    def show_prompt(self, on_finished=None, message=None):
        """Show the overlay as a save prompt (save-on-close).

        Args:
            on_finished (callable, optional): Called with the outcome string
                ("saved", "discard" or "cancel") once the user resolves the
                overlay. When provided, a "Don't Save" button is shown so the
                user can dismiss without saving.
            message (str, optional): Context header shown above the options.
        """
        self._on_finished = on_finished
        self.discard_btn.setVisible(on_finished is not None)
        self._set_message(message)
        self.update_fields()
        OverlayWidget.show(self)

    def update_fields(self):
        """Update fields for current data node"""
        self.data_node = self.parent().get_current_data_node()

        # Update node field
        self.node_option_cb.setCheckState(QtCore.Qt.Checked)

        # Update file fields
        current_file_path = self.data_node.get_file_path()
        self.file_path_le.setText(current_file_path or "")
        if current_file_path:
            self.file_option_cb.setCheckState(QtCore.Qt.Checked)

        # Restore autosave preferences
        self._load_autosave_settings()

    def _finish(self, outcome):
        """Hide the overlay and fire the pending prompt callback once"""
        self.hide()
        callback = self._on_finished
        self._on_finished = None
        self.discard_btn.hide()
        if callback:
            callback(outcome)

    def select_file_event(self):
        """Open save dialog window to select file path"""
        file_path = self.select_file_dialog()
        if not file_path:
            return
        global _LAST_USED_DIRECTORY
        _LAST_USED_DIRECTORY = os.path.dirname(file_path)
        self.file_path_le.setText(
            file_handlers.replace_path_with_token(file_path)
        )

    def select_file_dialog(self):
        """Get file dialog window starting in default folder"""
        picker_msg = "Picker Datas (*.pkr)"
        if os.environ.get(file_handlers.ANIM_PICKER_VAR, ""):
            path_module = string.normalize_path(
                os.environ.get(file_handlers.ANIM_PICKER_VAR, "")
            )
        else:
            path_module = _LAST_USED_DIRECTORY or basic.get_module_path()
        file_path = QtWidgets.QFileDialog.getSaveFileName(
            self, "Choose file", path_module, picker_msg
        )

        # Filter return result (based on qt version)
        if isinstance(file_path, tuple):
            file_path = file_path[0]

        if not file_path:
            return

        return file_path

    def _get_file_path(self):
        """Return line edit file path"""
        file_path = self.file_path_le.text()

        if file_path:
            return str(file_path)
        return None

    def save_event(self):
        """Process save operation"""
        # Get DataNode
        assert self.data_node, "No data_node found/selected"

        # Get character data
        data = self.parent().get_character_data()

        # Write data to node
        self.data_node.set_data(data)
        # in pyside2 True or False value was implicit, but pyside6 need compare
        # this lambda functions will fix compatibility
        self.to_node = (
            lambda: self.node_option_cb.checkState()
            == QtCore.Qt.CheckState.Checked
        )
        self.to_file = (
            lambda: self.file_option_cb.checkState()
            == QtCore.Qt.CheckState.Checked
        )
        self.data_node.write_data(
            to_node=self.to_node(),
            to_file=self.to_file(),
            file_path=self._get_file_path(),
        )

        # Refresh the saved baseline and restart the autosave countdown
        on_saved = getattr(self.parent(), "on_picker_saved", None)
        if callable(on_saved):
            on_saved()

        # Hide overlay and notify any pending prompt
        self._finish("saved")

    def discard_event(self):
        """Dismiss the prompt without saving (close-without-save)"""
        self._finish("discard")

    def cancel_event(self):
        """Cancel save (keep the window open)"""
        self._finish("cancel")


class AboutOverlayWidget(OverlayWidget):
    def __init__(self, parent=None):
        OverlayWidget.__init__(self, parent=parent)

    def setup(self):
        OverlayWidget.setup(self)

        # Add label
        label = QtWidgets.QLabel(self.get_text())
        self.layout.addWidget(label)

        # Add Close button
        btn_layout = QtWidgets.QHBoxLayout()

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum,
        )
        btn_layout.addItem(spacer)

        close_btn = basic.CallbackButton(callback=self.hide)
        close_btn.setText("Close")
        close_btn.setToolTip("Hide about informations")
        btn_layout.addWidget(close_btn)

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum,
        )
        btn_layout.addItem(spacer)

        self.layout.addLayout(btn_layout)

        # Add vertical spacer
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.layout.addItem(spacer)

    def get_text(self):
        text = """

        Anim_picker,

        Copyright (c) 2012-2013 Guillaume Barlier
        This programe is under MIT license.

        Original repository
        https://github.com/gbarlier

        Current development & maintainence by mGear Dev Team
        https://github.com/mgear-dev/anim_picker

        """

        return text


class LoadOverlayWidget(OverlayWidget):
    def __init__(self, parent=None):
        OverlayWidget.__init__(self, parent=parent)

    def setup(self):
        OverlayWidget.setup(self)
        # Add options group box
        group_box = QtWidgets.QGroupBox()
        group_box.setMaximumHeight(150)
        group_box.setTitle("Load options")
        self.option_layout = QtWidgets.QVBoxLayout(group_box)
        self.add_load_options()
        self.layout.addWidget(group_box)
        self.layout.addLayout(self.option_layout)
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.load_namespace_options()

        #  --------------------------------------------------------------------
        close_btn = basic.CallbackButton(callback=self.hide)
        close_btn.setText("Cancel")
        self.layout.addWidget(close_btn)
        #  --------------------------------------------------------------------
        self.update_namespaces()

    def select_file_event(self):
        """Open save dialog window to select file path"""
        file_path = self.select_file_dialog()
        if not file_path:
            return
        global _LAST_USED_DIRECTORY
        _LAST_USED_DIRECTORY = os.path.dirname(file_path)
        self.file_path_le.setText(file_path)

    def add_load_options(self):
        file_layout = QtWidgets.QHBoxLayout()

        self.file_path_le = QtWidgets.QLineEdit()
        file_layout.addWidget(self.file_path_le)
        file_btn = basic.CallbackButton(callback=self.select_file_event)
        file_btn.setText("Select File")
        file_layout.addWidget(file_btn)

        self.option_layout.addLayout(file_layout)

    def load_picker(self):
        file_path = self.file_path_le.text()
        if file_path == "" or not os.path.exists(file_path):
            msgA = "Path or file does not exist!"
            basic.promptAcceptance(self, msgA, "")
            return
        pkr_data = file_handlers.read_data_file(file_path)
        pkr_data["source_file_path"] = file_path
        namespace = self.namespace_cbox.currentText()
        self.new_picker_node(data=pkr_data, namespace=namespace)

    def update_namespaces(self):
        self.namespace_cbox.blockSignals(True)
        self.namespace_cbox.clear()
        self.namespace_cbox.addItems(self.get_namespaces())
        self.namespace_cbox.blockSignals(False)

    def get_namespaces(self):
        remove_defaults = ["UI", "shared"]
        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
        [namespaces.remove(x) for x in remove_defaults]
        namespaces.extend(["Root", "-Refresh-"])
        return namespaces

    def check_selection(self, index):
        if self.namespace_cbox.currentText() == "-Refresh-":
            self.update_namespaces()
            mgear.log("anim_picker: namespaces refreshed", mgear.sev_info)

    def load_namespace_options(self):
        layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel("Choose Namespace")
        func = self.check_selection
        self.namespace_cbox = basic.CallbackComboBox(
            callback=func, status_tip=None
        )
        layout.addWidget(label)
        layout.addWidget(self.namespace_cbox)
        btn = basic.CallbackButton(callback=self.load_picker)
        btn.setText("Load Picker")
        self.option_layout.addLayout(layout)
        self.option_layout.addWidget(btn)

    def select_file_dialog(self):
        """Get file dialog window starting in default folder"""
        picker_msg = "Picker Datas (*.pkr)"
        path_module = _LAST_USED_DIRECTORY or basic.get_module_path()
        file_path = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose file", path_module, picker_msg
        )

        # Filter return result (based on qt version)
        if isinstance(file_path, tuple):
            file_path = file_path[0]

        if not file_path:
            return

        return file_path

    def new_picker_node(self, data, namespace):
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "New character",
            "Node name",
            QtWidgets.QLineEdit.Normal,
            "PICKER_DATA",
        )

        if not (ok and name):
            return

        # Create new data node
        if namespace != "Root" and cmds.namespace(ex=namespace):
            name = "{}:{}".format(namespace, name)
        data_node = picker_node.DataNode(name=str(name))
        data_node.create()
        data_node.write_data(data=data)
        data_node.read_data()
        self.parent().refresh()
        self.hide()
