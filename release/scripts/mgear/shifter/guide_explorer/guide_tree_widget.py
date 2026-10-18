from mgear.vendor.Qt import QtCore, QtWidgets, QtGui

import contextlib
import logging
from dataclasses import dataclass
from functools import partial
from typing import Any, List, Optional

from maya import cmds
from maya.api import OpenMaya as om

import mgear.pymaya as pm
from mgear import shifter
from mgear.core import callbackManager as cb
from mgear.core import pyqt

from mgear.shifter import utils as shifter_utils
from mgear.shifter.guide_explorer import guide_tree_widget_items
from mgear.shifter.guide_explorer import guide_visibility_delegate
from mgear.shifter.guide_explorer.models import ShifterComponent
from mgear.shifter.guide_explorer import utils as guide_explorer_utils

from mgear.compatible import compatible_comp_dagmenu

# Blueprint status colors
BLUEPRINT_COLOR_ACTIVE = QtGui.QColor(100, 180, 255)  # Blue - using blueprint
BLUEPRINT_COLOR_OVERRIDE = QtGui.QColor(255, 200, 100)  # Yellow - local override
BLUEPRINT_COLOR_NOT_IN = None  # Default color - not in blueprint

logger = logging.getLogger("Guide Explorer - Tree Widget")

DATA_ROLE = QtCore.Qt.UserRole + 1
# -- Uuid of the scene node of an item, the key of every item lookup
UUID_ROLE = QtCore.Qt.UserRole + 2

# -- We use shorthand name for the attribute callback as
# -- the callback manager takes in short names and not long names
# -- "comp_name" and others have the same long and short names.
ATTRS_GUIDE = ["rig_name"]
ATTRS_COMP = ["comp_name", "comp_side", "comp_index"]
ATTR_VISIBILITY = "v"
# -- Attributes the blueprint colours of the component items depend on
ATTRS_GUIDE_BLUEPRINT = ["use_blueprint", "blueprint_path"]
ATTRS_COMP_BLUEPRINT = ["blueprint_local_override"]


