"""Per-solver panels of the Spring Manager window.

Backends stay Qt free. Each backend can register here a create panel,
shown in the Create section, a solver panel, shown in the Solver section,
and extra section panels (e.g. Colliders), each in its own section. They
are shown when the backend is the current solver.

Panels are QWidgets with a ``createRequested(dict)`` signal (create
panels) and a ``refresh()`` method called when the scene changes.
"""

import re
from functools import partial

from maya import cmds

from mgear.core import anim_utils
from mgear.core import attribute
from mgear.core import pyqt
from mgear.core import utils
from mgear.core import widgets

from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui
from mgear.vendor.Qt import QtWidgets

from . import chain
from . import colliders
from . import constants
from . import fit
from . import registry
from . import solver
from .backends import bone_dynamics
from .backends import classic
from .backends import classic_gravity
from .backends import get_backend

CREATE_PANELS = {}
SOLVER_PANELS = {}
# backend name: [(section title, panel class), ...]
SECTION_PANELS = {}
# backend name: builder(menu, springs, refresh) adding spring menu actions
SPRING_MENUS = {}

WARNING_COLOR = QtGui.QColor(230, 160, 60)
COLLIDERS_HEIGHT_KEY = constants.SETTINGS_PREFIX + "colliders_height"
ASSIGN_HEIGHT_KEY = constants.SETTINGS_PREFIX + "assign_height"
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


def register_section_panel(backend_name, title, panel_class):
    """Register an extra section panel of a backend.

    The panel gets the ``springs_fn`` and ``all_springs_fn`` attributes,
    like solver panels, and its ``refresh()`` is called when the scene
    changes.

    Args:
        backend_name (str): Backend name.
        title (str): Section title.
        panel_class (type): QWidget subclass with ``refresh()``.
    """
    SECTION_PANELS.setdefault(backend_name, []).append((title, panel_class))


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
# same rig as Classic: the same direction buttons
register_create_panel(classic_gravity.CLASSIC_GRAVITY_BACKEND, ClassicCreatePanel)


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
        self.pick_ground_btn = QtWidgets.QPushButton("Pick")
        self.pick_ground_btn.setToolTip(
            "Set the ground height from the lowest point of the selected "
            "objects or vertices"
        )

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
        ground_layout.addWidget(self.pick_ground_btn)
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
        self.pick_ground_btn.clicked.connect(self._pick_ground)
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

    def _pick_ground(self):
        if solver.pick_ground_height() is None:
            cmds.warning("Select the ground objects or vertices")
        self.refresh()

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


# -----------------------------------------------------------------------------
# Colliders
# -----------------------------------------------------------------------------

FIT_METHOD_LABELS = (
    (fit.AUTO, "Auto"),
    (fit.SKIN, "Skin Weights"),
    (fit.RAYCAST, "Ray Cast"),
)
COLLIDER_ROLE = QtCore.Qt.UserRole + 1


def _matcher(text):
    """Return a case-insensitive wildcard test for a filter text.

    Args:
        text (str): Filter text, ``*`` and ``?`` wildcards.

    Returns:
        callable: ``match(name)`` returning True, always for an empty text.
    """
    text = text.strip()
    if not text:
        return lambda name: True
    pattern = re.compile(pyqt.wildcard_to_regex(text), re.IGNORECASE)
    return lambda name: bool(pattern.search(name))


def _is_mesh(node):
    return bool(cmds.listRelatives(node, shapes=True, type="mesh", noIntermediate=True))


def _selected_meshes():
    """Return the selected mesh transforms, in selection order."""
    return [
        node
        for node in cmds.ls(selection=True, long=True, transforms=True)
        if _is_mesh(node)
    ]


