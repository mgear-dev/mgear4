"""Per-solver panels of the Spring Manager window.

Backends stay Qt free. Each backend can register here a create panel,
shown in the Create section, and a solver panel, shown in the Solver
section when the backend is the current solver.

Panels are QWidgets with a ``createRequested(dict)`` signal (create
panels) and a ``refresh()`` method called when the scene changes.
"""

from functools import partial

from maya import cmds

from mgear.core import anim_utils
from mgear.core import pyqt
from mgear.core import utils
from mgear.core import widgets

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from . import chain
from . import solver
from .backends import bone_dynamics
from .backends import classic
from .backends import get_backend

CREATE_PANELS = {}
SOLVER_PANELS = {}
# backend name: builder(menu, springs, refresh) adding spring menu actions
SPRING_MENUS = {}

WARNING_COLOR = QtGui.QColor(230, 160, 60)
WARNING_STYLE = "color: rgb(230, 160, 60);"


def register_create_panel(backend_name, panel_class):
    """Register the create panel class of a backend.

    Args:
        backend_name (str): Backend name.
        panel_class (type): QWidget subclass with ``createRequested``.
    """
    CREATE_PANELS[backend_name] = panel_class


def register_spring_menu(backend_name, builder):
    """Register the spring context menu actions of a backend.

    Args:
        backend_name (str): Backend name.
        builder (callable): ``builder(menu, springs, refresh)`` adds
            actions for the selected springs of that backend; ``refresh``
            updates the window after an edit.
    """
    SPRING_MENUS[backend_name] = builder


def register_solver_panel(backend_name, panel_class):
    """Register the solver panel class of a backend.

    Args:
        backend_name (str): Backend name.
        panel_class (type): QWidget subclass with ``refresh()``.
    """
    SOLVER_PANELS[backend_name] = panel_class


class CreatePanel(QtWidgets.QWidget):
    """Base create panel: emits ``createRequested(options)``."""

    createRequested = QtCore.Signal(dict)

    def options(self):
        """Return the create options.

        Returns:
            dict: Backend create options.
        """
        return {}

    def refresh(self):
        """Update the panel after a scene change."""

    def _on_create(self, *args):
        self.createRequested.emit(self.options())


class DefaultCreatePanel(CreatePanel):
    """A single "Create from Selection" button."""

    def __init__(self, parent=None):
        super(DefaultCreatePanel, self).__init__(parent)
        self.create_btn = QtWidgets.QPushButton("Create from Selection")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.create_btn)
        self.create_btn.clicked.connect(self._on_create)


