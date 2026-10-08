"""Spring Manager window."""

import html
import os
import re
import webbrowser
from collections import OrderedDict
from functools import partial

from maya import cmds
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import maya.api.OpenMaya as om2

import mgear
from mgear.core import callbackManager
from mgear.core import node_remap
from mgear.core import pyqt
from mgear.core import screen_capture
from mgear.core import utils
from mgear.core import widgets

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from . import bake
from . import constants
from . import presets
from . import registry
from . import ui_panels
from .backends import editable_springs
from .backends import get_backend
from .backends import get_backends
from .backends import values_differ

DOCS_URL = (
    "https://mgear4.readthedocs.io/en/master/"
    "animbitsUserDocumentation.html#spring-manager"
)
NEW_VALUES_KEY = constants.SETTINGS_PREFIX + "new_values"
LIBRARY_KEY = constants.SETTINGS_PREFIX + "library"
GRID_VIEW_KEY = constants.SETTINGS_PREFIX + "preset_grid"
SPRINGS_HEIGHT_KEY = constants.SETTINGS_PREFIX + "springs_height"
SPRINGS_HEIGHT = 150
BAKE_LAYER = "springBake"
MISSING_STATE = "plug-in missing"
# bake dialog destination combo index
DESTINATION_LAYER = 1
APPLY_SOLVER_KEY = constants.SETTINGS_PREFIX + "apply_solver"
PRESET_PATH_ROLE = QtCore.Qt.UserRole + 1

COLUMN_NAME = 0
COLUMN_SOLVER = 1
COLUMN_STATE = 2

LIST_ICON_SIZE = 40
GRID_ICON_SIZE = 96
DETAIL_ICON_SIZE = 128

TYPE_COLORS = {
    constants.PRESET_VALUES: QtGui.QColor(70, 140, 200),
    constants.PRESET_RIG: QtGui.QColor(200, 130, 60),
}
TYPE_LABELS = {
    constants.PRESET_VALUES: "Values",
    constants.PRESET_RIG: "Rig",
}
TYPE_HELP = {
    constants.PRESET_VALUES: (
        "Only the parameter values. Applies to any spring: the selected "
        "springs get the values, and selected controls without a spring "
        "get a new one. Use it for reusable looks (soft, stiff, tail...)."
    ),
    constants.PRESET_RIG: (
        "The springs of the selected controls: control names, creation "
        "options and values. Recreates that setup on the same character, "
        "in any namespace. Use it to save a character's spring setup."
    ),
}

# Factory and User libraries come first, custom folders after
BUILTIN_LIBRARY_COUNT = 2

_BADGES = {}


def type_badge(preset_type):
    """Return the cached placeholder icon of a preset type.

    Args:
        preset_type (str): Preset type.

    Returns:
        QtGui.QIcon: A rounded square with the type initial.
    """
    if preset_type not in _BADGES:
        _BADGES[preset_type] = QtGui.QIcon(
            pyqt.text_badge(
                TYPE_LABELS.get(preset_type, "?")[0],
                GRID_ICON_SIZE,
                TYPE_COLORS.get(preset_type, QtGui.QColor(120, 120, 120)),
            )
        )
    return _BADGES[preset_type]


def param_tooltip(spec):
    """Return the rich text tooltip of a parameter.

    Rich text, so Qt wraps the long lines.

    Args:
        spec (constants.ParamSpec): The parameter.

    Returns:
        str: The label in bold, then one paragraph per tooltip line.
    """
    paragraphs = "".join(
        "<p>{}</p>".format(html.escape(line)) for line in spec.tooltip.split("\n")
    )
    return "<b>{}</b>{}".format(html.escape(spec.label), paragraphs)


class Library(object):
    """A preset library folder.

    Attributes:
        label (str): Display name.
        folder (str): Folder path.
        read_only (bool): Presets can't be saved, renamed or deleted.
    """

    def __init__(self, label, folder, read_only=False):
        self.label = label
        self.folder = folder
        self.read_only = read_only


class SavePresetDialog(QtWidgets.QDialog):
    """Name, type, description and thumbnail of a new preset."""

    def __init__(self, can_save_rig, parent=None):
        """Initialize the dialog.

        Args:
            can_save_rig (bool): True when springs are selected, so a rig
                preset can be saved.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(SavePresetDialog, self).__init__(parent)
        self.setWindowTitle("Save Spring Preset")
        self.setMinimumWidth(pyqt.dpi_scale(380))

        self.name_le = QtWidgets.QLineEdit()
        self.name_le.setPlaceholderText("Preset name")
        self.values_rb = QtWidgets.QRadioButton("Values")
        self.rig_rb = QtWidgets.QRadioButton("Rig")
        self.values_rb.setToolTip(TYPE_HELP[constants.PRESET_VALUES])
        self.rig_rb.setToolTip(TYPE_HELP[constants.PRESET_RIG])
        self.rig_rb.setEnabled(can_save_rig)
        if can_save_rig:
            self.rig_rb.setChecked(True)
        else:
            self.values_rb.setChecked(True)
            self.rig_rb.setToolTip(
                TYPE_HELP[constants.PRESET_RIG]
                + "\n\nSelect springs to save a rig preset."
            )
        self.type_help = QtWidgets.QLabel()
        self.type_help.setWordWrap(True)
        self.type_help.setStyleSheet("color: rgb(160, 160, 160);")
        self.description_te = QtWidgets.QPlainTextEdit()
        self.description_te.setPlaceholderText("What is this preset for?")
        self.description_te.setFixedHeight(pyqt.dpi_scale(60))
        self.thumbnail = widgets.ThumbnailEditor(
            pyqt.capture_active_view_image(),
            size=pyqt.dpi_scale(DETAIL_ICON_SIZE),
            image_size=constants.THUMBNAIL_SIZE,
        )

        type_layout = QtWidgets.QHBoxLayout()
        type_layout.addWidget(self.values_rb)
        type_layout.addWidget(self.rig_rb)
        type_layout.addStretch()
        form = QtWidgets.QFormLayout()
        form.addRow("Name", self.name_le)
        form.addRow("Type", type_layout)
        form.addRow("", self.type_help)
        form.addRow("Description", self.description_te)
        form.addRow("Thumbnail", self.thumbnail)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.values_rb.toggled.connect(self._update_help)
        self._update_help()

    def _update_help(self, *args):
        self.type_help.setText(TYPE_HELP[self.preset_type()])

    def _accept(self):
        if not self.name():
            self.name_le.setFocus()
            return
        self.accept()

    def name(self):
        """Return the preset name.

        Returns:
            str: Name, stripped.
        """
        return self.name_le.text().strip()

    def preset_type(self):
        """Return the chosen preset type.

        Returns:
            str: :data:`constants.PRESET_VALUES` or ``PRESET_RIG``.
        """
        if self.rig_rb.isChecked():
            return constants.PRESET_RIG
        return constants.PRESET_VALUES

    def description(self):
        """Return the description.

        Returns:
            str: Description, stripped.
        """
        return self.description_te.toPlainText().strip()


class BakeDialog(QtWidgets.QDialog):
    """Bake options: frame range, pre-roll and delete or keep."""

    def __init__(self, count, parent=None):
        """Initialize the dialog.

        Args:
            count (int): Number of springs to bake, shown in the title.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(BakeDialog, self).__init__(parent)
        self.setWindowTitle("Bake {} Spring(s)".format(count))

        start = cmds.playbackOptions(query=True, minTime=True)
        end = cmds.playbackOptions(query=True, maxTime=True)

        self.playback_rb = QtWidgets.QRadioButton("Playback range")
        self.playback_rb.setChecked(True)
        self.custom_rb = QtWidgets.QRadioButton("Custom range")
        self.start_spin = QtWidgets.QDoubleSpinBox()
        self.end_spin = QtWidgets.QDoubleSpinBox()
        for spin, value in ((self.start_spin, start), (self.end_spin, end)):
            spin.setDecimals(0)
            spin.setRange(-1000000, 1000000)
            spin.setValue(value)
            spin.setEnabled(False)
        self.preroll_spin = QtWidgets.QSpinBox()
        self.preroll_spin.setRange(0, 10000)
        self.preroll_spin.setToolTip(
            "Frames simulated before the start frame so the springs are "
            "settled when baking starts. No keys are added before the start."
        )
        self.destination_combo = QtWidgets.QComboBox()
        self.destination_combo.addItems(("Base layer", "New animation layer"))
        self.destination_combo.setToolTip(
            "A new animation layer keeps the original animation untouched"
        )
        self.layer_le = QtWidgets.QLineEdit(BAKE_LAYER)
        self.layer_le.setEnabled(False)
        self.delete_cb = QtWidgets.QCheckBox("Delete springs after bake")
        self.delete_cb.setChecked(True)
        self.delete_cb.setToolTip(
            "When off, the springs are kept, disconnected from the controls "
            "and marked as baked."
        )

        range_layout = QtWidgets.QHBoxLayout()
        range_layout.addWidget(self.custom_rb)
        range_layout.addWidget(self.start_spin)
        range_layout.addWidget(self.end_spin)
        form = QtWidgets.QFormLayout()
        form.addRow("Pre-roll frames", self.preroll_spin)
        form.addRow("Bake to", self.destination_combo)
        form.addRow("Layer name", self.layer_le)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Bake")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.playback_rb)
        layout.addLayout(range_layout)
        layout.addLayout(form)
        layout.addWidget(self.delete_cb)
        layout.addWidget(buttons)

        self.custom_rb.toggled.connect(self.start_spin.setEnabled)
        self.custom_rb.toggled.connect(self.end_spin.setEnabled)
        self.destination_combo.currentIndexChanged.connect(
            lambda index: self.layer_le.setEnabled(index == DESTINATION_LAYER)
        )

    def options(self):
        """Return the bake options.

        Returns:
            dict: ``start``, ``end``, ``preroll``, ``delete_springs`` and
            ``destination_layer``.
        """
        start = end = None
        if self.custom_rb.isChecked():
            start = self.start_spin.value()
            end = self.end_spin.value()
        return {
            "start": start,
            "end": end,
            "preroll": self.preroll_spin.value(),
            "delete_springs": self.delete_cb.isChecked(),
            "destination_layer": (
                self.layer_le.text().strip() or BAKE_LAYER
                if self.destination_combo.currentIndex() == DESTINATION_LAYER
                else None
            ),
        }