class GuideTreeWidget(QtWidgets.QTreeWidget):
    """
    Tree widget displaying the active mGear guide and its components.

    Supports building, unbuilding, duplicating, mirroring, deleting,
    and adding components through a context menu or keyboard shortcuts.
    Also integrates with a Component Manager dialog for creating new components.

    :ivar _guide: Cached guide root or query result from the scene.
    :ivar component_manager: Dialog used for selecting and creating components.
    """
    labelsUpdated = QtCore.Signal()
    selectionPayloadRenamed = QtCore.Signal()

    def __init__(self, guide=None):
        """
        Initialize the tree widget and connect actions and signals.

        :param guide: Optional initial guide reference to populate the tree.
        :return: None
        """
        super(GuideTreeWidget, self).__init__()

        self._attr_cb_manager = cb.CallbackManager()
        self._selection_cb_manager = cb.CallbackManager()
        self._uuid_to_item = {}
        self._guide = guide
        self._scene_state = guide_explorer_utils.GuideSceneState()
        self.component_manager = None

        self._block_scene_selection_sync = False
        self._scene_sync_enabled = False
        self._scene_callbacks_active = False

        self._node_added_cb_id = None
        self._node_removed_cb_id = None

        # -- This part is critical for the callbacks slowing down
        # -- when building and importing
        self._pending_scene_refresh = False
        self._node_added_timer = QtCore.QTimer(self)
        self._node_added_timer.setSingleShot(True)
        self._node_added_timer.timeout.connect(self._process_pending_scene_refresh)

        self.add_actions()
        self.create_widgets()
        self.create_connections()

    def add_actions(self) -> None:
        """
        Create QAction instances and register them on the widget.

        Actions are also added to the widget so that their shortcuts remain
        active even when the context menu is closed.

        :return: None
        """
        self.refresh_action = QtWidgets.QAction("Refresh", self)
        self.refresh_action.setShortcut(QtGui.QKeySequence("R"))
        self.refresh_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.mirror_component_action = QtWidgets.QAction("Mirror", self)

        self.build_action = QtWidgets.QAction("Build", self)
        self.build_action.setShortcut(QtGui.QKeySequence("Ctrl+B"))
        self.build_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.unbuild_action = QtWidgets.QAction("Unbuild", self)
        self.unbuild_action.setShortcut(QtGui.QKeySequence("Ctrl+U"))
        self.unbuild_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.delete_action = QtWidgets.QAction("Delete", self)
        self.delete_action.setShortcut(QtGui.QKeySequence("Del"))
        self.delete_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.guide_visibility_action = QtWidgets.QAction("Guide Visibility", self)
        self.guide_visibility_action.setShortcut(QtGui.QKeySequence("H"))
        self.guide_visibility_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.unhide_all_guide_action = QtWidgets.QAction("Unhide All", self)
        self.unhide_all_guide_action.setShortcut(QtGui.QKeySequence("Ctrl+H"))
        self.unhide_all_guide_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.ctrl_visibility_action = QtWidgets.QAction("Control Visibility", self)
        self.ctrl_visibility_action.setShortcut(QtGui.QKeySequence("C"))
        self.ctrl_visibility_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.joint_visibility_action = QtWidgets.QAction("Joint Visibility", self)
        self.joint_visibility_action.setShortcut(QtGui.QKeySequence("J"))
        self.joint_visibility_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.select_component_action = QtWidgets.QAction("Select Component", self)
        self.select_component_action.setShortcut(QtGui.QKeySequence("F"))
        self.select_component_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        self.update_component_type_action = QtWidgets.QAction("Update Component Type", self)
        self.update_component_type_action.setShortcut(QtGui.QKeySequence("Ctrl+T"))
        self.update_component_type_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)

        # -- Register actions on the dialog so their shortcuts stay active.
        # -- Without this, actions only exist in the context menu and
        # -- their shortcuts will not trigger unless the menu is open.
        self.addAction(self.refresh_action)
        self.addAction(self.build_action)
        self.addAction(self.unbuild_action)
        self.addAction(self.delete_action)
        self.addAction(self.guide_visibility_action)
        self.addAction(self.unhide_all_guide_action)
        self.addAction(self.ctrl_visibility_action)
        self.addAction(self.joint_visibility_action)
        self.addAction(self.select_component_action)
        self.addAction(self.update_component_type_action)

    def create_widgets(self) -> None:
        """
        Create and configure the tree columns, header, and context menu policy.

        The tree uses two columns: component name and component type.
        The header is hidden for a cleaner look but retains stretch behavior.

        :return: None
        """
        self.setColumnCount(3)
        self.setIndentation(10)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        header = self.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(60)

        # -- Column 0: visibility icon
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        # -- Column 1: name (stretches)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        # -- Column 2: type (hugs content)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)

        # -- Hide the header after setting modes
        self.setHeaderHidden(True)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.viewport().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        # -- We assume here that icons sizes are always square and equal
        icon_size = QtCore.QSize(17, 17)
        self.visibility_delegate = guide_visibility_delegate.VisibilityDelegate(icon_size=icon_size, parent=self)
        self.setItemDelegateForColumn(2, self.visibility_delegate)

        # -- Setting the column widget of the visibility icons
        self.setColumnWidth(2, 10)

    def create_connections(self) -> None:
        """
        Connect UI signals to their handlers and wire actions to slots.

        Includes double-click selection, context menu handling, and all
        action triggers such as build, unbuild, mirror, delete and selection.

        :return: None
        """
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.build_action.triggered.connect(self.on_build_action_clicked)
        self.unbuild_action.triggered.connect(self.on_unbuild_action_clicked)
        self.refresh_action.triggered.connect(self.on_refresh_action_clicked)
        self.mirror_component_action.triggered.connect(self.on_mirror_action_clicked)
        self.delete_action.triggered.connect(self.on_delete_action_clicked)

        self.guide_visibility_action.triggered.connect(self.on_guide_visibility_action_clicked)
        self.unhide_all_guide_action.triggered.connect(self.on_unhide_all_action_clicked)
        self.ctrl_visibility_action.triggered.connect(self.on_control_visibility_action_clicked)
        self.joint_visibility_action.triggered.connect(self.on_joint_visibility_action_clicked)

        self.select_component_action.triggered.connect(self.on_select_component_action_clicked)

        self.update_component_type_action.triggered.connect(self.on_update_component_type_action_clicked)

    def on_build_action_clicked(self) -> None:
        """
        Build the rig from the current selection context.

        If the root item named "guide" is selected, the entire guide is built.
        If component items are selected, their corresponding roots are selected
        and provided to mGear Shifter for ``buildFromSelection``.

        :return: None
        """
        # -- Select the scene nodes of the UI selection
        nodes = [self._item_node(item) for item in self.selectedItems()]
        shifter_utils.select_items([node for node in nodes if node])

        # -- Do the rig build
        rig = shifter.Rig()
        rig.buildFromSelection()

    def on_unbuild_action_clicked(self) -> None:
        """
        Unbuild the current rig, if present.

        The function finds any node with the attribute ``*.is_rig`` and deletes
        the owning rig transform. Logs an error if no rig is found.

        :return: None
        """
        # -- Get the rig in the scene
        rig = shifter_utils.get_rig()

        if not rig:
            logger.error("No valid rig has been found in the scene to unbuild.")
            return

        # -- Delete the rig
        rig_name = rig[0].node().name()
        shifter_utils.delete_nodes([rig_name])

    def on_refresh_action_clicked(self) -> None:
        """
        Refresh the tree from the current scene.

        :return: None
        """
        self.refresh(force=True)

    def on_mirror_action_clicked(self) -> None:
        """
        Mirror the selected component guide.

        Only the last selected item is considered. The guide root is resolved
        and duplicated with mirroring enabled. The tree is refreshed afterward
        via callbacks.

        :return: None
        """
        items = self.selectedItems()

        if not items:
            return

        # -- Only consider the last selected item for now
        item = items[-1]
        comp_data = item.data(0, DATA_ROLE)

        if not isinstance(comp_data, ShifterComponent):
            logger.warning("Mirror is only supported for component items.")
            return

        # -- Resolve the component root as a PyNode
        try:
            root_node = shifter_utils.node_from_uuid(uuid=comp_data.uuid)
        except Exception:
            try:
                root_node = shifter_utils.node_from_name(name=comp_data.root_name)
            except Exception:
                logger.warning(f"Could not resolve component root for mirroring: {comp_data.full_name}")
                return

        # -- Mirror the guide
        guide = shifter.guide.Rig()
        guide.duplicate(root_node, True)

    def on_delete_action_clicked(self) -> None:
        """
        Delete selected guide or component roots from the scene.

        The function resolves node names from the selection, converts component
        items to their root nodes, and passes the list to a delete helper.
        The tree is refreshed afterward.

        :return: None
        """
        # -- Get the UI selection
        items = self.selectedItems()
        if not items:
            logger.warning("No item in the UI has been selected for deletion.")
            return

        # -- Delete the guide or component roots, resolved by uuid
        nodes = [self._item_node(item) for item in items]
        shifter_utils.delete_nodes([node for node in nodes if node])

        # -- The node removed callback refresh that follows finds no change
        self.refresh()

    def on_guide_visibility_action_clicked(self) -> None:
        """
        Toggle the visibility of the selected guide or component roots.

        :return: None
        """
        items = self.selectedItems()
        # -- Fail/exit early
        if not items:
            return

        for item in items:
            self.on_visibility_icon_clicked(item)

    def on_unhide_all_action_clicked(self) -> None:
        """
        Unhide the entire guide hierarchy.

        Iterates over all tree items representing the guide root and its
        components, forcing their ``visibility`` attribute to True where
        available and updating the corresponding visibility buttons.

        :return: None
        """
        # -- If there is no guide loaded, nothing to do
        if self._guide is None:
            return

        root = self.invisibleRootItem()
        if not root:
            return

        # -- Traverse all top-level items and their children
        stack: List[QtWidgets.QTreeWidgetItem] = [
            root.child(i) for i in range(root.childCount())
        ]

        while stack:
            item = stack.pop()

            # -- Push children to the stack to process the entire subtree
            for i in range(item.childCount()):
                stack.append(item.child(i))

            node = self._item_node(item)
            if not node:
                continue

            # -- Force visible
            if not cmds.getAttr(node + ".visibility"):
                cmds.setAttr(node + ".visibility", True)

            # -- Keep the UI button in sync
            self.update_visibility_widget(item, node)

    def on_control_visibility_action_clicked(self) -> None:
        """
        Toggle the rig control visibility.

        Resolves the active rig via 'shifter_utils.get_rig()', then flips the
        'ctl_vis' attribute on the rig root if present.

        :return: None
        """
        rig_list = shifter_utils.get_rig()
        rig = rig_list[0].node() if rig_list and hasattr(rig_list[0], "node") else None

        if not rig:
            return

        ctrl_visibility = rig.ctl_vis.get()
        rig.ctl_vis.set(not ctrl_visibility)

    def on_joint_visibility_action_clicked(self) -> None:
        """
        Toggle the rig joint visibility.

        Resolves the active rig via 'shifter_utils.get_rig()', then flips the
        'jnt_vis' attribute on the rig root if present.

        :return: None
        """
        rig_list = shifter_utils.get_rig()
        rig = rig_list[0].node() if rig_list and hasattr(rig_list[0], "node") else None

        if not rig:
            return

        jnt_visibility = rig.jnt_vis.get()
        rig.jnt_vis.set(not jnt_visibility)

    def on_select_component_action_clicked(self) -> None:
        """
        Select the scene nodes that correspond to the selected tree items.

        Builds a list of node names by reading DATA_ROLE:
        - If a ShifterComponent is stored, resolves it via UUID.
        - Otherwise treats the payload as a node-like object.

        :return: None
        """
        items = self.selectedItems()
        selection_list: List[str] = []

        for item in items:
            comp_data = item.data(0, DATA_ROLE)

            if hasattr(comp_data, "root_name"):
                node = shifter_utils.node_from_uuid(uuid=comp_data.uuid)
            else:
                node = comp_data

            selection_list.append(node)

        shifter_utils.select_items(selection_list, replace=True)

    def refresh(self, force=False, select=None):
        """Rebuild the tree when the scene guide or its components changed.

        A pending refresh from the node added/removed callbacks is dropped,
        as the tree now matches the scene.

        Args:
            force (bool, optional): Rebuild even if nothing changed.
            select (list of str, optional): Uuids of the items to select after
                the rebuild, instead of the currently selected items.

        Returns:
            bool: True if the tree was rebuilt.
        """
        self._pending_scene_refresh = False
        self._node_added_timer.stop()
        if not self._scene_state.update() and not force:
            return False
        self._rebuild(select)
        return True

    def get_guide_from_scene(self):
        """Rebuild the tree from the scene guide, whether it changed or not."""
        self.refresh(force=True)

    @contextlib.contextmanager
    def _one_selection_signal(self):
        """Emit ``itemSelectionChanged`` once for the selection changes inside."""
        self.blockSignals(True)
        try:
            yield
        finally:
            self.blockSignals(False)
        self.itemSelectionChanged.emit()

    def _rebuild(self, select=None):
        """Rebuild the tree and restore the selected items.

        The selected items are restored by uuid; when none of them exist
        anymore, the guide root is selected. ``itemSelectionChanged`` is
        emitted once.

        Args:
            select (list of str, optional): Uuids of the items to select,
                instead of the currently selected items.
        """
        current = self.currentItem()
        current_uuid = current.data(0, UUID_ROLE) if current else None
        if select is None:
            select = [item.data(0, UUID_ROLE) for item in self.selectedItems()]
        else:
            current_uuid = select[-1] if select else None

        with self._one_selection_signal():
            self._populate()
            items = [
                self._uuid_to_item[uuid]
                for uuid in select
                if uuid in self._uuid_to_item
            ]
            root_item = self.topLevelItem(0)
            if not items and root_item:
                items = [root_item]
            for item in items:
                item.setSelected(True)
            current = self._uuid_to_item.get(current_uuid)
            if current is None and items:
                current = items[-1]
            if current is not None:
                self.setCurrentItem(current, 0, QtCore.QItemSelectionModel.NoUpdate)

    def _populate(self):
        """Clear the tree and create the items of the last scanned guide."""
        self._attr_cb_manager.removeAllManagedCB()
        self.clear()
        self._uuid_to_item.clear()
        self._guide = None

        state = self._scene_state
        if not state.guide:
            logger.warning("No Guide has been found in the scene.")
            return

        self._guide = pm.PyNode(state.guide)

        root_item = guide_tree_widget_items.GuideTreeWidgetItem(
            parent=self, rig_name=cmds.getAttr(state.guide + ".rig_name")
        )
        root_item.setData(0, DATA_ROLE, self._guide)
        self._add_item(
            root_item,
            state.guide,
            state.snapshot[0],
            ATTRS_GUIDE,
            ATTRS_GUIDE_BLUEPRINT,
        )

        for node, root_uuid in zip(state.components, state.snapshot[1:]):
            data = self._component_data(node, root_uuid)
            comp_item = guide_tree_widget_items.ComponentTreeWidgetItem(
                root_item, data.full_name, data.comp_type
            )
            comp_item.setData(0, DATA_ROLE, data)
            self._add_item(comp_item, node, root_uuid, ATTRS_COMP, ATTRS_COMP_BLUEPRINT)

        self._update_blueprint_colors(state.components)

    @staticmethod
    def _component_data(node, uuid):
        """Read the tree data of a component root.

        Args:
            node (str): Name of the component root.
            uuid (str): Uuid of the component root.

        Returns:
            ShifterComponent: The component data.
        """
        comp_side = cmds.getAttr(node + ".comp_side")
        comp_index = cmds.getAttr(node + ".comp_index")
        return ShifterComponent(
            full_name="{}_{}{}".format(
                cmds.getAttr(node + ".comp_name"), comp_side, comp_index
            ),
            comp_type=cmds.getAttr(node + ".comp_type"),
            root_name=cmds.ls(node)[0],
            side=comp_side,
            index=comp_index,
            uuid=uuid,
        )

    def _add_item(self, item, node, uuid, label_attrs, blueprint_attrs):
        """Register a new tree item for a scene node.

        Args:
            item (QtWidgets.QTreeWidgetItem): The item.
            node (str): Long name of the guide or component root.
            uuid (str): Uuid of the node.
            label_attrs (list of str): Short names of the attributes the item
                label is made of.
            blueprint_attrs (list of str): Short names of the node attributes
                the blueprint colours depend on.
        """
        item.setData(0, UUID_ROLE, uuid)
        self._uuid_to_item[uuid] = item
        self._create_attr_callbacks(node, uuid, label_attrs, blueprint_attrs)
        self.update_visibility_widget(item, node)

    def _blueprint_components(self, guide):
        """Return the blueprint components of the guide, if it uses one.

        Args:
            guide (str): Long name of the guide root.

        Returns:
            dict: Blueprint components by full name, empty if the guide
                doesn't use a blueprint.
        """
        try:
            for attr in ("use_blueprint", "blueprint_path"):
                if not cmds.attributeQuery(attr, node=guide, exists=True):
                    return {}
            if not cmds.getAttr(guide + ".use_blueprint"):
                return {}
            path = cmds.getAttr(guide + ".blueprint_path")
            if not path:
                return {}
            return guide_explorer_utils.load_blueprint_components(path)
        except Exception as e:
            logger.debug(f"Could not load blueprint data: {e}")
            return {}

    def _update_blueprint_colors(self, nodes=None) -> None:
        """
        Color the component items by their blueprint status.

        Called after a rebuild and when the guide blueprint settings or a
        component local override change.

        :param nodes: Long names of the component roots, in item order.
            Resolved from the item uuids when not given.
        :return: None
        """
        root_item = self.topLevelItem(0)
        guide = self._item_node(root_item) if root_item else None
        if not guide:
            return

        blueprint_components = self._blueprint_components(guide)
        for index in range(root_item.childCount()):
            item = root_item.child(index)
            node = nodes[index] if nodes else self._item_node(item)
            if node:
                self._apply_blueprint_color(item, node, blueprint_components)

    def _apply_blueprint_color(
        self,
        item: QtWidgets.QTreeWidgetItem,
        node: str,
        blueprint_components: dict,
    ) -> None:
        """
        Apply text color to component item based on blueprint status.

        Colors:
        - Blue: Component in blueprint, using blueprint settings (no local override)
        - Yellow: Component in blueprint, but local override is enabled
        - Default: Component not in blueprint

        :param item: Tree widget item to color
        :param node: Long name of the component root
        :param blueprint_components: Dict of components from blueprint
        :return: None
        """
        full_name = item.data(0, DATA_ROLE).full_name
        color = None
        tooltip = full_name
        if full_name in blueprint_components:
            # Check if local override is enabled
            has_local_override = False
            if cmds.attributeQuery("blueprint_local_override", node=node, exists=True):
                has_local_override = cmds.getAttr(node + ".blueprint_local_override")

            if has_local_override:
                # Yellow - has local override
                color = BLUEPRINT_COLOR_OVERRIDE
                tooltip += " (Blueprint: Local Override)"
            else:
                # Blue - using blueprint settings
                color = BLUEPRINT_COLOR_ACTIVE
                tooltip += " (Blueprint: Active)"

        # -- No colour: back to the default text colour
        brush = QtGui.QBrush(color) if color else None
        item.setData(0, QtCore.Qt.ForegroundRole, brush)
        item.setData(1, QtCore.Qt.ForegroundRole, brush)
        item.setToolTip(0, tooltip)

    def _create_attr_callbacks(self, node, uuid, label_attrs, blueprint_attrs):
        """
        Register the label, visibility and blueprint change callbacks of a node.

        :param node: Name of the node to watch.
        :param uuid: Uuid of the node, passed to the callbacks.
        :param label_attrs: Short names of the attributes of the item label.
        :param blueprint_attrs: Short names of the attributes the blueprint
            colours depend on.
        :return: None
        """
        # -- Create a unique name so this manager can cleanly remove them later
        callback_namespace = f"GuideOverview.{uuid}"
        self._attr_cb_manager.attributeChangedCB(
            f"{callback_namespace}.label",
            partial(self._on_label_changed, uuid),
            node,
            label_attrs,
        )
        self._attr_cb_manager.attributeChangedCB(
            f"{callback_namespace}.{ATTR_VISIBILITY}",
            partial(self._on_visibility_changed, uuid),
            node,
            [ATTR_VISIBILITY],
        )
        self._attr_cb_manager.attributeChangedCB(
            f"{callback_namespace}.blueprint",
            self._update_blueprint_colors,
            node,
            blueprint_attrs,
        )

    def _item_node(self, item):
        """
        Return the long name of the scene node of a tree item.

        :param item: Tree item.
        :return: Long name of the node, or None if it no longer exists.
        """
        uuid = item.data(0, UUID_ROLE)
        nodes = cmds.ls(uuid, long=True) if uuid else None
        return nodes[0] if nodes else None

    def _register_node_added_callback(self) -> None:
        """
        Register DG node-added and node-removed callbacks.

        Used so the tree can refresh when new guide or component nodes
        are created or deleted.

        :return: None
        """
        if self._node_added_cb_id is None:
            self._node_added_cb_id = om.MDGMessage.addNodeAddedCallback(self._on_node_added,
                                                                        "transform")

        if self._node_removed_cb_id is None:
            self._node_removed_cb_id = om.MDGMessage.addNodeRemovedCallback(self._on_node_removed,
                                                                            "transform")

    @property
    def syncing_from_scene(self):
        """bool: True while the tree selection follows a Maya selection change."""
        return self._block_scene_selection_sync

    def _on_visibility_changed(self, uuid: str) -> None:
        """
        Update the eye icon when a guide or component root visibility changes.

        :param uuid: Uuid of the node whose visibility changed.
        :return: None
        """
        item = self._uuid_to_item.get(uuid)
        if item:
            self.update_visibility_widget(item)

    def _on_label_changed(self, uuid: str) -> None:
        """
        Update the item label when a guide or component naming attribute changes.

        :param uuid: Uuid of the node whose attribute changed.
        :return: None
        """
        item = self._uuid_to_item.get(uuid)
        node = self._item_node(item) if item else None
        if not node:
            return

        self.blockSignals(True)
        try:
            if isinstance(item.data(0, DATA_ROLE), ShifterComponent):
                data = self._component_data(node, uuid)
                item.setText(0, data.full_name)
                item.setData(0, DATA_ROLE, data)
                # -- The new name can be in the blueprint or not
                self._update_blueprint_colors()
            else:
                rig_name = cmds.getAttr(node + ".rig_name")
                item.setText(0, f"guide ({rig_name})")
        finally:
            self.blockSignals(False)

        self.labelsUpdated.emit()
        if self.currentItem() is item:
            self.selectionPayloadRenamed.emit()

    def _on_scene_selection_changed(self, *args: Any) -> None:
        """
        Sync the tree selection from the current Maya selection.

        Called whenever the Maya selection changes. The tree emits one
        ``itemSelectionChanged`` while ``syncing_from_scene`` is True.

        :return: None
        """
        if not self._scene_sync_enabled or self._block_scene_selection_sync:
            return

        selection = cmds.ls(selection=True, long=True)
        if not selection:
            return

        # -- The component root of the last selected object, or the object
        # -- itself when it is the guide root
        try:
            comp_root = shifter_utils.find_component_root(selection[-1])
            node = comp_root.name() if comp_root else selection[-1]
            uuid = shifter_utils.get_uuids([node])[0]
        except Exception:
            return

        item = self._uuid_to_item.get(uuid)
        if not item:
            return

        self._block_scene_selection_sync = True
        try:
            with self._one_selection_signal():
                self.clearSelection()
                self.setCurrentItem(item)
                self.scrollToItem(item)
                parent = item.parent()
                if parent:
                    self.expandItem(parent)
        finally:
            self._block_scene_selection_sync = False

    def _on_node_added(self, mobj: om.MObject, clientData: Any = None) -> None:
        """
        DG callback when a transform node is created.

        This does not inspect custom attributes because the callback fires
        before mGear has finished adding them. Instead, it schedules a
        debounced tree refresh if the widget is visible and a guide is
        currently loaded.

        :param mobj: Maya object that was added.
        :param clientData: Arbitrary client data passed by Maya.
        :return: None
        """
        # -- Only care while the widget is actually visible
        if not self.isVisible():
            return

        self._pending_scene_refresh = True

        # -- Restart the debounce timer. If more nodes are added before the timeout,
        # -- this will be called again and the timer will be restarted.
        self._node_added_timer.start(50)

    def _on_node_removed(self, mobj: om.MObject, clientData: Any = None) -> None:
        """
        DG callback when a transform node is deleted.

        Schedules a debounced tree refresh if the widget is visible.

        :param mobj: Maya object that was removed.
        :param clientData: Arbitrary client data passed by Maya.
        :return: None
        """
        if not self.isVisible():
            return

        self._pending_scene_refresh = True
        self._node_added_timer.start(100)

    def _process_pending_scene_refresh(self) -> None:
        """
        Handle any pending scene refresh requested by the node-added callback.

        Called by the debounce timer once there have been no new nodes added
        for the timer interval. The tree is only rebuilt when the guide or
        its components changed.

        :return: None
        """
        if not self._pending_scene_refresh:
            return

        # -- A build pumps Qt events while it runs, which would let this timer
        # -- fire mid-build. Keep the refresh pending and retry once it ends.
        if shifter.is_building():
            self._node_added_timer.start(100)
            return

        # -- Clear the flag first to avoid accidental loops
        self._pending_scene_refresh = False

        # -- If the widget is no longer visible, skip the refresh
        if not self.isVisible():
            return

        self.refresh()

    def on_update_component_type_action_clicked(self) -> None:
        """
        Update the component type for the selected component using the DAG menu.

        Ensures a single ShifterComponent is selected, selects the component
        in the scene if needed, calls the compatibility helper, then rebuilds
        the tree and attempts to reselect the updated component.

        :return: None
        """
        items = self.selectedItems()
        # -- If nothing is selected, do nothing.
        if not items:
            return

        # -- Currently on considering single item selection
        # -- Get the last selected item
        data = items[-1].data(0, DATA_ROLE)

        # -- Ensure it is a shifter component object
        if not isinstance(data, ShifterComponent):
            return

        selected_uuid = data.uuid

        # -- Ensure that we have something selected in order for something to be
        # -- picked up by the command
        if not self._scene_sync_enabled:
            try:
                node = shifter_utils.node_from_uuid(uuid=selected_uuid)
            except Exception:
                logger.warning(f"Could not resolve node from uuid: {selected_uuid}")
                return

            shifter_utils.select_items(items=[node])

        # -- Update the component type
        compatible_comp_dagmenu.update_component_type_and_update_guide_with_dagmenu()

        # -- Rebuild the tree and select the updated component, which has a
        # -- new root node with the same name
        self.refresh(force=True, select=cmds.ls(data.root_name, uuid=True))

    def on_visibility_icon_clicked(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """
        Toggle visibility for the node represented by the given item.

        :param item: Tree item whose visibility button was clicked.
        :return: None
        """
        node = self._item_node(item)
        if not node:
            return

        attr = node + ".visibility"
        cmds.setAttr(attr, not cmds.getAttr(attr))
        self.update_visibility_widget(item, node)

    def update_visibility_widget(
        self, item: QtWidgets.QTreeWidgetItem, node=None
    ) -> None:
        """
        Update the visibility icon for the given item.

        :param item: Tree item to refresh.
        :param node: Long name of the item node, resolved from the item uuid
            when not given.
        """
        if node is None:
            node = self._item_node(item)
        if not node:
            item.setDisabled(True)
            return

        is_visible = bool(cmds.getAttr(node + ".visibility"))
        item.setDisabled(False)

        icon_name = "mgear_eye.svg" if is_visible else "mgear_eye-off.svg"
        item.setIcon(2, pyqt.get_cached_icon(icon_name))
        item.setToolTip(2, "Visible" if is_visible else "Hidden")

    def _enable_scene_callbacks(self) -> None:
        """
        Ensure scene callbacks are registered.

        Only called when the widget becomes visible.

        :return: None
        """
        if self._scene_callbacks_active:
            return

        # -- Selection changed
        self._selection_cb_manager.selectionChangedCB("GuideOverview.Selection",
                                                      self._on_scene_selection_changed)

        # -- Node added, node removed
        self._register_node_added_callback()
        self._scene_callbacks_active = True

    def _disable_scene_callbacks(self) -> None:
        """
        Remove scene callbacks.

        Called when the widget is hidden or closed.

        :return: None
        """
        if not self._scene_callbacks_active:
            return

        # -- Stop any pending node-added refresh
        self._node_added_timer.stop()
        self._pending_scene_refresh = False

        # -- Remove selection callbacks
        self._selection_cb_manager.removeAllManagedCB()

        # -- Remove node-added callback
        if self._node_added_cb_id is not None:
            try:
                om.MMessage.removeCallback(self._node_added_cb_id)
            except Exception:
                pass
            self._node_added_cb_id = None

        if self._node_removed_cb_id is not None:
            try:
                om.MMessage.removeCallback(self._node_removed_cb_id)
            except Exception:
                pass
            self._node_removed_cb_id = None

        self._scene_callbacks_active = False

    def show_context_menu(self, point: QtCore.QPoint) -> None:
        """
        Show the context menu for the tree.

        Builds the right-click menu with guide and component actions, then opens it
        at the cursor position. The incoming point is in the viewport coordinate
        system and is mapped to global screen space.

        :param point: Position of the click in viewport coordinates.
        :return: None
        """
        has_guide = self._guide is not None
        rig_list = shifter_utils.get_rig()
        has_rig = bool(rig_list) and hasattr(rig_list[0], "node") and rig_list[0].node()

        menu = QtWidgets.QMenu(self)

        menu.addAction(self.build_action)
        menu.addAction(self.unbuild_action)
        menu.addSeparator()

        # -- Visibility actions
        visibility_actions: List[QtWidgets.QAction] = []

        if has_guide:
            visibility_actions.append(self.guide_visibility_action)
            visibility_actions.append(self.unhide_all_guide_action)

        if has_rig:
            visibility_actions.append(self.ctrl_visibility_action)
            visibility_actions.append(self.joint_visibility_action)

        for action in visibility_actions:
            menu.addAction(action)

        # -- Add separator only if at least one visibility action exists
        if visibility_actions:
            menu.addSeparator()

        menu.addAction(self.mirror_component_action)
        menu.addSeparator()
        menu.addAction(self.delete_action)
        menu.addSeparator()
        menu.addAction(self.select_component_action)
        menu.addSeparator()
        menu.addAction(self.refresh_action)
        menu.addSeparator()
        menu.addAction(self.update_component_type_action)

        menu.exec_(self.viewport().mapToGlobal(point))

    def clear_items(self) -> None:
        """
        Clear all items and associated callbacks from the tree.

        Removes all managed callbacks and resets the internal node-to-item maps.

        :return: None
        """
        # -- Attribute callbacks on guide and components
        self._attr_cb_manager.removeAllManagedCB()

        # -- Clear tree items and maps
        self.clear()
        self._uuid_to_item.clear()
        self._guide = None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Handle mouse presses so that clicking the visibility column
        toggles the icon instead of using a button widget.
        """
        index = self.indexAt(event.pos())
        if index.isValid() and index.column() == 2:
            item = self.itemFromIndex(index)
            if item:
                self.on_visibility_icon_clicked(item)

        # -- Keep normal selection behavior
        super(GuideTreeWidget, self).mousePressEvent(event)

    def teardown(self) -> None:
        """
        Fully tear down the tree widget before the parent UI is closed.

        This disables all scene callbacks and clears all items, mappings
        and attribute callbacks.

        :return: None
        """
        # -- Stop reacting to scene
        self._disable_scene_callbacks()

        # -- Clear tree model and attribute callbacks
        self.clear_items()

    def showEvent(self, event: QtCore.QEvent) -> None:
        """
        Qt show event handler.

        When the tree becomes visible, enable scene callbacks.

        :param event: Qt show event.
        :return: None
        """
        super().showEvent(event)
        self._enable_scene_callbacks()

    def hideEvent(self, event: QtCore.QEvent) -> None:
        """
        Qt hide event handler.

        When the tree is hidden, disable scene callbacks.

        :param event: Qt hide event.
        :return: None
        """
        self._disable_scene_callbacks()
        super().hideEvent(event)