class ClassicCreatePanel(CreatePanel):
    """Direction buttons of the classic solver."""

    def __init__(self, parent=None):
        super(ClassicCreatePanel, self).__init__(parent)
        self.direction_buttons = {}
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)
        directions = classic.DIRECTIONS + (classic.AUTO_DIRECTION,)
        for index, direction in enumerate(directions):
            auto = direction == classic.AUTO_DIRECTION
            button = QtWidgets.QPushButton("Auto" if auto else direction.upper())
            button.setToolTip(
                "Create springs on the selected controls, aiming along "
                "{}".format(
                    "the chain (child or parent direction)" if auto else direction
                )
            )
            button.clicked.connect(partial(self._on_create, direction))
            self.direction_buttons[direction] = button
            if auto:
                grid.addWidget(button, 2, 0, 1, 3)
            else:
                grid.addWidget(button, index // 3, index % 3)

    def _on_create(self, direction, *args):
        self.createRequested.emit({"direction": direction})


register_create_panel(classic.CLASSIC_BACKEND, ClassicCreatePanel)


# -----------------------------------------------------------------------------
# Bone Dynamics
# -----------------------------------------------------------------------------

TARGET_MODE_LABELS = (
    (bone_dynamics.TARGET_ANIMATION, "Animation"),
    (bone_dynamics.TARGET_CONTROLS, "Target Controls"),
    (bone_dynamics.TARGET_CAPTURED, "Captured Pose"),
    (bone_dynamics.TARGET_BLEND_MODE, "Blend (Pose Blend)"),
)
POLICY_LABELS = (
    (chain.KINEMATIC, "Kinematic (keep animation)"),
    (chain.AVERAGE, "Average of branches"),
    (chain.PRIMARY, "Follow primary branch"),
)
OFFSET_NONE = 1
OFFSET_PICK = 2


class BoneDynamicsCreatePanel(CreatePanel):
    """Create options of the Bone Dynamics solver."""

    def __init__(self, parent=None):
        super(BoneDynamicsCreatePanel, self).__init__(parent)
        self.target_combo = QtWidgets.QComboBox()
        for mode, label in TARGET_MODE_LABELS:
            self.target_combo.addItem(label, mode)
        self.target_combo.setToolTip(
            "Pose the chain is pulled back to (elasticity). Animation: the "
            "animated controls. Target Controls: keyable pose controls. "
            "Captured Pose: the pose at creation. Blend: Pose Blend fades "
            "from the animation to the pose."
        )
        self.policy_combo = QtWidgets.QComboBox()
        for policy, label in POLICY_LABELS:
            self.policy_combo.addItem(label, policy)
        self.policy_combo.setToolTip(
            "How a control with several child chains (e.g. a skirt root) "
            "moves: it keeps its animation, follows the average of its "
            "branches, or follows one branch."
        )
        self.primary_spin = QtWidgets.QSpinBox()
        self.primary_spin.setRange(0, 99)
        self.primary_spin.setEnabled(False)
        self.primary_spin.setToolTip("Branch followed, in child order")
        self.split_cb = QtWidgets.QCheckBox("Split branches into separate springs")
        self.split_cb.setToolTip("Each branch gets its own spring and settings")
        self.tip_spin = QtWidgets.QDoubleSpinBox()
        self.tip_spin.setRange(0.05, 10.0)
        self.tip_spin.setSingleStep(0.1)
        self.tip_spin.setValue(1.0)
        self.tip_spin.setToolTip(
            "Length of the virtual tip after the last control, relative to "
            "the last bone, when the control has no child transform"
        )
        self.offset_combo = QtWidgets.QComboBox()
        self.offset_combo.addItems(("Auto (Shifter world)", "None", "Picked node"))
        self.offset_combo.setToolTip(
            "Node whose motion is cancelled from the simulation (character "
            "root), so fast moves do not drag the chains"
        )
        self.offset_le = QtWidgets.QLineEdit()
        self.offset_le.setPlaceholderText("Root motion node")
        self.offset_le.setEnabled(False)
        self.offset_btn = QtWidgets.QPushButton("<")
        self.offset_btn.setToolTip("Use the selected node")
        self.offset_btn.setEnabled(False)
        self.visualizer_cb = QtWidgets.QCheckBox("Visualizer")
        self.create_btn = QtWidgets.QPushButton("Create Chain from Selection")
        self.create_btn.setToolTip(
            "Select the root control of each chain: its child controls are "
            "found automatically"
        )

        policy_layout = QtWidgets.QHBoxLayout()
        policy_layout.addWidget(self.policy_combo, 1)
        policy_layout.addWidget(self.primary_spin)
        offset_layout = QtWidgets.QHBoxLayout()
        offset_layout.addWidget(self.offset_combo)
        offset_layout.addWidget(self.offset_le, 1)
        offset_layout.addWidget(self.offset_btn)
        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Target pose", self.target_combo)
        form.addRow("Branch root", policy_layout)
        form.addRow("", self.split_cb)
        form.addRow("Tip length", self.tip_spin)
        form.addRow("Root motion", offset_layout)
        form.addRow("", self.visualizer_cb)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addWidget(self.create_btn)

        self.policy_combo.currentIndexChanged.connect(self._update_enabled)
        self.offset_combo.currentIndexChanged.connect(self._update_enabled)
        self.offset_btn.clicked.connect(self._pick_offset)
        self.create_btn.clicked.connect(self._on_create)

    def _update_enabled(self, *args):
        self.primary_spin.setEnabled(self.policy_combo.currentData() == chain.PRIMARY)
        picked = self.offset_combo.currentIndex() == OFFSET_PICK
        self.offset_le.setEnabled(picked)
        self.offset_btn.setEnabled(picked)

    def _pick_offset(self):
        selection = cmds.ls(selection=True)
        if selection:
            self.offset_le.setText(selection[0])

    def options(self):
        """Return the create options.

        Returns:
            dict: Options of :meth:`BoneDynamicsBackend.create`.
        """
        offset = bone_dynamics.AUTO_OFFSET
        if self.offset_combo.currentIndex() == OFFSET_NONE:
            offset = None
        elif self.offset_combo.currentIndex() == OFFSET_PICK:
            offset = self.offset_le.text().strip() or None
        return {
            "target_mode": self.target_combo.currentData(),
            "branch_policy": self.policy_combo.currentData(),
            "primary": self.primary_spin.value(),
            "split": self.split_cb.isChecked(),
            "tip_length": self.tip_spin.value(),
            "offset": offset,
            "visualizer": self.visualizer_cb.isChecked(),
        }


class BoneDynamicsSolverPanel(QtWidgets.QWidget):
    """Scene solver settings, wind and visualizer of Bone Dynamics.

    Attributes:
        springs_fn (callable): Returns the springs selected in the window.
        all_springs_fn (callable): Returns every spring of the window.
    """

    def __init__(self, parent=None):
        super(BoneDynamicsSolverPanel, self).__init__(parent)
        self.springs_fn = None
        self.all_springs_fn = None
        self._backend = get_backend(bone_dynamics.BACKEND)

        self.playback_label = QtWidgets.QLabel(
            "Playback is not set to play every frame: the simulation needs "
            "every frame in order."
        )
        self.playback_label.setWordWrap(True)
        self.playback_label.setStyleSheet(WARNING_STYLE)
        self.playback_btn = QtWidgets.QPushButton("Fix")
        self.playback_widget = QtWidgets.QWidget()
        banner = QtWidgets.QHBoxLayout(self.playback_widget)
        banner.setContentsMargins(0, 0, 0, 0)
        banner.addWidget(self.playback_label, 1)
        banner.addWidget(self.playback_btn)

        self.enable_cb = widgets.TriStateCheckBox("Enabled")
        self.start_spin = QtWidgets.QDoubleSpinBox()
        self.start_spin.setDecimals(0)
        self.start_spin.setRange(-100000, 100000)
        self.start_spin.setKeyboardTracking(False)
        self.start_spin.setToolTip("Frame where the simulation starts (resets)")
        self.gravity = widgets.VectorSpinBox(decimals=1)
        self.gravity.setToolTip(
            "Gravity vector, in scene units. Each spring scales it with its "
            "Gravity parameter."
        )
        self.ground_cb = widgets.TriStateCheckBox("Ground")
        self.ground_spin = QtWidgets.QDoubleSpinBox()
        self.ground_spin.setRange(-100000, 100000)
        self.ground_spin.setKeyboardTracking(False)
        self.iterations_spin = QtWidgets.QSpinBox()
        self.iterations_spin.setRange(0, 10)
        self.iterations_spin.setKeyboardTracking(False)
        self.iterations_spin.setToolTip("Collision iterations, 0 turns collisions off")

        self.wind_combo = QtWidgets.QComboBox()
        self.create_wind_btn = QtWidgets.QPushButton("Create Wind")
        self.connect_wind_btn = QtWidgets.QPushButton("Connect")
        self.connect_wind_btn.setToolTip("Connect the selected springs to the wind")
        self.disconnect_wind_btn = QtWidgets.QPushButton("Disconnect")
        self.vis_on_btn = QtWidgets.QPushButton("Visualizer On")
        self.vis_off_btn = QtWidgets.QPushButton("Visualizer Off")
        for button in (self.vis_on_btn, self.vis_off_btn):
            button.setToolTip("Selected springs, or every spring without selection")

        ground_layout = QtWidgets.QHBoxLayout()
        ground_layout.addWidget(self.ground_cb)
        ground_layout.addWidget(self.ground_spin, 1)
        wind_layout = QtWidgets.QHBoxLayout()
        wind_layout.addWidget(self.wind_combo, 1)
        wind_layout.addWidget(self.connect_wind_btn)
        wind_layout.addWidget(self.disconnect_wind_btn)
        wind_layout.addWidget(self.create_wind_btn)
        vis_layout = QtWidgets.QHBoxLayout()
        vis_layout.addWidget(self.vis_on_btn)
        vis_layout.addWidget(self.vis_off_btn)
        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("", self.enable_cb)
        form.addRow("Start frame", self.start_spin)
        form.addRow("Gravity", self.gravity)
        form.addRow("", ground_layout)
        form.addRow("Iterations", self.iterations_spin)
        form.addRow("Wind", wind_layout)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.playback_widget)
        layout.addLayout(form)
        layout.addLayout(vis_layout)

        self.playback_btn.clicked.connect(self._fix_playback)
        self.enable_cb.valueCommitted.connect(partial(self._set, solver.ENABLE))
        self.start_spin.valueChanged.connect(partial(self._set, solver.START_FRAME))
        self.gravity.valueCommitted.connect(partial(self._set, solver.GRAVITY))
        self.ground_cb.valueCommitted.connect(partial(self._set, solver.GROUND_ENABLE))
        self.ground_spin.valueChanged.connect(partial(self._set, solver.GROUND_HEIGHT))
        self.iterations_spin.valueChanged.connect(partial(self._set, solver.ITERATIONS))
        self.create_wind_btn.clicked.connect(self._create_wind)
        self.connect_wind_btn.clicked.connect(self._connect_wind)
        self.disconnect_wind_btn.clicked.connect(self._disconnect_wind)
        self.vis_on_btn.clicked.connect(partial(self._set_visualizer, True))
        self.vis_off_btn.clicked.connect(partial(self._set_visualizer, False))

    def _springs(self, all_when_empty=False):
        springs = self.springs_fn() if self.springs_fn else []
        if not springs and all_when_empty and self.all_springs_fn:
            springs = self.all_springs_fn()
        return [
            spring
            for spring in springs
            if spring.backend == bone_dynamics.BACKEND and spring.exists()
        ]

    def refresh(self):
        """Read the solver settings, winds and playback state."""
        node = solver.find_solver()
        settings = solver.get_settings(node) if node else {}
        self.enable_cb.setValue(settings.get("enable", True))
        self.ground_cb.setValue(settings.get("ground_enable", False))
        for widget, value in (
            (self.start_spin, settings.get("start_frame", 1)),
            (self.ground_spin, settings.get("ground_height", 0.0)),
            (self.iterations_spin, settings.get("iterations", 5)),
        ):
            with pyqt.block_signals(widget):
                widget.setValue(value)
        self.gravity.setValue(settings.get("gravity") or solver.default_gravity())

        with pyqt.block_signals(self.wind_combo):
            current = self.wind_combo.currentText()
            self.wind_combo.clear()
            for wind in self._backend.winds():
                self.wind_combo.addItem(wind)
            index = self.wind_combo.findText(current)
            if index >= 0:
                self.wind_combo.setCurrentIndex(index)
        has_springs = bool(self._springs(all_when_empty=True))
        self.playback_widget.setVisible(
            has_springs and not anim_utils.get_play_every_frame()
        )

    def _set(self, attr, value):
        with utils.undo_chunk("springManagerSolver"):
            solver.set_value(attr, value)

    def _fix_playback(self):
        anim_utils.set_play_every_frame(True)
        self.refresh()

    def _create_wind(self):
        wind = self._backend.create_wind()
        self.refresh()
        self.wind_combo.setCurrentIndex(self.wind_combo.findText(wind))

    def _connect_wind(self):
        wind = self.wind_combo.currentText()
        springs = self._springs()
        if not wind or not springs:
            cmds.warning("Select springs and a wind controller")
            return
        self._backend.connect_wind(springs, wind)

    def _disconnect_wind(self):
        springs = self._springs()
        if not springs:
            cmds.warning("Select the springs to disconnect from the wind")
            return
        self._backend.disconnect_wind(springs)

    def _set_visualizer(self, visible):
        self._backend.set_visualizer(self._springs(all_when_empty=True), visible)