def _float_widget(spec, decimals=3):
    return widgets.FloatSliderSpinBox(
        minimum=spec.minimum,
        maximum=spec.maximum,
        default=spec.default,
        decimals=decimals,
        soft_maximum=spec.soft_maximum,
    )


# parameter kind: widget factory. Kinds without a widget are not shown.
PARAM_WIDGETS = {
    constants.PARAM_FLOAT: _float_widget,
    constants.PARAM_INT: partial(_float_widget, decimals=0),
    constants.PARAM_BOOL: lambda spec: widgets.TriStateCheckBox(),
    constants.PARAM_VECTOR: lambda spec: widgets.VectorSpinBox(
        minimum=spec.minimum, maximum=spec.maximum, default=spec.default
    ),
}


class SpringManager(MayaQWidgetDockableMixin, QtWidgets.QDialog, pyqt.SettingsMixin):
    """Dockable Spring Manager window."""

    toolName = "mgearSpringManager"

    def __init__(self, parent=None):
        """Initialize the window.

        Args:
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(SpringManager, self).__init__(parent)
        pyqt.SettingsMixin.__init__(self)

        self.closed = False
        self.callbacks = callbackManager.CallbackManager()
        self._selection_pending = False
        self._refresh_pending = False
        # selection pushed to Maya by the list, its callback is skipped
        self._pushed_selection = None
        self._items = {}
        self._node_map = {}
        self._panel_backend = None
        self._drag_start = {}
        self._new_values = {}
        self._libraries = []
        self._preset_cache = {}
        self._icon_cache = {}

        # actions
        self.bake_selected_action = None
        self.bake_all_action = None
        self.delete_selected_action = None
        self.delete_all_action = None
        self.select_all_action = None
        self.refresh_action = None
        self.save_preset_action = None
        self.add_library_action = None
        self.remove_library_action = None
        self.reveal_library_action = None
        self.docs_action = None
        self.apply_solver_action = None
        # widgets
        self.menu_bar = None
        self.solver_combo = None
        self.create_section = None
        self.create_stack = None
        self.create_panels = {}
        self.solver_section = None
        self.solver_stack = None
        self.solver_panels = {}
        self.springs_section = None
        self.spring_search_le = None
        self.spring_tree = None
        self.spring_grip = None
        self.params_section = None
        self.params_status = None
        self.params_layout = None
        self.param_widgets = {}
        self.reset_btn = None
        self.key_btn = None
        self.presets_section = None
        self.library_combo = None
        self.add_library_btn = None
        self.grid_view_btn = None
        self.search_le = None
        self.preset_view = None
        self.preset_model = None
        self.preset_proxy = None
        self.detail_widget = None
        self.detail_icon = None
        self.detail_title = None
        self.detail_text = None
        self.apply_btn = None
        self.apply_values_btn = None
        self.save_btn = None
        self.expander = None
        self.missing_label = None
        self.sections = []

        self.setObjectName(self.toolName)
        self.setWindowTitle("Spring Manager")
        self.setMinimumWidth(pyqt.dpi_scale(360))
        if cmds.about(ntOS=True):
            flags = self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint
            self.setWindowFlags(flags)
        elif cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)

        self.create_actions()
        self.create_widgets()
        self.create_layout()

        self.user_settings = {
            GRID_VIEW_KEY: (self.grid_view_btn, False),
            SPRINGS_HEIGHT_KEY: (self.spring_grip, pyqt.dpi_scale(SPRINGS_HEIGHT)),
            APPLY_SOLVER_KEY: (self.apply_solver_action, True),
        }
        self.load_settings()
        self._new_values = self.load_json_setting(NEW_VALUES_KEY, {})
        self._load_libraries()

        self.create_connections()
        self.on_solver_changed()
        self.set_grid_view(self.grid_view_btn.isChecked())
        self.scene_changed()
        self._update_expander()
        self._start_callbacks()

    # -----------------------------------------------------------------
    # UI setup
    # -----------------------------------------------------------------
    def create_actions(self):
        """Create the menu actions."""
        self.bake_selected_action = QtWidgets.QAction("Bake Selected...", self)
        self.bake_all_action = QtWidgets.QAction("Bake All...", self)
        self.delete_selected_action = QtWidgets.QAction("Delete Selected", self)
        self.delete_all_action = QtWidgets.QAction("Delete All", self)
        self.select_all_action = QtWidgets.QAction("Select All Spring Controls", self)
        self.refresh_action = QtWidgets.QAction("Refresh", self)

        self.save_preset_action = QtWidgets.QAction("Save Preset...", self)
        self.add_library_action = QtWidgets.QAction("Add Library Folder...", self)
        self.remove_library_action = QtWidgets.QAction("Remove Library Folder", self)
        self.reveal_library_action = QtWidgets.QAction("Reveal Library Folder", self)
        self.docs_action = QtWidgets.QAction("Documentation", self)
        self.apply_solver_action = QtWidgets.QAction("Apply Solver Settings", self)
        self.apply_solver_action.setCheckable(True)
        self.apply_solver_action.setChecked(True)
        self.apply_solver_action.setToolTip(
            "Rig presets also set the scene solver settings (gravity, "
            "start frame...)"
        )

    def create_widgets(self):
        """Create the widgets."""
        self.menu_bar = QtWidgets.QMenuBar()
        springs_menu = self.menu_bar.addMenu("Springs")
        springs_menu.addAction(self.bake_selected_action)
        springs_menu.addAction(self.bake_all_action)
        springs_menu.addSeparator()
        springs_menu.addAction(self.delete_selected_action)
        springs_menu.addAction(self.delete_all_action)
        springs_menu.addSeparator()
        springs_menu.addAction(self.select_all_action)
        springs_menu.addAction(self.refresh_action)
        presets_menu = self.menu_bar.addMenu("Presets")
        presets_menu.addAction(self.save_preset_action)
        presets_menu.addAction(self.apply_solver_action)
        presets_menu.addSeparator()
        presets_menu.addAction(self.add_library_action)
        presets_menu.addAction(self.remove_library_action)
        presets_menu.addAction(self.reveal_library_action)
        help_menu = self.menu_bar.addMenu("Help")
        help_menu.addAction(self.docs_action)

        # solver
        self.solver_combo = QtWidgets.QComboBox()
        model = self.solver_combo.model()
        for index, backend in enumerate(get_backends()):
            self.solver_combo.addItem(backend.label, backend.name)
            if not backend.is_available():
                item = model.item(index)
                item.setEnabled(False)
                item.setToolTip(backend.unavailable_message)

        # create
        self.create_section = widgets.CollapsibleWidget(
            "Create", expanded=True, expandable=False
        )
        # one create panel per solver, see ui_panels
        self.create_stack = QtWidgets.QStackedWidget()
        self.solver_section = widgets.CollapsibleWidget(
            "Solver", expanded=True, expandable=False
        )
        self.solver_stack = QtWidgets.QStackedWidget()
        for backend in get_backends():
            create_class = ui_panels.CREATE_PANELS.get(
                backend.name, ui_panels.DefaultCreatePanel
            )
            panel = create_class()
            self.create_panels[backend.name] = panel
            self.create_stack.addWidget(panel)
            solver_class = ui_panels.SOLVER_PANELS.get(backend.name)
            if solver_class:
                panel = solver_class()
                panel.springs_fn = self.selected_springs
                panel.all_springs_fn = self.all_springs
                self.solver_panels[backend.name] = panel
                self.solver_stack.addWidget(panel)
        self.missing_label = QtWidgets.QLabel(
            "Some springs need a solver plug-in that is not loaded: they "
            "can't be edited or baked. See Help > Documentation."
        )
        self.missing_label.setWordWrap(True)
        self.missing_label.setStyleSheet(ui_panels.WARNING_STYLE)
        self.missing_label.setVisible(False)

        # springs: fixed height list, resized with the grip under it
        self.springs_section = widgets.CollapsibleWidget(
            "Springs", expanded=True, expandable=False
        )
        self.spring_search_le = QtWidgets.QLineEdit()
        self.spring_search_le.setPlaceholderText("Filter springs (* wildcard)")
        self.spring_search_le.setClearButtonEnabled(True)
        self.spring_tree = QtWidgets.QTreeWidget()
        self.spring_tree.setHeaderLabels(("Control", "Solver", "State"))
        self.spring_tree.setRootIsDecorated(False)
        self.spring_tree.setUniformRowHeights(True)
        self.spring_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.spring_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.spring_grip = widgets.HeightGrip(
            self.spring_tree, minimum=pyqt.dpi_scale(60)
        )
        self.spring_grip.set_target_height(pyqt.dpi_scale(SPRINGS_HEIGHT))
        header = self.spring_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COLUMN_NAME, QtWidgets.QHeaderView.Stretch)
        for column in (COLUMN_SOLVER, COLUMN_STATE):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)

        # parameters
        self.params_section = widgets.CollapsibleWidget(
            "Parameters", expanded=True, expandable=False
        )
        self.params_status = QtWidgets.QLabel()
        self.params_status.setWordWrap(True)
        self.params_layout = QtWidgets.QVBoxLayout()
        self.params_layout.setContentsMargins(0, 0, 0, 0)
        self.reset_btn = QtWidgets.QPushButton("Reset Defaults")
        self.key_btn = QtWidgets.QPushButton("Key All")
        self.key_btn.setToolTip("Set a key on every parameter of the selected springs")

        # presets
        self.presets_section = widgets.CollapsibleWidget("Presets", expanded=True)
        self.library_combo = QtWidgets.QComboBox()
        self.library_combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.add_library_btn = QtWidgets.QToolButton()
        self.add_library_btn.setText("+")
        self.add_library_btn.setToolTip("Add a library folder")
        self.grid_view_btn = QtWidgets.QToolButton()
        self.grid_view_btn.setText("Grid")
        self.grid_view_btn.setCheckable(True)
        self.grid_view_btn.setToolTip("Show the presets as a thumbnail grid")
        self.search_le = QtWidgets.QLineEdit()
        self.search_le.setPlaceholderText("Search presets (* wildcard)")
        self.search_le.setClearButtonEnabled(True)
        self.preset_model = QtGui.QStandardItemModel(self)
        self.preset_proxy = QtCore.QSortFilterProxyModel(self)
        self.preset_proxy.setSourceModel(self.preset_model)
        self.preset_view = QtWidgets.QListView()
        self.preset_view.setModel(self.preset_proxy)
        self.preset_view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.preset_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.preset_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.preset_view.setMinimumHeight(pyqt.dpi_scale(80))
        self.preset_view.setResizeMode(QtWidgets.QListView.Adjust)
        self.detail_widget = QtWidgets.QWidget()
        self.detail_icon = QtWidgets.QLabel()
        self.detail_icon.setFixedSize(
            pyqt.dpi_scale(LIST_ICON_SIZE * 2), pyqt.dpi_scale(LIST_ICON_SIZE * 2)
        )
        self.detail_icon.setAlignment(QtCore.Qt.AlignCenter)
        self.detail_title = QtWidgets.QLabel()
        self.detail_text = QtWidgets.QLabel()
        self.detail_text.setWordWrap(True)
        self.detail_text.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.detail_text.setStyleSheet("color: rgb(170, 170, 170);")
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.apply_btn.setToolTip(
            "Values presets: apply the values to the selected springs and "
            "create springs on selected controls without one.\n"
            "Rig presets: create or update springs on the preset controls, "
            "in the namespace of the selection."
        )
        self.apply_values_btn = QtWidgets.QPushButton("Apply Values")
        self.apply_values_btn.setToolTip(
            "Apply only the parameter values to the selected springs, for "
            "any preset type"
        )
        self.save_btn = QtWidgets.QPushButton("Save...")
        self.save_btn.setToolTip(
            "Save a preset: a values preset (from the selected spring or the "
            "values for new springs) or a rig preset (the selected springs)"
        )

        # takes the free space when no stretching section is expanded
        self.expander = QtWidgets.QWidget()
        self.expander.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding
        )
        self.sections = [
            self.create_section,
            self.solver_section,
            self.springs_section,
            self.params_section,
            self.presets_section,
        ]

    def create_layout(self):
        """Lay the widgets out."""
        window_layout = QtWidgets.QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)
        window_layout.setMenuBar(self.menu_bar)
        # the sections scroll when the window is too short for them
        content = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(content)
        window_layout.addWidget(scroll)
        main_layout = QtWidgets.QVBoxLayout(content)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        solver_layout = QtWidgets.QHBoxLayout()
        solver_layout.setContentsMargins(4, 2, 4, 2)
        solver_layout.addWidget(QtWidgets.QLabel("Solver"))
        solver_layout.addWidget(self.solver_combo, 1)
        main_layout.addLayout(solver_layout)
        main_layout.addWidget(self.missing_label)

        self.create_section.addWidget(self.create_stack)
        self.solver_section.addWidget(self.solver_stack)
        main_layout.addWidget(self.solver_section)
        main_layout.addWidget(self.create_section)

        self.springs_section.addWidget(self.spring_search_le)
        self.springs_section.addWidget(self.spring_tree)
        self.springs_section.addWidget(self.spring_grip)
        main_layout.addWidget(self.springs_section)

        params_buttons = QtWidgets.QHBoxLayout()
        params_buttons.addWidget(self.reset_btn)
        params_buttons.addWidget(self.key_btn)
        self.params_section.addWidget(self.params_status)
        self.params_section.addLayout(self.params_layout)
        self.params_section.addLayout(params_buttons)
        main_layout.addWidget(self.params_section)

        library_layout = QtWidgets.QHBoxLayout()
        library_layout.addWidget(self.library_combo)
        library_layout.addWidget(self.add_library_btn)
        library_layout.addWidget(self.grid_view_btn)
        detail_text_layout = QtWidgets.QVBoxLayout()
        detail_text_layout.addWidget(self.detail_title)
        detail_text_layout.addWidget(self.detail_text, 1)
        detail_layout = QtWidgets.QHBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(self.detail_icon, 0, QtCore.Qt.AlignTop)
        detail_layout.addLayout(detail_text_layout, 1)
        preset_buttons = QtWidgets.QHBoxLayout()
        preset_buttons.addWidget(self.apply_btn)
        preset_buttons.addWidget(self.apply_values_btn)
        preset_buttons.addWidget(self.save_btn)
        self.presets_section.addLayout(library_layout)
        self.presets_section.addWidget(self.search_le)
        self.presets_section.addWidget(self.preset_view)
        self.presets_section.addWidget(self.detail_widget)
        self.presets_section.body_layout.setStretchFactor(self.preset_view, 1)
        self.presets_section.addLayout(preset_buttons)
        main_layout.addWidget(self.presets_section)

        main_layout.addWidget(self.expander)

    def create_connections(self):
        """Connect the signals."""
        self.bake_selected_action.triggered.connect(self.bake_selected)
        self.bake_all_action.triggered.connect(self.bake_all)
        self.delete_selected_action.triggered.connect(self.delete_selected)
        self.delete_all_action.triggered.connect(self.delete_all)
        self.select_all_action.triggered.connect(self.select_all_controls)
        self.refresh_action.triggered.connect(self.scene_changed)
        self.save_preset_action.triggered.connect(self.save_preset)
        self.add_library_action.triggered.connect(self.add_library)
        self.remove_library_action.triggered.connect(self.remove_library)
        self.reveal_library_action.triggered.connect(self.reveal_library)
        self.docs_action.triggered.connect(partial(webbrowser.open, DOCS_URL))

        for section in self.sections:
            section.expandedChanged.connect(self._update_expander)
        self.solver_combo.currentIndexChanged.connect(self.on_solver_changed)
        for panel in self.create_panels.values():
            panel.createRequested.connect(self.create_springs)
        self.spring_search_le.textChanged.connect(self.filter_springs)
        self.spring_tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.spring_tree.customContextMenuRequested.connect(self._tree_menu)
        self.reset_btn.clicked.connect(self.reset_params)
        self.key_btn.clicked.connect(self.key_params)

        self.library_combo.currentIndexChanged.connect(self.on_library_changed)
        self.add_library_btn.clicked.connect(self.add_library)
        self.grid_view_btn.toggled.connect(self.set_grid_view)
        self.search_le.textChanged.connect(self._on_search_changed)
        self.preset_view.doubleClicked.connect(self._on_preset_double_clicked)
        self.preset_view.customContextMenuRequested.connect(self._preset_menu)
        self.preset_view.selectionModel().selectionChanged.connect(
            self.update_preset_details
        )
        self.apply_btn.clicked.connect(self.apply_preset)
        self.apply_values_btn.clicked.connect(self.apply_preset_values)
        self.save_btn.clicked.connect(self.save_preset)

    def _update_expander(self, *args):
        """Fill the free space when no stretching section is expanded."""
        stretching = any(
            section.is_expanded() and section.is_expandable()
            for section in self.sections
        )
        self.expander.setVisible(not stretching)

    def _on_search_changed(self, text):
        pyqt.set_proxy_filter(self.preset_proxy, text)

    def _on_preset_double_clicked(self, index):
        self.apply_preset()

    # -----------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------
    def _start_callbacks(self):
        """Register the selection, undo and scene callbacks."""
        cbm = self.callbacks
        cbm.selectionChangedCB("selection", self._on_selection_event)
        cbm.eventCB("undo", self._on_scene_event, "Undo")
        cbm.eventCB("redo", self._on_scene_event, "Redo")
        cbm.sceneMessageCB(
            "afterNew", self._on_scene_event, om2.MSceneMessage.kAfterNew
        )
        cbm.sceneMessageCB(
            "afterOpen", self._on_scene_event, om2.MSceneMessage.kAfterOpen
        )

    def _on_selection_event(self, *args):
        """Coalesce Maya selection callbacks into one UI update."""
        if self._selection_pending:
            return
        self._selection_pending = True
        QtCore.QTimer.singleShot(0, self._deferred_selection)

    def _deferred_selection(self):
        self._selection_pending = False
        if self.closed:
            return
        if self._pushed_selection is not None:
            pushed = self._pushed_selection
            self._pushed_selection = None
            if pushed == cmds.ls(selection=True, long=True):
                return
        self.on_maya_selection_changed()

    def _on_scene_event(self, *args):
        """Coalesce undo, redo and scene callbacks into one refresh."""
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QtCore.QTimer.singleShot(0, self._deferred_refresh)

    def _deferred_refresh(self):
        self._refresh_pending = False
        if not self.closed:
            self.scene_changed()

    def scene_changed(self):
        """Rebuild the springs list and sync it with the Maya selection."""
        self.refresh_springs()
        self.on_maya_selection_changed()
        panel = self.solver_panels.get(self.solver_combo.currentData())
        if panel:
            panel.refresh()

    # -----------------------------------------------------------------
    # Solver and create
    # -----------------------------------------------------------------
    def current_backend(self):
        """Return the backend selected in the solver combo.

        Returns:
            SpringBackend: The backend.
        """
        return get_backend(self.solver_combo.currentData())

    def on_solver_changed(self, *args):
        """Show the create options of the solver and refresh the panel."""
        backend = self.current_backend()
        name = backend.name if backend else None
        if name in self.create_panels:
            pyqt.show_stacked_page(self.create_stack, self.create_panels[name])
        solver_panel = self.solver_panels.get(name)
        self.solver_section.setVisible(bool(solver_panel))
        if solver_panel:
            pyqt.show_stacked_page(self.solver_stack, solver_panel)
            solver_panel.refresh()
        self.update_params_panel()
        self.refresh_presets()

    def create_springs(self, options=None):
        """Create springs on the selected controls.

        Args:
            options (dict, optional): Create options from the solver's
                create panel.
        """
        controls = cmds.ls(selection=True, long=True, type="transform")
        if not controls:
            cmds.warning("Select the controls to add springs to")
            return
        backend = self.current_backend()
        if not backend or not backend.is_available():
            cmds.warning("The selected solver is not available")
            return
        springs = backend.create(
            controls, self._backend_new_values(backend), dict(options or {})
        )
        if springs:
            cmds.select(controls, replace=True)
        self.scene_changed()
        mgear.log("Created {} spring(s)".format(len(springs)))

    # -----------------------------------------------------------------
    # Springs list and selection sync
    # -----------------------------------------------------------------
    def refresh_springs(self):
        """Rebuild the springs list from the scene.

        Spring records still in the scene are reused, keeping their cached
        controls and settings node.
        """
        springs = registry.list_springs(previous=list(self._items))
        self._items = {}
        # plug-in queries once per backend, not per row
        available = {}
        missing = False
        with pyqt.block_signals(self.spring_tree):
            self.spring_tree.clear()
            for spring in springs:
                backend = get_backend(spring.backend)
                if spring.backend not in available:
                    available[spring.backend] = bool(backend) and (
                        backend.is_available(),
                        backend.editable,
                    )
                state = available[spring.backend]
                missing = missing or not (state and state[0])
                item = QtWidgets.QTreeWidgetItem(
                    [
                        spring.label,
                        backend.label if backend else spring.backend,
                        spring.state if state and state[0] else MISSING_STATE,
                    ]
                )
                item.setData(COLUMN_NAME, QtCore.Qt.UserRole, spring)
                item.setToolTip(COLUMN_NAME, spring.node)
                if state and not state[1]:
                    item.setToolTip(COLUMN_SOLVER, backend.read_only_message)
                    item.setForeground(
                        COLUMN_SOLVER, QtGui.QBrush(ui_panels.WARNING_COLOR)
                    )
                self.spring_tree.addTopLevelItem(item)
                self._items[spring] = item
        self._node_map = registry.node_map(springs)
        self.missing_label.setVisible(missing)
        self.filter_springs()

    def filter_springs(self, *args):
        """Hide the springs not matching the filter text."""
        text = self.spring_search_le.text().strip()
        pattern = re.compile(pyqt.wildcard_to_regex(text), re.IGNORECASE)
        for item in self._items.values():
            visible = not text or any(
                pattern.search(item.text(column))
                for column in (COLUMN_NAME, COLUMN_SOLVER, COLUMN_STATE)
            )
            item.setHidden(not visible)

    def all_springs(self):
        """Return the springs listed, as of the last refresh.

        Returns:
            list: :class:`registry.Spring` records.
        """
        return list(self._items)

    def selected_springs(self):
        """Return the springs selected in the list.

        Returns:
            list: :class:`registry.Spring` records.
        """
        return [
            item.data(COLUMN_NAME, QtCore.Qt.UserRole)
            for item in self.spring_tree.selectedItems()
        ]

    def on_maya_selection_changed(self):
        """Select the rows of the springs owning the Maya selection."""
        if self.closed:
            return
        springs = registry.selected_springs(self._node_map)
        if any(spring not in self._items for spring in springs):
            self.refresh_springs()
        with pyqt.block_signals(self.spring_tree):
            self.spring_tree.clearSelection()
            for spring in springs:
                item = self._items.get(spring)
                if item:
                    item.setSelected(True)
        self.update_params_panel()

    def on_tree_selection_changed(self):
        """Select the controls of the springs selected in the list."""
        controls = []
        for spring in self.selected_springs():
            if spring.exists():
                controls.extend(spring.controls)
        if controls:
            cmds.select(controls, replace=True)
        else:
            cmds.select(clear=True)
        self._pushed_selection = cmds.ls(selection=True, long=True)
        self.update_params_panel()

    def select_all_controls(self):
        """Select the controls of every spring."""
        controls = []
        for spring in registry.list_springs(previous=list(self._items)):
            controls.extend(spring.controls)
        cmds.select(controls, replace=True)

    def _tree_menu(self, position):
        menu = QtWidgets.QMenu(self)
        springs = self.selected_springs()
        select_rig = menu.addAction("Select Rig Nodes")
        enable = menu.addAction("Enable")
        disable = menu.addAction("Disable")
        menu.addSeparator()
        menu.addAction(self.bake_selected_action)
        menu.addAction(self.delete_selected_action)
        menu.addSeparator()
        menu.addAction(self.refresh_action)
        for action in (select_rig, enable, disable):
            action.setEnabled(bool(springs))
        select_rig.triggered.connect(self.select_rig_nodes)
        enable.triggered.connect(partial(self.set_enabled, True))
        disable.triggered.connect(partial(self.set_enabled, False))
        groups = OrderedDict()
        for spring, backend in editable_springs(springs):
            groups.setdefault(backend.name, []).append(spring)
        for name, group in groups.items():
            builder = ui_panels.SPRING_MENUS.get(name)
            if builder:
                builder(menu, group, self.update_params_panel)
        menu.exec_(self.spring_tree.viewport().mapToGlobal(position))
        menu.deleteLater()

    def select_rig_nodes(self):
        """Select the nodes created by the selected springs."""
        nodes = []
        for spring in self.selected_springs():
            if spring.exists():
                nodes.extend(
                    node
                    for node in spring.members
                    if cmds.objectType(node, isAType="dagNode")
                )
        if nodes:
            cmds.select(nodes, replace=True)

    def set_enabled(self, enabled):
        """Turn the selected springs on or off.

        Args:
            enabled (bool): True to turn them on.
        """
        groups = OrderedDict()
        for spring, backend in editable_springs(self.selected_springs()):
            groups.setdefault(backend, []).append(spring)
        with utils.undo_chunk("springManagerSetEnabled"):
            for backend, springs in groups.items():
                backend.set_enabled(springs, enabled)
        self.update_params_panel()

    # -----------------------------------------------------------------
    # Parameters panel
    # -----------------------------------------------------------------
    def _target_springs(self, editable=None):
        """Return the springs edited by the parameter panel.

        Args:
            editable (list, optional): ``(spring, backend)`` pairs of the
                selected editable springs, read from the list when None.

        Returns:
            list: Selected editable springs of the panel backend.
        """
        if editable is None:
            editable = editable_springs(self.selected_springs())
        return [
            spring for spring, backend in editable if backend is self._panel_backend
        ]

    def update_params_panel(self):
        """Rebuild or refresh the parameter rows for the selection."""
        if self.closed:
            return
        selected = self.selected_springs()
        editable = editable_springs(selected)
        backend = editable[0][1] if editable else self.current_backend()
        if backend is not self._panel_backend:
            self._build_param_rows(backend)
        springs = self._target_springs(editable)
        values = [backend.get_params(spring) for spring in springs]

        read_only = bool(selected) and not springs
        if read_only:
            selected_backend = get_backend(selected[0].backend)
            self.params_status.setText(
                (selected_backend and selected_backend.read_only_message)
                or "The selected springs can't be edited."
            )
        elif springs:
            status = ["Editing {} spring(s).".format(len(springs))]
            status.extend(backend.param_warnings(springs, values))
            self.params_status.setText(" ".join(status))
        else:
            self.params_status.setText(
                "Values for new springs (select springs to edit them)"
            )
        for widget in self.param_widgets.values():
            widget.setEnabled(not read_only)
        self.key_btn.setEnabled(bool(springs))

        if springs:
            for attr, widget in self.param_widgets.items():
                current = [v[attr] for v in values if attr in v]
                if not current:
                    continue
                widget.setValue(current[0])
                if not values_differ(current):
                    continue
                if isinstance(current[0], tuple):
                    # vectors: mixed per component
                    widget.setMixed(
                        [
                            values_differ([value[i] for value in current])
                            for i in range(len(current[0]))
                        ]
                    )
                else:
                    widget.setMixed(True)
        elif backend:
            new_values = self._backend_new_values(backend)
            for attr, widget in self.param_widgets.items():
                widget.setValue(new_values[attr])

    def _build_param_rows(self, backend):
        """Create the parameter rows of a backend, grouped.

        Args:
            backend (SpringBackend): The backend, or None.
        """
        pyqt.clear_layout(self.params_layout)
        self.param_widgets = {}
        self._panel_backend = backend
        if not backend:
            return
        specs = [spec for spec in backend.param_specs() if spec.kind in PARAM_WIDGETS]
        metrics = self.fontMetrics()
        label_width = max(
            [pyqt.text_width(metrics, spec.label) for spec in specs] or [0]
        ) + pyqt.dpi_scale(8)
        forms = OrderedDict()
        for spec in specs:
            if spec.group not in forms:
                box = QtWidgets.QGroupBox(spec.group)
                form = QtWidgets.QFormLayout(box)
                form.setContentsMargins(4, 4, 4, 4)
                form.setSpacing(2)
                forms[spec.group] = form
                self.params_layout.addWidget(box)
            widget = PARAM_WIDGETS[spec.kind](spec)
            if hasattr(widget, "sliderPressed"):
                widget.sliderPressed.connect(
                    partial(self._on_param_drag_start, spec.attr)
                )
                widget.valueChanged.connect(partial(self._on_param_changed, spec.attr))
            widget.valueCommitted.connect(partial(self._on_param_committed, spec.attr))
            label = QtWidgets.QLabel(spec.label)
            label.setMinimumWidth(label_width)
            if spec.tooltip:
                tooltip = param_tooltip(spec)
                label.setToolTip(tooltip)
                widget.setToolTip(tooltip)
            forms[spec.group].addRow(label, widget)
            self.param_widgets[spec.attr] = widget

    def _on_param_drag_start(self, attr):
        """Remember the plugs and values before a slider drag.

        Args:
            attr (str): Parameter attribute.
        """
        backend = self._panel_backend
        self._drag_start = {}
        for spring in self._target_springs():
            plug = backend.param_plugs(spring).get(attr)
            if plug:
                self._drag_start[plug] = cmds.getAttr(plug)

    def _on_param_changed(self, attr, value):
        """Preview a slider drag live, without undo.

        Args:
            attr (str): Parameter attribute.
            value (float): New value.
        """
        if not self._drag_start or not self.param_widgets[attr].slider.isSliderDown():
            return
        with utils.undo_disabled():
            for plug in self._drag_start:
                cmds.setAttr(plug, value)

    def _on_param_committed(self, attr, value):
        """Apply an edit in one undo step, or store it for new springs.

        Args:
            attr (str): Parameter attribute.
            value (object): New value.
        """
        springs = self._target_springs()
        backend = self._panel_backend
        if not springs:
            self._new_values.setdefault(backend.name, {})[attr] = value
            self.save_json_setting(NEW_VALUES_KEY, self._new_values)
            return
        # undo must restore the value from before the drag
        with utils.undo_disabled():
            for plug, start in self._drag_start.items():
                cmds.setAttr(plug, start)
        self._drag_start = {}
        backend.set_params(springs, {attr: value})

    def reset_params(self):
        """Reset the parameters of the selected springs, or the new values."""
        backend = self._panel_backend
        if not backend:
            return
        springs = self._target_springs()
        if springs:
            backend.set_params(springs, backend.default_params())
        else:
            self._new_values.pop(backend.name, None)
            self.save_json_setting(NEW_VALUES_KEY, self._new_values)
        self.update_params_panel()

    def key_params(self):
        """Key every keyable parameter of the selected springs."""
        backend = self._panel_backend
        keyable = {spec.attr for spec in backend.param_specs() if spec.keyable}
        plugs = []
        for spring in self._target_springs():
            plugs.extend(
                plug
                for attr, plug in backend.param_plugs(spring).items()
                if attr in keyable
            )
        if plugs:
            cmds.setKeyframe(plugs)

    def _backend_new_values(self, backend):
        """Return the values for new springs of a backend.

        Args:
            backend (SpringBackend): The backend.

        Returns:
            dict: ``{attr: value}``, defaults for unset parameters.
        """
        values = backend.default_params()
        stored = self._new_values.get(backend.name) or {}
        values.update({key: value for key, value in stored.items() if key in values})
        return values

    # -----------------------------------------------------------------
    # Bake and delete
    # -----------------------------------------------------------------
    def bake_selected(self):
        """Bake the selected springs, asking for the options."""
        self._bake(self.selected_springs())

    def bake_all(self):
        """Bake every spring, asking for the options."""
        self._bake(list(self._items))

    def _bake(self, springs):
        count = sum(
            1
            for spring in springs
            if spring.exists() and spring.state != constants.STATE_BAKED
        )
        if not count:
            cmds.warning("No springs to bake")
            return
        dialog = BakeDialog(count, self)
        if not dialog.exec_():
            return
        bake.bake(springs, **dialog.options())
        self.scene_changed()

    def delete_selected(self):
        """Delete the selected springs, giving the animation back."""
        springs = self.selected_springs()
        if not springs:
            cmds.warning("Select the springs to delete")
            return
        bake.delete(springs)
        self.scene_changed()

    def delete_all(self):
        """Delete every spring after confirmation."""
        springs = registry.list_springs(previous=list(self._items))
        if not springs:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Delete All Springs",
            "Delete {} spring(s)? The animation is given back to the "
            "controls.".format(len(springs)),
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        bake.delete(springs)
        self.scene_changed()

    # -----------------------------------------------------------------
    # Preset libraries
    # -----------------------------------------------------------------
    def _load_libraries(self):
        """Fill the library combo: Factory, User and custom folders."""
        custom = self.load_json_setting(constants.CUSTOM_LIBRARIES_KEY, [])
        self._libraries = [
            Library("Factory", presets.factory_folder(), read_only=True),
            Library("User", presets.user_folder()),
        ]
        self._libraries += [
            Library(path, path) for path in custom if isinstance(path, str)
        ]
        current = self.settings.value(LIBRARY_KEY)
        with pyqt.block_signals(self.library_combo):
            self.library_combo.clear()
            for library in self._libraries:
                self.library_combo.addItem(library.label, library.folder)
                self.library_combo.setItemData(
                    self.library_combo.count() - 1,
                    library.folder,
                    QtCore.Qt.ToolTipRole,
                )
            index = self.library_combo.findData(current)
            self.library_combo.setCurrentIndex(max(index, 0))
        self.refresh_presets()

    def _save_custom_libraries(self):
        self.save_json_setting(
            constants.CUSTOM_LIBRARIES_KEY,
            [library.folder for library in self._libraries[BUILTIN_LIBRARY_COUNT:]],
        )

    def current_library(self):
        """Return the current library.

        Returns:
            Library: The library.
        """
        return self._libraries[max(self.library_combo.currentIndex(), 0)]

    def on_library_changed(self, *args):
        """Remember the current library and list its presets."""
        self.settings.setValue(LIBRARY_KEY, self.current_library().folder)
        self.refresh_presets()

    def _load_preset(self, path):
        """Return a preset, cached until the file changes.

        Args:
            path (str): Preset file path.

        Returns:
            dict: The preset, or None when it can not be read.
        """
        try:
            stamp = os.path.getmtime(path)
        except OSError:
            return None
        cached = self._preset_cache.get(path)
        if cached and cached[0] == stamp:
            return cached[1]
        try:
            preset = presets.read(path)
        except (IOError, OSError, ValueError) as error:
            mgear.log(str(error), mgear.sev_warning)
            preset = None
        self._preset_cache[path] = (stamp, preset)
        return preset

    def _preset_icon(self, path, preset_type):
        """Return the icon of a preset, cached until its thumbnail changes.

        Args:
            path (str): Preset file path.
            preset_type (str): Preset type, for the placeholder badge.

        Returns:
            QtGui.QIcon: The thumbnail, or the type badge.
        """
        thumbnail = presets.thumbnail_path(path)
        try:
            stamp = os.path.getmtime(thumbnail)
        except OSError:
            return type_badge(preset_type)
        cached = self._icon_cache.get(thumbnail)
        if cached and cached[0] == stamp:
            return cached[1]
        pixmap = QtGui.QPixmap(thumbnail)
        icon = QtGui.QIcon(pixmap) if not pixmap.isNull() else type_badge(preset_type)
        self._icon_cache[thumbnail] = (stamp, icon)
        return icon

    def refresh_presets(self, *args):
        """List the presets of the current library."""
        library = self.current_library()
        solver_name = self.solver_combo.currentData()
        items = []
        for name, path in presets.list_presets(library.folder):
            preset = self._load_preset(path)
            if preset is None or solver_name not in presets.preset_backends(preset):
                continue
            preset_type = presets.preset_type(preset)
            item = QtGui.QStandardItem(self._preset_icon(path, preset_type), name)
            item.setData(path, PRESET_PATH_ROLE)
            item.setToolTip(
                "{} ({})\n{}".format(
                    name, TYPE_LABELS[preset_type], presets.describe(preset)
                )
            )
            items.append(item)
        self.preset_model.clear()
        for item in items:
            self.preset_model.appendRow(item)
        self.save_btn.setEnabled(not library.read_only)
        self.save_preset_action.setEnabled(not library.read_only)
        self.remove_library_action.setEnabled(
            self.library_combo.currentIndex() >= BUILTIN_LIBRARY_COUNT
        )
        self.update_preset_details()

    def set_grid_view(self, grid):
        """Show the presets as a thumbnail grid or as a list.

        Args:
            grid (bool): True for the grid.
        """
        view = self.preset_view
        if grid:
            size = pyqt.dpi_scale(GRID_ICON_SIZE)
            view.setViewMode(QtWidgets.QListView.IconMode)
            view.setIconSize(QtCore.QSize(size, size))
            view.setGridSize(QtCore.QSize(size + 16, size + 28))
            view.setWordWrap(True)
            view.setMovement(QtWidgets.QListView.Static)
        else:
            size = pyqt.dpi_scale(LIST_ICON_SIZE)
            view.setViewMode(QtWidgets.QListView.ListMode)
            view.setIconSize(QtCore.QSize(size, size))
            view.setGridSize(QtCore.QSize())
            view.setWordWrap(False)

    def update_preset_details(self, *args):
        """Show the thumbnail, type and description of the current preset."""
        paths = self.selected_preset_paths()
        preset = self._load_preset(paths[0]) if len(paths) == 1 else None
        self.detail_widget.setVisible(bool(preset))
        if not preset:
            return
        preset_type = presets.preset_type(preset)
        size = pyqt.dpi_scale(LIST_ICON_SIZE * 2)
        self.detail_icon.setPixmap(
            self._preset_icon(paths[0], preset_type).pixmap(size, size)
        )
        self.detail_title.setText(
            "<b>{}</b> &nbsp;<span style='color:{}'>{} preset</span>".format(
                presets.preset_name(paths[0]),
                TYPE_COLORS[preset_type].name(),
                TYPE_LABELS[preset_type],
            )
        )
        self.detail_text.setText(presets.describe(preset))

    def add_library(self):
        """Add a custom library folder."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Add Spring Preset Library"
        )
        if not folder:
            return
        folder = os.path.normpath(folder)
        if folder not in [library.folder for library in self._libraries]:
            self._libraries.append(Library(folder, folder))
            self._save_custom_libraries()
            self.library_combo.addItem(folder, folder)
        self.library_combo.setCurrentIndex(self.library_combo.findData(folder))

    def remove_library(self):
        """Remove the current custom library folder from the list."""
        index = self.library_combo.currentIndex()
        if index < BUILTIN_LIBRARY_COUNT:
            return
        del self._libraries[index]
        self._save_custom_libraries()
        self.library_combo.removeItem(index)

    def reveal_library(self):
        """Open the current library folder in the file browser."""
        folder = self.current_library().folder
        if not os.path.isdir(folder):
            cmds.warning("The library folder does not exist yet: " + folder)
            return
        utils.reveal_in_file_browser(folder)

    # -----------------------------------------------------------------
    # Presets
    # -----------------------------------------------------------------
    def selected_preset_paths(self):
        """Return the file paths of the selected presets.

        Returns:
            list: File paths.
        """
        return [
            index.data(PRESET_PATH_ROLE)
            for index in self.preset_view.selectionModel().selectedRows()
        ]

    def _read_presets(self):
        paths = self.selected_preset_paths()
        if not paths:
            cmds.warning("Select a preset first")
            return []
        loaded = [self._load_preset(path) for path in paths]
        return [preset for preset in loaded if preset]

    def _choose_namespace(self):
        """Return the namespace to apply presets to, from the selection.

        Returns:
            str: Namespace with trailing colon, ``""`` for the root
            namespace, or None when the user cancels.
        """
        names = cmds.ls(selection=True) or []
        if not names:
            return ""
        namespace, candidates = node_remap.common_namespace(names)
        if namespace is not None:
            return namespace
        labels = [candidate or ":" for candidate in candidates]
        choice, accepted = QtWidgets.QInputDialog.getItem(
            self,
            "Choose Namespace",
            "The selection has several namespaces. Apply the preset to:",
            labels,
            0,
            False,
        )
        if not accepted:
            return None
        return "" if choice == ":" else choice

    def apply_preset(self):
        """Apply the selected presets.

        Rig presets create or update their springs, in the namespace of
        the selection. Values presets apply their values to the selected
        springs and create springs on selected controls that have none.
        """
        loaded = self._read_presets()
        if not loaded:
            return
        namespace = ""
        if any(
            presets.preset_type(preset) == constants.PRESET_RIG for preset in loaded
        ):
            namespace = self._choose_namespace()
            if namespace is None:
                return
        missing = []
        with utils.undo_chunk("springManagerApplyPreset"):
            for preset in loaded:
                if presets.preset_type(preset) == constants.PRESET_VALUES:
                    self._apply_values_preset(preset)
                else:
                    missing.extend(
                        presets.apply_by_name(
                            preset,
                            namespace,
                            apply_solver=self.apply_solver_action.isChecked(),
                        )[1]
                    )
        if missing:
            cmds.warning(
                "{} preset control(s) not found, see the script editor".format(
                    len(missing)
                )
            )
        self.scene_changed()

    def _apply_values_preset(self, preset):
        """Apply a values preset to the selection.

        Args:
            preset (dict): The preset.
        """
        selection = cmds.ls(selection=True, long=True, type="transform") or []
        owners = registry.map_nodes_to_springs(selection, self._node_map)
        springs = list(OrderedDict.fromkeys(s for s in owners.values() if s))
        presets.apply_values(preset, springs)
        free = [node for node, spring in owners.items() if not spring]
        entry = preset["springs"][0] if preset["springs"] else {}
        backend = get_backend(entry.get("backend"))
        if free and backend and backend.is_available():
            params = self._backend_new_values(backend)
            params.update(presets.entry_values(entry))
            backend.create(free, params, entry.get("options"))
        if not springs and not free:
            cmds.warning("Select springs or controls to apply the preset to")

    def apply_preset_values(self):
        """Apply only the values of the selected preset to the springs."""
        loaded = self._read_presets()
        if not loaded:
            return
        springs = self.selected_springs()
        if not springs:
            cmds.warning("Select the springs to apply the values to")
            return
        presets.apply_values(loaded[0], springs)
        self.update_params_panel()

    def _values_preset_params(self, springs):
        """Return the backend and values a values preset is saved from.

        Args:
            springs (list): Selected editable ``(spring, backend)`` pairs.

        Returns:
            tuple: ``(backend, params)``: the first selected spring, or the
            values for new springs when none is selected.
        """
        if springs:
            spring, backend = springs[0]
            return backend, backend.get_params(spring)
        backend = self._panel_backend
        return backend, self._backend_new_values(backend)

    def save_preset(self):
        """Save a values or rig preset in the current library."""
        library = self.current_library()
        if library.read_only:
            cmds.warning("The {} library is read only".format(library.label))
            return
        springs = editable_springs(self.selected_springs())
        dialog = SavePresetDialog(bool(springs), self)
        if not dialog.exec_():
            return
        path = presets.preset_path(library.folder, dialog.name())
        if os.path.exists(path):
            answer = QtWidgets.QMessageBox.question(
                self,
                "Save Spring Preset",
                "Overwrite preset '{}'?".format(dialog.name()),
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return

        if dialog.preset_type() == constants.PRESET_RIG:
            saved = presets.save(
                path, [spring for spring, _ in springs], dialog.description()
            )
        else:
            backend, params = self._values_preset_params(springs)
            saved = presets.build_values_preset(
                backend.name, params, dialog.description()
            )
            presets.write(path, saved)
        if not saved:
            return
        self._write_thumbnail(path, dialog.thumbnail.image())
        self.refresh_presets()

    def _write_thumbnail(self, path, image):
        """Save or remove the thumbnail of a preset.

        Args:
            path (str): Preset file path.
            image (QtGui.QImage): The thumbnail, None to remove it.
        """
        thumbnail = presets.thumbnail_path(path)
        if image is None:
            if os.path.exists(thumbnail):
                os.remove(thumbnail)
        else:
            image.save(thumbnail, "PNG")

    def rename_preset(self):
        """Rename the selected preset."""
        paths = self.selected_preset_paths()
        if len(paths) != 1 or self.current_library().read_only:
            return
        old_name = presets.preset_name(paths[0])
        name, accepted = QtWidgets.QInputDialog.getText(
            self, "Rename Spring Preset", "Preset name:", text=old_name
        )
        name = name.strip() if accepted else ""
        if not name or name == old_name:
            return
        try:
            presets.rename(paths[0], name)
        except OSError as error:
            cmds.warning(str(error))
            return
        self.refresh_presets()

    def edit_preset_description(self):
        """Edit the description of the selected preset."""
        paths = self.selected_preset_paths()
        if len(paths) != 1 or self.current_library().read_only:
            return
        preset = self._load_preset(paths[0]) or {}
        text, accepted = QtWidgets.QInputDialog.getMultiLineText(
            self,
            "Preset Description",
            "Description:",
            preset.get("description") or "",
        )
        if accepted:
            presets.set_description(paths[0], text.strip())
            self.refresh_presets()

    def update_preset_thumbnail(self, region=False):
        """Replace the thumbnail of the selected preset.

        Args:
            region (bool, optional): Capture a screen region instead of the
                active viewport.
        """
        paths = self.selected_preset_paths()
        if len(paths) != 1 or self.current_library().read_only:
            return
        if region:
            image = screen_capture.capture_screen_region(hide_widgets=[self.window()])
        else:
            image = pyqt.capture_active_view_image()
        image = pyqt.square_crop_image(image, constants.THUMBNAIL_SIZE)
        if image is None:
            return
        self._write_thumbnail(paths[0], image)
        self.refresh_presets()

    def delete_presets(self):
        """Delete the selected presets after confirmation."""
        paths = self.selected_preset_paths()
        if not paths or self.current_library().read_only:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Delete Spring Presets",
            "Delete these presets?\n{}".format(
                "\n".join(presets.preset_name(path) for path in paths)
            ),
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        for path in paths:
            presets.remove(path)
        self.refresh_presets()

    def select_preset_controls(self):
        """Select the scene controls stored in the selected rig presets."""
        namespace = self._choose_namespace()
        if namespace is None:
            return
        controls = []
        for preset in self._read_presets():
            for entry in preset["springs"]:
                controls.extend(
                    name
                    for name in presets.resolve_controls(entry, namespace)
                    if cmds.objExists(name)
                )
        if controls:
            cmds.select(controls, replace=True)
        else:
            cmds.warning("None of the preset controls exist in the scene")

    def _reveal_selected_preset(self):
        paths = self.selected_preset_paths()
        if paths:
            utils.reveal_in_file_browser(paths[0])

    def _preset_menu(self, position):
        menu = QtWidgets.QMenu(self)
        paths = self.selected_preset_paths()
        single = len(paths) == 1
        read_only = self.current_library().read_only
        editable = single and not read_only
        rig = single and any(
            presets.preset_type(preset) == constants.PRESET_RIG
            for preset in self._read_presets()
        )
        apply_action = menu.addAction("Apply")
        values_action = menu.addAction("Apply Values to Selected")
        select_action = menu.addAction("Select Preset Controls")
        menu.addSeparator()
        description_action = menu.addAction("Edit Description...")
        viewport_action = menu.addAction("Thumbnail from Viewport")
        region_action = menu.addAction("Thumbnail from Screen Region...")
        menu.addSeparator()
        rename_action = menu.addAction("Rename...")
        delete_action = menu.addAction("Delete")
        reveal_action = menu.addAction("Reveal in File Browser")
        for action in (apply_action, values_action):
            action.setEnabled(bool(paths))
        select_action.setEnabled(rig)
        for action in (description_action, viewport_action, region_action):
            action.setEnabled(editable)
        rename_action.setEnabled(editable)
        delete_action.setEnabled(bool(paths) and not read_only)
        reveal_action.setEnabled(single)
        apply_action.triggered.connect(self.apply_preset)
        values_action.triggered.connect(self.apply_preset_values)
        select_action.triggered.connect(self.select_preset_controls)
        description_action.triggered.connect(self.edit_preset_description)
        viewport_action.triggered.connect(partial(self.update_preset_thumbnail, False))
        region_action.triggered.connect(partial(self.update_preset_thumbnail, True))
        rename_action.triggered.connect(self.rename_preset)
        delete_action.triggered.connect(self.delete_presets)
        reveal_action.triggered.connect(self._reveal_selected_preset)
        menu.exec_(self.preset_view.viewport().mapToGlobal(position))
        menu.deleteLater()

    # -----------------------------------------------------------------
    # Window lifecycle
    # -----------------------------------------------------------------
    def shutdown(self):
        """Remove the callbacks and save the settings (once)."""
        if self.closed:
            return
        self.closed = True
        self.callbacks.removeAllManagedCB()
        self.save_settings()

    def closeEvent(self, event):
        """Handle the floating-window close.

        Args:
            event (QtGui.QCloseEvent): The close event.
        """
        self.shutdown()
        super(SpringManager, self).closeEvent(event)

    def dockCloseEventTriggered(self):
        """Handle the docked workspace-control close."""
        self.shutdown()


def open_spring_manager(*args):
    """Show the dockable Spring Manager, replacing an open one.

    Returns:
        SpringManager: The window instance.
    """
    return pyqt.showDialog(SpringManager, dockable=True)


# backwards compatible entry point
openSpringManagerManager = open_spring_manager