class CollidersPanel(QtWidgets.QWidget):
    """Create, fit, mirror and assign the colliders of a solver's springs.

    Actions the solver can't use (or that need the boneDynamicsNode
    plug-in) are disabled, with a tooltip saying why.

    Attributes:
        springs_fn (callable): Returns the springs selected in the window.
        all_springs_fn (callable): Returns every spring of the window.
    """

    def __init__(self, backend_name=bone_dynamics.BACKEND, parent=None):
        """Initialize the panel.

        Args:
            backend_name (str, optional): The solver whose springs are
                listed in the assignment table.
            parent (QtWidgets.QWidget, optional): Parent widget.
        """
        super(CollidersPanel, self).__init__(parent)
        self.springs_fn = None
        self.all_springs_fn = None
        self._backend_name = backend_name
        self._solver = get_backend(backend_name)
        # the Bone Dynamics backend: sim joints of spring controls, fit radius
        self._backend = get_backend(bone_dynamics.BACKEND)
        # action widget: its tooltip when enabled, see _update_actions
        self._tooltips = {}
        self._springs = []
        self._colliders = []
        # settings key: (widget, default), saved by the window
        self.user_settings = {}

        # create
        self.create_buttons = {}
        for kind_type, label, tooltip in (
            (colliders.SPHERE, "Sphere", "A sphere on each selected joint or control"),
            (
                colliders.CAPSULE,
                "Capsule",
                "A capsule on each selected joint or control",
            ),
            (
                colliders.PLANE,
                "Plane",
                "An infinite plane on each selected joint or control (its XZ plane collides)",
            ),
            (
                colliders.MESH,
                "Mesh",
                "Experimental: collide with each selected mesh. Slow on dense "
                "meshes: a proxy is recommended",
            ),
        ):
            button = QtWidgets.QPushButton(label)
            button.setToolTip(tooltip)
            self.create_buttons[kind_type] = button
        self.proxy_cb = QtWidgets.QCheckBox("Proxy")
        self.proxy_cb.setChecked(True)
        self.proxy_cb.setToolTip(
            "Mesh colliders use a reduced, soft-edged copy following the mesh"
        )
        self.reduce_spin = QtWidgets.QSpinBox()
        self.reduce_spin.setRange(0, 99)
        self.reduce_spin.setValue(int(colliders.PROXY_REDUCE))
        self.reduce_spin.setSuffix(" %")
        self.reduce_spin.setToolTip("Faces removed from the proxy")

        # fit: the mesh from the field, or the last selected mesh
        self.fit_mesh_le = QtWidgets.QLineEdit()
        self.fit_mesh_le.setPlaceholderText("Last selected mesh")
        self.fit_mesh_le.setClearButtonEnabled(True)
        self.fit_mesh_le.setToolTip(
            "Mesh measured by the fit tools. Empty: the last selected mesh"
        )
        self.fit_mesh_btn = QtWidgets.QPushButton("<")
        self.fit_mesh_btn.setToolTip("Use the selected mesh")
        self.fit_capsules_btn = QtWidgets.QPushButton("Fit Capsules")
        self.fit_capsules_btn.setToolTip(
            "Body colliders: select the joints or controls of one or more "
            "chains (spine, arms...). A capsule per bone, and a sphere at "
            "each chain end with End Spheres"
        )
        self.fit_sphere_btn = QtWidgets.QPushButton("Fit Sphere")
        self.fit_sphere_btn.setToolTip(
            "Select vertices (and optionally the driver) for one sphere, or "
            "joints or controls for a sphere at each"
        )
        self.fit_radius_btn = QtWidgets.QPushButton("Fit Bone Radius")
        self.fit_radius_btn.setToolTip(
            "Chain volume: sets Root Radius, Tip Radius and Bone As Capsule "
            "of the springs selected in the list (or by their controls) "
            "from the mesh thickness"
        )
        self.method_combo = QtWidgets.QComboBox()
        for method, label in FIT_METHOD_LABELS:
            self.method_combo.addItem(label, method)
        self.method_combo.setToolTip(
            "Skin Weights: vertices weighted to each joint. Ray Cast: any "
            "mesh. Auto: Skin Weights when the mesh is skinned to the joints"
        )
        self.padding_spin = QtWidgets.QDoubleSpinBox()
        self.padding_spin.setRange(0.1, 5.0)
        self.padding_spin.setSingleStep(0.05)
        self.padding_spin.setValue(1.0)
        self.padding_spin.setToolTip("Radius multiplier: 1.1 = 10% bigger")
        self.percentile_spin = QtWidgets.QDoubleSpinBox()
        self.percentile_spin.setRange(1, 100)
        self.percentile_spin.setDecimals(0)
        self.percentile_spin.setValue(75)
        self.percentile_spin.setToolTip(
            "Skin Weights: percentile of the vertex distances used as radius. "
            "100 encloses every vertex, 50 is the median"
        )
        self.min_radius_spin = QtWidgets.QDoubleSpinBox()
        self.min_radius_spin.setRange(0.0, 1000.0)
        self.min_radius_spin.setValue(0.1)
        self.min_radius_spin.setToolTip("Smallest radius")
        self.end_spheres_cb = QtWidgets.QCheckBox("End Spheres")
        self.end_spheres_cb.setChecked(True)
        self.end_spheres_cb.setToolTip(
            "Fit Capsules also adds a sphere at each chain end (head, hands)"
        )

        # list and assignment table
        self.collider_list = QtWidgets.QListWidget()
        self.collider_list.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection
        )
        self.collider_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.collider_filter_le = QtWidgets.QLineEdit()
        self.collider_filter_le.setPlaceholderText("Filter colliders (* wildcard)")
        self.collider_filter_le.setClearButtonEnabled(True)
        self.collider_filter_le.setToolTip(
            "Filters the colliders list and the table columns"
        )
        self.collider_grip = widgets.HeightGrip(
            self.collider_list, minimum=pyqt.dpi_scale(40)
        )
        self.collider_grip.set_target_height(pyqt.dpi_scale(90))
        self.collider_list.setToolTip("Right-click for actions")
        self.table = QtWidgets.QTableWidget()
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.spring_filter_le = QtWidgets.QLineEdit()
        self.spring_filter_le.setPlaceholderText("Filter springs (* wildcard)")
        self.spring_filter_le.setClearButtonEnabled(True)
        self.spring_filter_le.setToolTip("Filters the table rows")
        self.table_grip = widgets.HeightGrip(self.table, minimum=pyqt.dpi_scale(60))
        self.table_grip.set_target_height(pyqt.dpi_scale(140))
        self.user_settings = {
            COLLIDERS_HEIGHT_KEY: (self.collider_grip, pyqt.dpi_scale(90)),
            ASSIGN_HEIGHT_KEY: (self.table_grip, pyqt.dpi_scale(140)),
        }
        self.table.setToolTip("Check a cell to assign the collider to the spring")
        self.assign_btn = QtWidgets.QPushButton("Assign")
        self.assign_btn.setToolTip("Assign the colliders of the selected cells")
        self.unassign_btn = QtWidgets.QPushButton("Unassign")
        self.unassign_btn.setToolTip("Unassign the colliders of the selected cells")
        self.assign_all_btn = QtWidgets.QPushButton("Assign All")
        self.assign_all_btn.setToolTip("Assign every collider to every spring")

        create_layout = QtWidgets.QHBoxLayout()
        for button in self.create_buttons.values():
            create_layout.addWidget(button)
        mesh_layout = QtWidgets.QHBoxLayout()
        mesh_layout.addWidget(QtWidgets.QLabel("Mesh:"))
        mesh_layout.addWidget(self.proxy_cb)
        mesh_layout.addWidget(QtWidgets.QLabel("Reduce"))
        mesh_layout.addWidget(self.reduce_spin)
        mesh_layout.addStretch()
        fit_mesh_layout = QtWidgets.QHBoxLayout()
        fit_mesh_layout.addWidget(QtWidgets.QLabel("Fit mesh"))
        fit_mesh_layout.addWidget(self.fit_mesh_le, 1)
        fit_mesh_layout.addWidget(self.fit_mesh_btn)
        fit_layout = QtWidgets.QHBoxLayout()
        fit_layout.addWidget(self.fit_capsules_btn)
        fit_layout.addWidget(self.fit_sphere_btn)
        fit_layout.addWidget(self.fit_radius_btn)
        options = QtWidgets.QGridLayout()
        options.addWidget(QtWidgets.QLabel("Method"), 0, 0)
        options.addWidget(self.method_combo, 0, 1)
        options.addWidget(QtWidgets.QLabel("Padding"), 0, 2)
        options.addWidget(self.padding_spin, 0, 3)
        options.addWidget(QtWidgets.QLabel("Percentile"), 1, 0)
        options.addWidget(self.percentile_spin, 1, 1)
        options.addWidget(QtWidgets.QLabel("Min Radius"), 1, 2)
        options.addWidget(self.min_radius_spin, 1, 3)
        options.addWidget(self.end_spheres_cb, 2, 0, 1, 2)
        assign_layout = QtWidgets.QHBoxLayout()
        assign_layout.addWidget(self.assign_btn)
        assign_layout.addWidget(self.unassign_btn)
        assign_layout.addWidget(self.assign_all_btn)
        create_box = QtWidgets.QGroupBox("Create")
        create_box.setToolTip(
            "A collider on each selected joint or control, or one in world "
            "space without selection"
        )
        create_box_layout = QtWidgets.QVBoxLayout(create_box)
        create_box_layout.addLayout(create_layout)
        create_box_layout.addLayout(mesh_layout)
        fit_box = QtWidgets.QGroupBox("Fit")
        fit_box.setToolTip(
            "Colliders and bone volumes sized to the Fit mesh, on each "
            "selected joint or control"
        )
        fit_box_layout = QtWidgets.QVBoxLayout(fit_box)
        fit_box_layout.addLayout(fit_mesh_layout)
        fit_box_layout.addLayout(fit_layout)
        fit_box_layout.addLayout(options)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(create_box)
        layout.addWidget(fit_box)
        layout.addWidget(self.collider_filter_le)
        layout.addWidget(self.collider_list)
        layout.addWidget(self.collider_grip)
        layout.addWidget(self.spring_filter_le)
        layout.addWidget(self.table)
        layout.addWidget(self.table_grip)
        layout.addLayout(assign_layout)

        for kind_type, button in self.create_buttons.items():
            button.clicked.connect(partial(self._create, kind_type))
        self.fit_mesh_btn.clicked.connect(self._pick_fit_mesh)
        self.fit_capsules_btn.clicked.connect(self._fit_capsules)
        self.fit_sphere_btn.clicked.connect(self._fit_sphere)
        self.fit_radius_btn.clicked.connect(self._fit_radius)
        self.collider_list.customContextMenuRequested.connect(self._list_menu)
        self.collider_filter_le.textChanged.connect(self.apply_filters)
        self.spring_filter_le.textChanged.connect(self.apply_filters)
        self.table.itemChanged.connect(self._on_item_changed)
        self.assign_btn.clicked.connect(partial(self._assign_selected, True))
        self.unassign_btn.clicked.connect(partial(self._assign_selected, False))
        self.assign_all_btn.clicked.connect(self._assign_all)

    # data ---------------------------------------------------------------------

    def fit_options(self):
        """Return the fit options of the panel.

        Returns:
            fit.FitOptions: The options.
        """
        return fit.FitOptions(
            method=self.method_combo.currentData(),
            padding=self.padding_spin.value(),
            percentile=self.percentile_spin.value(),
            min_radius=self.min_radius_spin.value(),
            end_spheres=self.end_spheres_cb.isChecked(),
        )

    def _update_actions(self):
        """Enable the actions the solver uses and the plug-ins allow.

        Driven by the solver's ``collider_types`` and ``bone_volume``.
        """
        if not self._tooltips:
            self._tooltips = {
                widget: widget.toolTip()
                for widget in list(self.create_buttons.values())
                + [self.fit_capsules_btn, self.fit_sphere_btn, self.fit_radius_btn]
            }
        unused = "Not used by {} springs".format(self._solver.label)
        no_plugin = "Needs the boneDynamicsNode plug-in"
        plugin = colliders.plugin_shapes()
        types = self._solver.collider_types
        reasons = {}
        for kind_type, button in self.create_buttons.items():
            if kind_type not in types:
                reasons[button] = unused
            elif kind_type in (colliders.CAPSULE, colliders.MESH) and not plugin:
                reasons[button] = no_plugin
        if colliders.CAPSULE not in types:
            reasons[self.fit_capsules_btn] = unused
        elif not plugin:
            reasons[self.fit_capsules_btn] = no_plugin
        if colliders.SPHERE not in types:
            reasons[self.fit_sphere_btn] = unused
        if not self._solver.bone_volume:
            reasons[self.fit_radius_btn] = unused
        for widget, tooltip in self._tooltips.items():
            widget.setEnabled(widget not in reasons)
            widget.setToolTip(reasons.get(widget, tooltip))
        # the mesh options follow the Mesh button
        mesh_enabled = self.create_buttons[colliders.MESH].isEnabled()
        self.proxy_cb.setEnabled(mesh_enabled)
        self.reduce_spin.setEnabled(mesh_enabled)

    def refresh(self):
        """Rebuild the colliders list and the assignment table."""
        self._update_actions()
        springs = self.all_springs_fn() if self.all_springs_fn else []
        self._springs = [
            spring
            for spring in springs
            if spring.backend == self._backend_name and spring.exists()
        ]
        self._colliders = colliders.list_colliders()
        selected = {
            item.data(COLLIDER_ROLE) for item in self.collider_list.selectedItems()
        }
        with pyqt.block_signals(self.collider_list):
            self.collider_list.clear()
            for network in self._colliders:
                item = QtWidgets.QListWidgetItem(
                    "{}  ({})".format(
                        colliders.label(network), colliders.collider_type(network)
                    )
                )
                item.setData(COLLIDER_ROLE, network)
                driver = colliders.driver(network)
                item.setToolTip("Driver: {}".format(driver) if driver else "World")
                self.collider_list.addItem(item)
                item.setSelected(network in selected)
        with pyqt.block_signals(self.table):
            self.table.clear()
            self.table.setRowCount(len(self._springs))
            self.table.setColumnCount(len(self._colliders))
            self.table.setVerticalHeaderLabels(
                [spring.label for spring in self._springs]
            )
            self.table.setHorizontalHeaderLabels(
                [colliders.label(network) for network in self._colliders]
            )
            # network names: no spring records per cell
            assigned = {
                network: set(
                    attribute.get_message_inputs(network, constants.ASSIGNED_ATTR)
                )
                for network in self._colliders
            }
            for row, spring in enumerate(self._springs):
                for column, network in enumerate(self._colliders):
                    item = QtWidgets.QTableWidgetItem()
                    item.setFlags(
                        QtCore.Qt.ItemIsUserCheckable
                        | QtCore.Qt.ItemIsEnabled
                        | QtCore.Qt.ItemIsSelectable
                    )
                    item.setCheckState(
                        QtCore.Qt.Checked
                        if spring.node in assigned[network]
                        else QtCore.Qt.Unchecked
                    )
                    self.table.setItem(row, column, item)
            self.table.resizeColumnsToContents()
        self.apply_filters()

    def apply_filters(self, *args):
        """Hide the colliders and springs not matching the filter fields."""
        colliders_match = _matcher(self.collider_filter_le.text())
        for row in range(self.collider_list.count()):
            item = self.collider_list.item(row)
            item.setHidden(not colliders_match(item.text()))
        for column, network in enumerate(self._colliders):
            self.table.setColumnHidden(
                column, not colliders_match(colliders.label(network))
            )
        springs_match = _matcher(self.spring_filter_le.text())
        for row, spring in enumerate(self._springs):
            self.table.setRowHidden(row, not springs_match(spring.label))

    def selected_colliders(self):
        """Return the colliders selected in the list."""
        return [item.data(COLLIDER_ROLE) for item in self.collider_list.selectedItems()]

    # actions ------------------------------------------------------------------

    def _run(self, function, *args):
        """Run an action, showing errors as warnings, then refresh."""
        try:
            return function(*args)
        except (RuntimeError, ValueError) as error:
            cmds.warning(str(error))
        finally:
            self.refresh()

    def _create(self, kind_type):
        if kind_type == colliders.MESH:
            meshes = _selected_meshes()
            if not meshes:
                cmds.warning("Select a mesh")
                return
            for mesh in meshes:
                self._run(
                    colliders.create_mesh,
                    mesh,
                    self.proxy_cb.isChecked(),
                    float(self.reduce_spin.value()),
                )
            return
        # one collider per selected joint or control, or one in world space
        self._run(
            colliders.create_many,
            kind_type,
            cmds.ls(selection=True, long=True, transforms=True),
        )

    def _pick_fit_mesh(self):
        meshes = _selected_meshes()
        if meshes:
            self.fit_mesh_le.setText(cmds.ls(meshes[-1])[0])
        else:
            cmds.warning("Select a mesh")

    def fit_inputs(self):
        """Return the fit mesh and the selected target nodes.

        The mesh is the Fit mesh field, or the last selected mesh. The
        targets are the selected transforms that are not meshes (joints,
        controls), in selection order. Bone Dynamics spring controls are
        replaced by their sim joints, hidden in the scene.

        Returns:
            tuple: ``(mesh or None, [target long names])``.
        """
        selection = cmds.ls(selection=True, long=True, transforms=True)
        mesh = self.fit_mesh_le.text().strip()
        if mesh and not cmds.objExists(mesh):
            cmds.warning("Fit mesh {} not found".format(mesh))
            mesh = ""
        if not mesh:
            meshes = [node for node in selection if _is_mesh(node)]
            mesh = meshes[-1] if meshes else None
        targets = [
            self._backend.sim_joint(node) or node
            for node in selection
            if not _is_mesh(node)
        ]
        return mesh, targets

    def _fit_capsules(self):
        mesh, targets = self.fit_inputs()
        if not mesh or not targets:
            cmds.warning("Set the Fit mesh and select the joints or controls")
            return
        self._run(fit.fit_capsules, mesh, targets, self.fit_options())

    def _fit_sphere(self):
        components = cmds.filterExpand(selectionMask=(31, 32, 34)) or []
        mesh, targets = self.fit_inputs()
        if components:
            self._run(
                fit.fit_sphere,
                None,
                targets[0] if targets else None,
                components,
                self.fit_options(),
            )
            return
        if not mesh or not targets:
            cmds.warning(
                "Select vertices, or set the Fit mesh and select joints or controls"
            )
            return
        # one sphere per selected joint or control
        self._run(fit.fit_spheres, mesh, targets, self.fit_options())

    def _fit_radius(self):
        mesh, targets = self.fit_inputs()
        springs = self.springs_fn() if self.springs_fn else []
        springs = springs or registry.springs_from_nodes(targets)
        springs = [
            spring
            for spring in springs
            if spring.backend == bone_dynamics.BACKEND and spring.exists()
        ]
        if not springs or not mesh:
            cmds.warning(
                "Select springs in the list (or their controls) and set the " "Fit mesh"
            )
            return
        self._run(fit.fit_bone_radius, self._backend, springs, mesh, self.fit_options())

    def _list_menu(self, position):
        networks = self.selected_colliders()
        if not networks:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction("Select Collider").triggered.connect(
            lambda: cmds.select(
                [colliders.collider_transform(network) for network in networks]
            )
        )
        drivers = [colliders.driver(network) for network in networks]
        select_driver = menu.addAction("Select Driver")
        select_driver.setEnabled(any(drivers))
        select_driver.triggered.connect(
            lambda: cmds.select([driver for driver in drivers if driver])
        )
        menu.addSeparator()
        menu.addAction("Mirror").triggered.connect(
            lambda: self._run(colliders.mirror, networks)
        )
        menu.addSeparator()
        menu.addAction("Delete").triggered.connect(
            lambda: self._run(colliders.delete, networks)
        )
        menu.exec_(self.collider_list.mapToGlobal(position))

    def _set_assigned(self, cells, assigned):
        """Assign or unassign colliders for (row, column) cells, one undo."""
        with utils.undo_chunk("springManagerAssignColliders"):
            for row, column in cells:
                spring = self._springs[row]
                network = self._colliders[column]
                if assigned:
                    registry.assign(network, [spring])
                else:
                    registry.unassign(network, [spring])
        self.refresh()

    def _on_item_changed(self, item):
        self._set_assigned(
            [(item.row(), item.column())], item.checkState() == QtCore.Qt.Checked
        )

    def _assign_selected(self, assigned):
        cells = [(item.row(), item.column()) for item in self.table.selectedItems()]
        if not cells:
            cmds.warning("Select cells of the assignment table")
            return
        self._set_assigned(cells, assigned)

    def _assign_all(self):
        self._set_assigned(
            [
                (row, column)
                for row in range(len(self._springs))
                for column in range(len(self._colliders))
            ],
            True,
        )


register_section_panel(bone_dynamics.BACKEND, "Colliders", CollidersPanel)
register_section_panel(
    classic_gravity.CLASSIC_GRAVITY_BACKEND,
    "Colliders",
    partial(CollidersPanel, classic_gravity.CLASSIC_GRAVITY_BACKEND),
)
