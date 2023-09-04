import maya.cmds as cmds

from mgear.vendor.Qt import QtCore

from mgear.core import pyqt
from mgear.shifter.game_tools_fbx import fbx_export_node, partition_widgets


class PartitionNodeClass(partition_widgets.NodeClass):
    def __init__(
        self,
        node_name,
        node_type,
        is_root,
        icon,
        enabled,
        network_enabled,
        is_master=False,
    ):
        super(PartitionNodeClass, self).__init__(
            node_name=node_name,
            node_type=node_type,
            is_root=is_root,
            icon=icon,
            enabled=enabled,
            network_enabled=network_enabled,
        )
        self._is_master = is_master

    @property
    def is_master(self):
        return self._is_master

    @is_master.setter
    def is_master(self, flag):
        self._is_master = flag


class PartitionTreeItem(partition_widgets.TreeItem):
    def __init__(self, node, header, show_enabled, parent=None):
        super(PartitionTreeItem, self).__init__(
            node=node, header=header, show_enabled=show_enabled, parent=parent
        )

    def is_master(self):
        return self.node.is_master


class PartitionsOutliner(partition_widgets.OutlinerTreeView):
    NODE_CLASS = PartitionNodeClass
    TREE_ITEM_CLASS = PartitionTreeItem

    def __init__(self, parent=None):
        self._master_item = None
        self._geo_roots = []
        super(PartitionsOutliner, self).__init__(parent=parent)
        self.create_connections()

    def create_connections(self):
        self.itemEnabledChanged.connect(self.partition_item_enabled_changed)
        self.itemAddNode.connect(self.partition_item_add_skeletal_mesh)
        self.itemRenamed.connect(self.partition_item_renamed)
        self.itemRemoved.connect(self.partition_skeletal_mesh_removed)
        self.droppedItems.connect(self.partition_items_dropped)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            index = self.indexAt(event.pos())
            if index.row() == -1:
                self._action_button_pressed = False
                super(PartitionsOutliner, self).mousePressEvent(event)
                self.clearSelection()
                self.window().repaint()
                return
            item = self._get_corresponding_item(index)
            if item and not item.is_root():
                cmds.select(item.get_name())

        super(PartitionsOutliner, self).mouseDoubleClickEvent(event)

    def can_be_dropped(self, index):
        valid = super(PartitionsOutliner, self).can_be_dropped(index)
        if not valid:
            return valid

        # only root nodes can accept drop events
        item = self.itemFromIndex(index)
        return False if not item.is_master else True

    def set_geo_roots(self, geo_roots):
        self._geo_roots = geo_roots
        self.reset_contents()

    def get_master_partition(self):
        master_partition = {}
        master_partition["Master"] = {"enabled": True, "skeletal_meshes": []}
        if not self._master_item:
            return master_partition

        for i in range(self._master_item.childCount()):
            item = self._master_item.child(i)
            master_partition["Master"]["skeletal_meshes"].append(
                item.get_name()
            )

        return master_partition

    def find_items(self):
        export_nodes = fbx_export_node.FbxExportNode.find()
        if not export_nodes:
            return {}
        export_node = export_nodes[0]
        if len(export_nodes) > 1:
            cmds.warning(
                'Multiple FBX Export nodes found in scene. \
                         Using first one found: "{}"'.format(
                    export_node
                )
            )
        return export_node.get_partitions()

    def populate_items(self, add_callbacks=True):
        if add_callbacks:
            self.cleanup()

        self._master_item = self._create_master_root_item()
        self._master_item.setFlags(
            self._master_item.flags()
            | QtCore.Qt.ItemIsEditable
            | QtCore.Qt.ItemIsDropEnabled
        )
        self._master_item.setFlags(
            self._master_item.flags() & ~QtCore.Qt.ItemIsDragEnabled
        )
        self.addTopLevelItem(self._master_item)

        all_items = self.find_items()

        for item_name, item_data in all_items.items():
            root_item = self._create_root_item(item_name)
            root_item.setFlags(
                root_item.flags()
                | QtCore.Qt.ItemIsEditable
                | QtCore.Qt.ItemIsDropEnabled
            )
            root_item.setFlags(
                root_item.flags() & ~QtCore.Qt.ItemIsDragEnabled
            )
            self.addTopLevelItem(root_item)
            child_items = item_data.get("skeletal_meshes", [])
            for child_node in child_items:
                child = self._add_partition_item(child_node, root_item)
                child.setFlags(child.flags() | QtCore.Qt.ItemIsEditable)
                child.setFlags(child.flags() & ~QtCore.Qt.ItemIsDropEnabled)
                root_item.addChild(child)
                if add_callbacks:
                    pass
            enabled = item_data.get("enabled", True)
            color = item_data.get("color", None)
            if not enabled:
                root_item.set_enabled()
            if color is not None:
                root_item.set_label_color(color)

        self._update_master_partition()

    def _on_custom_context_menu_requested(self, pos):
        item = self._get_current_item()
        if not item or item.is_master():
            return

        super(PartitionsOutliner, self)._on_custom_context_menu_requested(pos)

    def _create_master_root_item(self):
        node_icon = pyqt.get_icon("mgear_package")
        root_node = self.NODE_CLASS(
            "Master", "Root", True, node_icon, True, True, is_master=True
        )
        root_node.can_be_disabled = False
        root_node.can_be_deleted = False
        root_node.can_add_children = False
        root_node.can_be_duplicated = False

        item = self.TREE_ITEM_CLASS(root_node, "Master", True, parent=self)

        return item

    def _add_master_partition_item(self, node, partition_item):
        node_icon = pyqt.get_icon("mgear_box")
        item_node = self.NODE_CLASS(
            node,
            "Geometry",
            False,
            node_icon,
            True,
            partition_item.node.network_enabled,
        )
        item_node.can_be_disabled = False
        item_node.can_be_deleted = False

        item = self.TREE_ITEM_CLASS(item_node, "", True, partition_item)

        return item

    def _update_master_partition(self):
        if not self._master_item or not self._geo_roots:
            return

        found_meshes = []
        for geo_root in self._geo_roots:
            if not geo_root:
                return
            children = (
                cmds.listRelatives(
                    geo_root,
                    allDescendents=True,
                    fullPath=True,
                    type="transform",
                )
                or []
            )
            meshes = [
                child
                for child in children
                if cmds.listRelatives(child, shapes=True) or []
            ]
            found_meshes.extend(meshes)
        if not found_meshes:
            return

        partition_meshes = []
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if not item or item == self._master_item:
                continue
            for j in range(item.childCount()):
                child = item.child(j)
                partition_meshes.append(child.get_name())

        for found_mesh in found_meshes:
            if found_mesh in partition_meshes:
                continue
            child = self._add_master_partition_item(
                found_mesh, self._master_item
            )
            child.setFlags(
                child.flags()
                | QtCore.Qt.ItemIsEditable
                | QtCore.Qt.ItemIsDropEnabled
            )
            self._master_item.addChild(child)

    def partition_item_enabled_changed(self, item):
        if not item:
            return

        export_node = fbx_export_node.FbxExportNode.get()
        if not export_node:
            return

        export_node.set_partition_enabled(
            item.node.node_name, item.is_enabled()
        )

    def partition_item_add_skeletal_mesh(self, item):
        if not item:
            return

        export_node = fbx_export_node.FbxExportNode.get()
        if not export_node:
            return

        transforms = cmds.ls(sl=True, long=True, type="transform")
        meshes = [
            child
            for child in transforms
            if cmds.listRelatives(child, shapes=True)
        ]

        export_node.add_skeletal_meshes_to_partition(
            item.node.node_name, meshes
        )

        self.reset_contents()

    def partition_item_renamed(self, old_name, new_name):
        if not old_name or not new_name or old_name == new_name:
            return

        export_node = fbx_export_node.FbxExportNode.get()
        if not export_node:
            return

        export_node.set_partition_name(old_name, new_name)

    def partition_skeletal_mesh_removed(self, parent_name, removed_name):
        if not parent_name or not removed_name:
            return

        export_node = fbx_export_node.FbxExportNode.get()
        if not export_node:
            return

        export_node.delete_skeletal_mesh_from_partition(
            parent_name, removed_name
        )

        self.reset_contents()

    def partition_items_dropped(
        self, parent_item, dropped_items, duplicate=False
    ):
        if not parent_item or not dropped_items:
            return

        export_node = fbx_export_node.FbxExportNode.get()
        if not export_node:
            return

        valid_items = [item for item in dropped_items if item.is_master]
        if not valid_items:
            return

        if not duplicate:
            # remove items from their old partitions
            for item in valid_items:
                export_node.delete_skeletal_mesh_from_partition(
                    item.parent().node.node_name, item.node.node_name
                )

        # add items to new partition
        meshes_names = [item.node.node_name for item in valid_items]
        export_node.add_skeletal_meshes_to_partition(
            parent_item.node.node_name, meshes_names
        )