register_create_panel(bone_dynamics.BACKEND, BoneDynamicsCreatePanel)
register_solver_panel(bone_dynamics.BACKEND, BoneDynamicsSolverPanel)


def _bone_dynamics_menu(menu, springs, refresh):
    """Add the target pose actions of Bone Dynamics springs.

    Args:
        menu (QtWidgets.QMenu): Springs context menu.
        springs (list): Selected Bone Dynamics springs.
        refresh (callable): Updates the window after an edit.
    """
    backend = get_backend(bone_dynamics.BACKEND)

    def set_mode(mode):
        backend.set_target_mode(springs, mode)
        refresh()

    def set_external():
        if len(springs) != 1:
            cmds.warning("Select the external chain nodes, then one spring control")
            return
        controls = set(cmds.ls(springs[0].controls, long=True))
        external = [
            node for node in cmds.ls(selection=True, long=True) if node not in controls
        ]
        try:
            backend.set_target_mode(springs, bone_dynamics.TARGET_EXTERNAL, external)
        except ValueError as error:
            cmds.warning(str(error))
        refresh()

    target_menu = menu.addMenu("Target Pose")
    for mode, label in TARGET_MODE_LABELS:
        target_menu.addAction(label).triggered.connect(partial(set_mode, mode))
    external = target_menu.addAction("External Chain from Selection")
    external.setToolTip(
        "Select the external nodes in order, then a control of the spring"
    )
    external.triggered.connect(set_external)
    target_menu.addSeparator()
    capture = target_menu.addAction("Capture Pose")
    capture.triggered.connect(lambda: backend.capture_pose(springs))


register_spring_menu(bone_dynamics.BACKEND, _bone_dynamics_menu)
