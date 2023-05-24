import copy
import weakref
from functools import partial

from mgear.core import pyqt, utils
from mgear.shifter import game_tools_fbx_utils as fu
from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui

import maya.cmds as cmds

# TODO: Remove following dependencies
import maya.app.flux.core as fx
from maya.app.flux.core import pix
from MASH.itemStyle import *

ROW_HEIGHT = 30
LABEL_COLORS = ['red', 'blue', 'grey', 'orange', 'green', 'yellow', 'purple']
COLORS = {
	'blue': [88, 165, 204],
	'grey': [189, 189, 189],
	'orange': [219, 148, 86],
	'green': [85, 171, 100],
	'yellow': [191, 178, 58],
	'purple': [174, 156, 219],
	'default': [241, 90, 91]
}


class NodeClass(object):
	def __init__(self, node_name, node_type, is_root, icon, enabled, network_enabled):
		super(NodeClass, self).__init__()

		self._node_name = node_name
		self._node_type = node_type
		self._is_root = is_root
		self._icon = icon
		self._enabled = enabled
		self._network_enabled = network_enabled
		self._label_color = QtGui.QColor(241, 90, 91)
		color = QtGui.QColor(0, 0, 0)
		color.setNamedColor('#444444')
		if self._is_root:
			color.setNamedColor('#5d5d5d')
		self._background_color = color
		self._tooltip = None
		self._can_be_deleted = True
		self._can_be_disabled = True
		self._can_be_duplicated = True
		self._can_add_children = True

	def __repr__(self):
		return 'NODE - {} {}'.format(self._node_name, self._node_type)

	@property
	def node_name(self):
		return self._node_name

	@node_name.setter
	def node_name(self, value):
		self._node_name = value

	@property
	def display_name(self):
		return self.node_name.split('|')[-1]

	@property
	def node_type(self):
		return self._node_type

	@property
	def is_root(self):
		return self._is_root

	@property
	def icon(self):
		return self._icon

	@property
	def enabled(self):
		return self._enabled

	@enabled.setter
	def enabled(self, flag):
		self._enabled = flag

	@property
	def network_enabled(self):
		return self._network_enabled

	@network_enabled.setter
	def network_enabled(self, flag):
		self._network_enabled = flag

	@property
	def label_color(self):
		return self._label_color

	@label_color.setter
	def label_color(self, value):
		self._label_color = value

	@property
	def background_color(self):
		return self._background_color

	@property
	def can_be_deleted(self):
		return self._can_be_deleted

	@can_be_deleted.setter
	def can_be_deleted(self, flag):
		self._can_be_deleted = flag

	@property
	def can_be_disabled(self):
		return self._can_be_disabled

	@can_be_disabled.setter
	def can_be_disabled(self, flag):
		self._can_be_disabled = flag

	@property
	def can_be_duplicated(self):
		return self._can_be_duplicated

	@can_be_duplicated.setter
	def can_be_duplicated(self, flag):
		self._can_be_duplicated = flag

	@property
	def can_add_children(self):
		return self._can_add_children

	@can_add_children.setter
	def can_add_children(self, flag):
		self._can_add_children = flag


class OutlinerMenu(QtWidgets.QMenu):
	def __init__(self, title='', parent=None):
		super(OutlinerMenu, self).__init__(title, parent)

		self.hovered.connect(self._on_hovered)

	def _on_hovered(self, action):
		QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), action.toolTip(), self, self.actionGeometry(action))


class TreeItem(QtWidgets.QTreeWidgetItem):

	def __init__(self, node, header, show_enabled, parent=None):
		super(TreeItem, self).__init__()

		self._node = node  # type: NodeClass
		self._header = header
		self._connected_nodes = list()
		self._show_enabled = show_enabled

		self.set_parent(parent)

	@property
	def node(self):
		return self._node

	def parent(self):
		return self._parent

	def set_parent(self, parent):
		self._parent = parent

	def get_name(self):
		return self.node.node_name if self.node else self._header

	def set_name(self, name):
		self.node.node_name = name

	def get_display_name(self):
		return self.node.display_name if self.node else self.get_name()

	def get_node_type(self):
		return self.node.node_type

	def get_icon(self):
		return self.node.icon

	def set_enabled(self):
		self.node.enabled = not self.is_enabled()
		if not self.is_root():
			pass
		else:
			self.node.network_enabled = self.is_enabled()

	def get_background_color(self):
		return self.node.background_color

	def get_window_background_color(self):
		return QtGui.QColor(43, 43, 43)

	def get_inactive_color(self):
		return QtGui.QColor(150, 150, 150)

	def is_enabled(self):
		return self.node.enabled

	def network_enabled(self):
		return self.parent().node.network_enabled if self.parent() else True

	def is_root(self):
		return self.node.is_root

	def get_label_color(self):
		return self.node.label_color

	def set_label_color(self, color):
		if isinstance(color, (list, tuple)):
			color = QtGui.QColor(*color)
		self.node.label_color = color
		for i in range(self.childCount()):
			child = self.child(i)
			child.node.label_color = color

		value = [color.red(), color.green(), color.blue()]
		export_node = fu.FbxExportNode.get()
		if not export_node:
			return
		export_node.set_partition_color(self.node.node_name, value)

	def get_action_button_count(self):
		return 7 if self.node.is_root else 3

	def has_enable_toggle(self):
		return self._show_enabled

	def get_action_button(self, index):
		if self.node.is_root:
			if index >= 0 and index <= 6:
				return [
					'Enabled' if self.node.can_be_disabled else None,
					None, 'Add' if self.node.can_add_children else None, None, None, None, None][index]
		else:
			if index >= 0 and index <= 2:
				return [
					'Enabled' if self.node.can_be_disabled else None,
					None, 'Remove' if self.node.can_be_deleted else None][index]

		return None

	def delete_node(self):
		export_node = fu.FbxExportNode.get()
		if not export_node:
			return
		if self.is_root():
			result = export_node.delete_skeletal_mesh_partition(self.get_name())
			if result:
				self.parent().takeTopLevelItem(self.parent().indexOfTopLevelItem(self))
		else:
			result = export_node.delete_skeletal_mesh_from_partition(self.parent().get_name(), self.get_name())
			if result:
				self.parent().takeChild(self.parent().indexOfChild(self))


class OutlinerTreeView(QtWidgets.QTreeWidget):

	TREE_ITEM_CLASS = TreeItem
	NODE_CLASS = NodeClass

	EXPAND_WIDTH = pix(60)
	TRASH_IMAGE = pyqt.get_icon('mgear_trash')
	COPY_IMAGE = pyqt.get_icon('mgear_copy')

	itemEnabledChanged = QtCore.Signal(object)
	itemAddNode = QtCore.Signal(object)
	itemRenamed = QtCore.Signal(str, str)
	itemRemoved = QtCore.Signal(str, str)
	droppedItems = QtCore.Signal(object, list, bool)

	def __init__(self, parent=None):
		super(OutlinerTreeView, self).__init__(parent)

		self._last_hit_action = None
		self._selection_parent = None
		self._selection_node = None
		self._action_button_pressed = False
		self._registered_node_callbacks = list()
		self._button_pressed = None

		self.setHeaderHidden(True)
		self.setIndentation(12)
		self.setMouseTracking(True)
		self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

		self.populate_items()

		self.header().setCascadingSectionResizes(False)
		self.setColumnWidth(0, pix(250))
		self.header().resizeSection(0, pix(250));
		self.resizeColumnToContents(0)
		delegate = TreeViewDelegate(self)
		self.setItemDelegate(delegate)
		self.setStyle(ItemStyle())
		self.setRootIsDecorated(False)
		self.expandAll()
		self.setExpandsOnDoubleClick(False)
		self.setDragEnabled(True)
		self.setAcceptDrops(True)
		self.setDropIndicatorShown(True)
		self.setDefaultDropAction(QtCore.Qt.MoveAction)

		self._context_menu = OutlinerMenu(parent=self)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self._on_custom_context_menu_requested)

	@property
	def last_hit_action(self):
		return self._last_hit_action

	@last_hit_action.setter
	def last_hit_action(self, value):
		self._last_hit_action = value

	def mousePressEvent(self, event):
		"""
		Triggers actions based on mouse press
		"""

		self._button_pressed = event.button()

		if event.button() in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton):
			index = self.indexAt(event.pos())
			if index.row() == -1:
				self._action_button_pressed = False
				super(OutlinerTreeView, self).mousePressEvent(event)
				self.clearSelection()
				self.window().repaint()
				return

			item = self._get_corresponding_item(index)
			action = self._get_current_action(event.pos(), item)

			if item.node.node_type != 'Root':
				self._selection_parent = item.parent().get_name()
				self._selection_node = item.get_name()

			self.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.NoUpdate)

			if action is not None:
				self._action_button_pressed = True
				if action == 'Enabled':
					item.set_enabled()
					self.itemEnabledChanged.emit(item)
				if action == 'Add':
					self.itemAddNode.emit(item)
				if action == 'Remove':
					if not item.is_root():
						parent_name = item.parent().get_name()
						item_name = item.get_name()
						item.parent().takeChild(item.parent().indexOfChild(item))
						self.itemRemoved.emit(parent_name, item_name)
				if action == 'ExpandCollapse':
					if item.node.node_type == 'Root':
						self._toggle_expand_collapse()
			else:
				pass
			event.accept()
		elif event.button() == QtCore.Qt.MiddleButton:
			super(OutlinerTreeView, self).mousePressEvent(event)

		# self.clearSelection()
		super(OutlinerTreeView, self).mousePressEvent(event)
		self.window().repaint()

	def mouseMoveEvent(self, event):
		if not self._action_button_pressed:
			super(OutlinerTreeView, self).mouseMoveEvent(event)

		modifiers = QtGui.QGuiApplication.keyboardModifiers()
		if modifiers == QtCore.Qt.AltModifier:
			QtWidgets.QWidget.setCursor(self, (QtGui.QCursor(QtCore.Qt.DragCopyCursor)))
		else:
			QtWidgets.QWidget.unsetCursor(self)
		self._last_hit_action = None

		# dirty the treeview so it will repaint when the mouse moves over it
		# this is needed to change the icon rollover state
		region = self.childrenRegion()
		self.setDirtyRegion(region)

	def mouseReleaseEvent(self, event):
		QtGui.QGuiApplication.restoreOverrideCursor()
		if not self._action_button_pressed:
			super(OutlinerTreeView, self).mouseReleaseEvent(event)
		else:
			self._action_button_pressed = False
		self.window().repaint()

	def leaveEvent(self, event):
		self._last_hit_action = None
		self.window().repaint()

	@utils.one_undo
	def dropEvent(self, event):
		index = self.indexAt(event.pos())
		item = self.itemFromIndex(index)

		can_be_dropped = self.can_be_dropped(index)
		if not can_be_dropped:
			event.ignore()
			return

		self.droppedItems.emit(
			item, self.selectedItems(), True if self._button_pressed == QtCore.Qt.RightButton else False)

		self.reset_contents()

	def can_be_dropped(self, index):

		item = self.itemFromIndex(index)
		drop_indicator_position = self.dropIndicatorPosition()

		is_invalid_position = (not index.isValid() or item.childCount() == -1 or (
				item.parent().indexOfChild(item) == (item.childCount() - 1) if item.parent() != self else True and
				drop_indicator_position == QtWidgets.QAbstractItemView.BelowItem))

		return not is_invalid_position

	def get_indent(self, index):
		indent = 0
		while (index and index.parent().isValid()):
			index = index.parent()
			indent += self.indentation()

		return indent

	def find_items(self):
		return dict()

	def populate_items(self, add_callbacks=True):

		if add_callbacks:
			self.cleanup()

		all_items = self.find_items()

		for item_name, item_data in all_items.items():
			root_item = self._create_root_item(item_name)
			root_item.setFlags(root_item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDropEnabled)
			root_item.setFlags(root_item.flags() & ~QtCore.Qt.ItemIsDragEnabled)
			self.addTopLevelItem(root_item)

			for child_node in item_data:
				child = self._add_partition_item(child_node, root_item)
				child.setFlags(child.flags() | QtCore.Qt.ItemIsEditable | ~QtCore.Qt.ItemIsDropEnabled)
				child.setFlags(root_item.flags() & ~QtCore.Qt.ItemIsDragEnabled)
				root_item.addChild(child)
				if add_callbacks:
					pass

	def clear_items(self):
		"""
		Clear all tree widget items
		"""

		# NOTE: it seems self.clear() crashes Maya
		for i in range(self.topLevelItemCount()):
			self.takeTopLevelItem(0)

	def reset_contents(self, reset_callbacks=True, expand=True):
		"""
		Forces the repopulation the tree widget
		"""

		self._selection_parent = None
		self._selection_node = None

		self.clear_items()
		self.populate_items(reset_callbacks)

		if expand:
			self.expandAll()

	def cleanup(self):
		self._registered_node_callbacks = list()

	def _create_root_item(self, partition):

		node_icon = pyqt.get_icon('mgear_package')
		root_node = self.NODE_CLASS(partition, 'Root', True, node_icon, True, True)

		item = self.TREE_ITEM_CLASS(root_node, partition, True, parent=self)

		return item

	def _add_partition_item(self, node, partition_item):

		node_icon = pyqt.get_icon('mgear_box')
		item_node = self.NODE_CLASS(node, 'Geometry', False, node_icon, True, partition_item.node.network_enabled)
		item_node.can_be_disabled = False

		item = self.TREE_ITEM_CLASS(item_node, '', True, partition_item)

		return item

	def _get_corresponding_item(self, index):
		return self.itemFromIndex(index) if index.isValid() else None

	def _get_current_item(self):
		return self.currentItem()

	def _get_current_action(self, point, item):
		if item:
			if item.childCount() > 0 and point.x() < self.EXPAND_WIDTH:
				return 'ExpandCollapse'
			return self._last_hit_action
		return None

	def _get_label_color(self):
		item = self._get_current_item()
		return item.node.label_color

	@utils.one_undo
	def _set_label_color(self, color_label):
		color = self._get_color_from_label(color_label)
		self._get_current_item().set_label_color(color)

	def _get_color_from_label(self, color_label):
		return QtGui.QColor(*COLORS.get(color_label.lower(), COLORS['default']))

	def _toggle_expand_collapse(self):
		"""
		Expands and collaps the partition nodes
		"""

		item = self.currentItem()
		self.collapseItem(item) if item.isExpanded() else self.expandItem(item)

	def _delete_node(self):
		item = self._get_current_item()
		if item is None:
			return
		response = cmds.confirmDialog(
			title='Confirm', message='Confirm Deletion',
			button=['Yes', 'No'], defaultButton='Yes', cancelButton='No', dismissString='No')
		if response == 'Yes':
			cmds.select(clear=True)
			item.delete_node()

	def _on_custom_context_menu_requested(self, pos):
		"""
		Internal callback function that rebuils the context menu from scratch
		"""

		selected_indexes = self.selectedIndexes()
		num_indexes = len(selected_indexes)
		self._context_menu.clear()
		item = self._get_current_item()
		if item is None:
			return
		if item.is_root():
			if num_indexes > 0:
				pixmap = QtGui.QPixmap(pix(100), pix(100))
				pixmap.fill(self._get_label_color())
				label_icon = QtGui.QIcon(pixmap)
				prev_menu = self._context_menu.addMenu(label_icon, 'Label Color')
				for color_label in LABEL_COLORS:
					pixmap = QtGui.QPixmap(pix(100), pix(100))
					pixmap.fill(self._get_color_from_label(color_label))
					label_icon = QtGui.QIcon(pixmap)
					prev_menu.addAction(
						label_icon, color_label, lambda color_label=color_label: self._set_label_color(color_label))
			if item.node.can_be_duplicated:
				duplicate_action = self._context_menu.addAction(self.COPY_IMAGE, 'Duplicate')
				duplicate_action.setEnabled(False)
			if item.node.can_be_deleted:
				self._context_menu.addAction(self.TRASH_IMAGE, 'Delete', self._delete_node)
		else:
			if item.node.can_be_deleted:
				self._context_menu.addAction(self.TRASH_IMAGE, 'Delete', self._delete_node)

		self._context_menu.popup(QtGui.QCursor.pos())
		self._context_menu.exec_(self.mapToGlobal(pos))


class TreeViewDelegate(QtWidgets.QItemDelegate):
	def __init__(self, tree_view):
		super(TreeViewDelegate, self).__init__()

		self._tree_view = weakref.ref(tree_view)

	@property
	def tree_view(self):
		return self._tree_view()

	def initStyleOption(self, option, index):
		super(TreeViewDelegate, self).initStyleOption(option, index)
		# override what you need to change in option
		if option.state & QtWidgets.QStyle.State_Selected:
			option.state &= ~ QtWidgets.QStyle.State_Selected
			option.backgroundBrush = QtGui.QBrush(QtCore.Qt.red)

	def paint(self, painter, option, index):
		if not index.isValid():
			return

		item = self.tree_view.itemFromIndex(index)
		row_painter = RowPainter(painter, option, item, self.tree_view)
		row_painter.paint_row()

	def sizeHint(self, option, index):
		hint = super(TreeViewDelegate, self).sizeHint(option, index)
		hint.setHeight(pix(ROW_HEIGHT))
		return hint

	def createEditor(self, parent, option, index):
		"""
		Overrides createEditor function to create the double click editor for renaming nodes.
		"""

		# only root items can be renamed
		item = self.tree_view.itemFromIndex(index)
		if not item or not item.is_root():
			return None

		editor = QtWidgets.QLineEdit(parent)
		editor.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		return editor

	def updateEditorGeometry(self, editor, option, index):
		"""
		Overrides updateEditorGeometry so a valid rectangle for the QtWidgets.QLineEditor is defined.
		"""

		indent = self.tree_view.get_indent(index)
		rect = copy.deepcopy(option.rect)
		rect.setLeft(indent + pix(46.5))
		rect.setBottom(rect.bottom() - pix(4))
		rect.setRight(rect.right() - pix(50))
		editor.setGeometry(rect)

	def setEditorData(self, editor, index):
		item = self.tree_view.itemFromIndex(index)
		editor.setText(item.get_display_name())

	def setModelData(self, editor, model, index):
		"""
		Overrides setModelData which will trigger the node renaming to run within Maya
		"""

		new_value = editor.text()
		item = self.tree_view.itemFromIndex(index)
		if not item:
			return
		name = item.get_name()
		if not name or name == new_value:
			return
		item.set_name(new_value)
		self.tree_view.itemRenamed.emit(name, new_value)


class RowPainter(object):

	DISABLED_BACKGROUND_IMAGE = fx.getPixmap('out_MASH_ChevronBG')
	DISABLED_HIGHLIGHT_IMAGE = fx.getPixmap('out_MASH_ChevronBGSelected')
	EXPANDED_ARROW = (pix(QtCore.QPointF(9.0, 11.0)), pix(QtCore.QPointF(19.0, 11.0)), pix(QtCore.QPointF(14.0, 16.0)))
	COLLAPSED_ARROW = (pix(QtCore.QPointF(12.0, 8.0)), pix(QtCore.QPointF(17.0, 13.0)), pix(QtCore.QPointF(12.0, 18.0)))
	ARROW_COLOR = QtGui.QColor(189, 189, 189)
	ICON_PADDING = pix(10.0)
	ICON_WIDTH = pix(20)
	ICON_WIDTH_NO_DPI = pix(20)
	ICON_TOP_OFFSET = pix(4)
	COLOR_BAR_WIDTH = pix(6)
	DRAG_HANDLE_IMAGE = fx.getPixmap('out_MASH_OutlinerDrag')
	LOCK_IMAGE = fx.getPixmap('out_MASH_OutlinerNoDrag')
	ACTION_BORDER = pix(0)
	ACTION_WIDTH = pix(20)
	ENABLED_IMAGE = fx.getPixmap('out_MASH_Enable')
	DISABLED_IMAGE = fx.getPixmap('out_MASH_Disable')
	ENABLED_SELECTED_IMAGE = fx.getPixmap('out_MASH_Enable_Selected')
	INACTIVE_ENABLED_IMAGE = fx.getPixmap('out_MASH_Inactive')
	ADD_IMAGE = pyqt.get_icon('mgear_plus')
	REMOVE_IMAGE = pyqt.get_icon('mgear_minus')

	def __init__(self, painter, option, item, parent):
		super(RowPainter, self).__init__()

		self._parent = weakref.ref(parent)
		self._painter = painter
		self._item = item  # type: TreeItem
		self._rect = copy.deepcopy(option.rect)
		self._is_highlighted = option.showDecorationSelected and option.state & QtWidgets.QStyle.State_Selected
		self._highlight_color = option.palette.color(QtGui.QPalette.Highlight)

	@property
	def item(self):
		return self._item

	@property
	def parent(self):
		return self._parent

	def paint_row(self):
		self._draw_background()
		self._draw_color_bar()
		self._draw_fill()
		self._draw_arrow_drag_lock()
		text_rect = self._draw_text()
		self._draw_icon(text_rect)
		self._add_action_icons()

	def _draw_background(self):
		"""
		Internal function that draws the cell background color/image
		"""

		if self.item.is_root() or self.item.network_enabled():
			color = self._highlight_color if self._is_highlighted else self.item.get_background_color()
			self._painter.fillRect(self._rect, color)
		else:
			pixmap = self.DISABLED_HIGHLIGHT_IMAGE if self._is_highlighted else self.DISABLED_BACKGROUND_IMAGE
			self._painter.drawTiledPixmap(self._rect, pixmap, QtCore.QPoint(self._rect.left(), 0))

	def _draw_color_bar(self):
		"""Draws the label color bar"""

		color = self.item.get_label_color()
		rect2 = copy.deepcopy(self._rect)
		rect2.setRight(rect2.left() + self.COLOR_BAR_WIDTH)
		self._painter.fillRect(rect2, color)

	def _draw_fill(self):
		"""Draws the border of the cell"""

		rect2 = copy.deepcopy(self._rect)
		old_pen = self._painter.pen()
		self._painter.setPen(QtGui.QPen(self.item.get_window_background_color(), pix(2)))
		rect2.setLeft(rect2.left())
		rect2.setRight(rect2.right() - pix(2))
		rect2.setTop(rect2.top())
		rect2.setBottom(rect2.bottom())
		self._painter.drawRect(rect2)
		self._painter.setPen(old_pen)

	def _draw_arrow_drag_lock(self):
		"""
		Draws the expansion arrow on the nodes that need it
		"""

		self._painter.save()
		old_brush = self._painter.brush()
		if self.item.is_root() and self.item.childCount() > 0:
			padding = pix(3)
			self._painter.translate(self._rect.left() + padding, self._rect.top() + pix(2))
			arrow = self.COLLAPSED_ARROW
			if self.item.isExpanded():
				arrow = self.EXPANDED_ARROW
			self._painter.setBrush(self.ARROW_COLOR)
			self._painter.setPen(QtCore.Qt.NoPen)
			self._painter.drawPolygon(arrow)
			self._painter.setBrush(old_brush)
		else:
			rect2 = copy.deepcopy(self._rect)
			padding = pix(26)
			new_rect = QtCore.QRect()
			new_rect.setRight(rect2.left() + padding)
			new_rect.setLeft(new_rect.right() - self.ICON_WIDTH_NO_DPI)
			new_rect.setBottom(rect2.top() - self.ICON_WIDTH + pix(6))
			new_rect.setTop(new_rect.bottom() + self.ICON_WIDTH)
			icon = self.DRAG_HANDLE_IMAGE
			self._painter.drawPixmap(new_rect, icon)
		self._painter.setBrush(old_brush)
		self._painter.restore()

	def _draw_text(self):
		"""
		Draws node name
		"""

		old_pen = self._painter.pen()
		draw_enabled = True
		if not self.item.node.is_root and not self.item.network_enabled():
			draw_enabled = False
		if self.item.node.enabled and draw_enabled:
			self._painter.setPen(QtGui.QPen(self.parent().palette().text().color(), pix(1)))
		else:
			self._painter.setPen(QtGui.QPen(self.item.get_inactive_color(), pix(1)))
		text_rect = copy.deepcopy(self._rect)
		text_rect.setBottom(text_rect.bottom() + pix(2))
		text_rect.setLeft(text_rect.left() + pix(40) + self.ICON_PADDING)
		text_rect.setRight(text_rect.right() - pix(11))
		self._painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.item.get_display_name())
		self._painter.setPen(old_pen)

		return text_rect

	def _draw_icon(self, text_rect):
		"""
		Internal function that draws the node icon
		"""

		rect2 = copy.deepcopy(text_rect)
		icon = None
		icon = self.item.get_icon()
		if icon:
			new_rect = QtCore.QRect()
			new_rect.setRight(rect2.left() - pix(4))
			new_rect.setLeft(new_rect.right() - self.ICON_WIDTH_NO_DPI)
			new_rect.setBottom(rect2.top() - self.ICON_WIDTH + pix(3))
			new_rect.setTop(new_rect.bottom() + self.ICON_WIDTH)
			draw_enabled = True
			if not self.item.node.is_root and not self.item.network_enabled():
				draw_enabled = False
			if not self.item.node.enabled or not draw_enabled:
				self._painter.setOpacity(0.5)
			self._painter.drawPixmap(new_rect, icon)

	def _draw_action(self, action_name, pixmap, left, top):
		"""
		Internal function that draws the icons for this node.
		"""

		if pixmap is not None:
			icon_rect = QtCore.QRect(left, top, self.ICON_WIDTH, self.ICON_WIDTH)
			p = self.parent().mapFromGlobal(QtGui.QCursor.pos())
			if not icon_rect.contains(p):
				self._painter.setOpacity(1.0)
			else:
				self.parent().last_hit_action = action_name
				pixmap = self._rollover_icon(pixmap)
			self._painter.drawPixmap(icon_rect, pixmap)
			self._painter.setOpacity(1.0)

	def _rollover_icon(self, pixmap):
		img = QtGui.QImage(pixmap.toImage().convertToFormat(QtGui.QImage.Format_ARGB32))
		imgh = img.height()
		imgw = img.width()
		for y in range(0, imgh, 1):
			for x in range(0, imgw, 1):
				pixel = img.pixel(x, y)
				high_limit = 205
				low_limit = 30
				adjustment = 255 - high_limit
				color = QtGui.QColor(pixel)
				v = color.value()
				s = color.saturation()
				h = color.hue()
				if v > low_limit:
					if v < high_limit:
						v = v + adjustment
					else:
						v = 255
				v = color.setHsv(h, s, v)
				img.setPixel(x, y, QtGui.qRgba(color.red(), color.green(), color.blue(), QtGui.qAlpha(pixel)))

		return QtGui.QPixmap(img)

	def _add_action_icons(self):
		"""
		Internal function that draws the icons, buttons and tags on the right hand side of the cell
		"""

		top = self._rect.top() + self.ICON_TOP_OFFSET

		start = self.ACTION_BORDER
		count = self._item.get_action_button_count()

		for i in range(count):
			extra_padding = 0
			checked = False
			pixmap = None
			action_name = self._item.get_action_button(i)
			if action_name == 'Enabled':
				show_enabled_button = self.item.has_enable_toggle()
				if not show_enabled_button:
					start += self.ACTION_WIDTH + extra_padding
					continue
				extra_padding = pix(10)
				pixmap = self.ENABLED_IMAGE
				if not self.item.is_root() and not self.item.network_enabled():
					pixmap = self.INACTIVE_ENABLED_IMAGE
				checked = self.item.is_enabled()
				if not checked:
					pixmap = self.DISABLED_IMAGE
				if self._is_highlighted and checked:
					pixmap = self.ENABLED_SELECTED_IMAGE
			elif action_name == 'Add':
				pixmap = self.ADD_IMAGE
			elif action_name == 'Remove':
				pixmap = self.REMOVE_IMAGE

			start += self.ACTION_WIDTH + extra_padding
			self._draw_action(action_name, pixmap, self._rect.right() - start, top)


class AnimClipsListWidget(QtWidgets.QWidget):

	def __init__(self, parent=None):
		super(AnimClipsListWidget, self).__init__(parent=parent)

		self._game_tools_fbx = parent
		self._root_joint = None
		self._export_path = None
		self._file_name = None

		main_layout = QtWidgets.QVBoxLayout()
		self.setLayout(main_layout)

		anim_clip_option_layout = QtWidgets.QHBoxLayout()
		self._anim_clips_checkbox = QtWidgets.QCheckBox(parent=self)
		self._anim_clips_checkbox.setChecked(True)
		self._add_anim_clip_button = QtWidgets.QPushButton('Add Clip', parent=self)
		self._delete_all_clips_button = QtWidgets.QPushButton('Delete All Clips', parent=self)
		anim_clip_option_layout.addWidget(self._anim_clips_checkbox)
		anim_clip_option_layout.addStretch()
		anim_clip_option_layout.addWidget(self._add_anim_clip_button)
		anim_clip_option_layout.addWidget(self._delete_all_clips_button)

		anim_clip_area = QtWidgets.QScrollArea(parent=self)
		anim_clip_area.setWidgetResizable(True)
		anim_clip_content = QtWidgets.QWidget(parent=self)
		anim_clip_area.setWidget(anim_clip_content)

		anim_clip_stretch_layout = QtWidgets.QVBoxLayout()
		anim_clip_stretch_layout.setSpacing(0)
		anim_clip_stretch_layout.setContentsMargins(0, 0, 0, 0)
		self._clips_layout = QtWidgets.QVBoxLayout()
		self._clips_layout.setSpacing(0)
		self._clips_layout.setContentsMargins(0, 0, 0, 0)
		anim_clip_stretch_layout.addLayout(self._clips_layout)
		anim_clip_content.setLayout(anim_clip_stretch_layout)
		anim_clip_stretch_layout.addStretch()

		main_layout.addLayout(anim_clip_option_layout)
		main_layout.addWidget(anim_clip_area)

		self._anim_clips_checkbox.toggled.connect(self._on_toggled_anim_clips_checkbox)
		self._add_anim_clip_button.clicked.connect(self._on_add_animation_clip_button_clicked)
		self._delete_all_clips_button.clicked.connect(self._on_delete_all_animation_clips_button_clicked)

	def refresh(self):

		pyqt.clear_layout(self._clips_layout)

		if not self._game_tools_fbx:
			return
		self._root_joint = self._game_tools_fbx.get_root_joint()
		self._export_path = self._game_tools_fbx.get_export_path()
		self._file_name = self._game_tools_fbx.get_file_name()

		if not self._root_joint:
			return
		export_node = fu.FbxExportNode.get()
		if not export_node:
			return

		for anim_clip_data in export_node.get_animation_clips(self._root_joint):
			anim_clip_name = anim_clip_data.get('title', None)
			if not anim_clip_name:
				continue
			self._add_animation_clip(anim_clip_name)

	def _add_animation_clip(self, clip_name):

		# TODO: Add code to avoid adding anim clips with duplicated names

		anim_clip_widget = AnimClipWidget(clip_name, parent=self._game_tools_fbx)
		self._clips_layout.addWidget(anim_clip_widget)

		return anim_clip_widget

	def _on_toggled_anim_clips_checkbox(self, flag):

		for i in range(self._clips_layout.count()):
			anim_clip_widget = self._clips_layout.itemAt(i).widget()
			anim_clip_widget.set_enabled(flag)

	def _on_add_animation_clip_button_clicked(self):

		if not self._root_joint:
			cmds.warning('Was not possible to add animation clip because not root joint is defined!')
			return

		export_node = fu.FbxExportNode.get() or fu.FbxExportNode.create()
		anim_clip_name = export_node.add_animation_clip(self._root_joint)
		if not anim_clip_name:
			cmds.warning('Was not possible to add new animation clip')
			return

		self._add_animation_clip(anim_clip_name)

	def _on_delete_all_animation_clips_button_clicked(self):

		if not self._root_joint:
			return

		export_node = fu.FbxExportNode.get()
		if not export_node:
			return

		export_node.delete_all_animation_clips()

		self.refresh()


class AnimClipWidget(QtWidgets.QFrame):
	def __init__(self, clip_name=None, parent=None):
		super(AnimClipWidget, self).__init__(parent)

		self._game_tools_fbx = parent
		self._clip_name = clip_name
		self._previous_name = clip_name

		self.setFixedHeight(150)
		self.window().setAttribute(QtCore.Qt.WA_AlwaysShowToolTips, True)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

		main_layout = QtWidgets.QVBoxLayout()
		self.setLayout(main_layout)

		self._export_checkbox = QtWidgets.QCheckBox(parent=self)
		self._title_line_edit = QtWidgets.QLineEdit(parent=self)
		self._title_line_edit.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Preferred)
		self._close_button = QtWidgets.QPushButton('X', parent=self)
		self._close_button.setMaximumWidth(20)
		close_layout = QtWidgets.QHBoxLayout()
		close_layout.setSpacing(2)
		close_layout.setContentsMargins(0, 0, 0, 0)
		close_layout.addWidget(self._export_checkbox)
		close_layout.addWidget(self._title_line_edit)
		close_layout.addWidget(self._close_button)

		options_layout_1 = QtWidgets.QHBoxLayout()
		options_layout_1.setSpacing(2)
		options_layout_1.setContentsMargins(0, 0, 0, 0)
		# self._start_at_origin_checkbox = QtWidgets.QCheckBox('Origin', parent=self)
		# self._start_at_frame_zero_checkbox = QtWidgets.QCheckBox('Frame 0', parent=self)
		# options_layout_1.addWidget(self._export_checkbox)
		# options_layout_1.addWidget(self._start_at_origin_checkbox)
		# options_layout_1.addWidget(self._start_at_frame_zero_checkbox)
		self._export_checkbox.setChecked(True)
		# self._start_at_origin_checkbox.setChecked(True)

		options_layout_2 = QtWidgets.QHBoxLayout()
		options_layout_2.setSpacing(2)
		options_layout_2.setContentsMargins(0, 0, 0, 0)
		self._up_button = QtWidgets.QPushButton(parent=self)
		up_pix = QtGui.QPixmap(':UVTkArrowRight.png')
		rm_up_pix = QtGui.QMatrix()
		rm_up_pix.rotate(-90)
		up_pix = up_pix.transformed(rm_up_pix)
		self._up_button.setIcon(up_pix)
		self._up_button.setStatusTip('Move Sequence Up')
		self._down_button = QtWidgets.QPushButton(parent=self)
		down_pix = QtGui.QPixmap(':UVTkArrowRight.png')
		rm_down_pix = QtGui.QMatrix()
		rm_down_pix.rotate(90)
		down_pix = down_pix.transformed(rm_down_pix)
		self._down_button.setIcon(down_pix)
		self._down_button.setStatusTip('Move Sequence Down')
		self._set_range_button = QtWidgets.QPushButton(parent=self)
		self._set_range_button.setIcon(QtGui.QIcon(':adjustTimeline.png'))
		self._set_range_button.setStatusTip('Set Range')
		self._playbast_button = QtWidgets.QPushButton(parent=self)
		self._playbast_button.setIcon(QtGui.QIcon(':playblast.png'))
		self._playbast_button.setStatusTip('Playblast')
		self._play_button = QtWidgets.QPushButton(parent=self)
		self._play_button.setIcon(QtGui.QIcon(':playClip.png'))
		self._play_button.setStatusTip('Play Sequence')
		self._export_button = QtWidgets.QPushButton('Export', parent=self)
		options_layout_2.addWidget(self._up_button)
		options_layout_2.addWidget(self._down_button)
		options_layout_2.addWidget(self._set_range_button)
		options_layout_2.addWidget(self._playbast_button)
		options_layout_2.addWidget(self._play_button)
		options_layout_2.addWidget(self._export_button)

		options_layout_3 = QtWidgets.QHBoxLayout()
		options_layout_3.setSpacing(2)
		options_layout_3.setContentsMargins(0, 0, 0, 0)
		start_frame_label = QtWidgets.QLabel('Start Frame:', parent=self)
		self._start_frame_line_edit = QtWidgets.QLineEdit(parent=self)
		self._start_frame_line_edit.setValidator(QtGui.QIntValidator())
		end_frame_label = QtWidgets.QLabel('End Frame:', parent=self)
		self._end_frame_line_edit = QtWidgets.QLineEdit(parent=self)
		self._end_frame_line_edit.setValidator(QtGui.QIntValidator())
		self._frame_rate_combo = QtWidgets.QComboBox(parent=self)
		self._frame_rate_combo.addItems(['30 FPS', '60 FPS', '120 FPS'])
		options_layout_3.addWidget(start_frame_label)
		options_layout_3.addWidget(self._start_frame_line_edit)
		options_layout_3.addWidget(end_frame_label)
		options_layout_3.addWidget(self._end_frame_line_edit)
		options_layout_3.addWidget(self._frame_rate_combo)

		options_layout_4 = QtWidgets.QHBoxLayout()
		options_layout_4.setSpacing(2)
		options_layout_4.setContentsMargins(0, 0, 0, 0)
		self._anim_layer_label = QtWidgets.QLabel('Animation Layer: ', parent=self)
		self._anim_layer_combo = QtWidgets.QComboBox(parent=self)
		self._anim_layer_combo.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Maximum)
		options_layout_4.addWidget(self._anim_layer_label)
		options_layout_4.addWidget(self._anim_layer_combo)

		main_layout.addLayout(close_layout)
		main_layout.addLayout(options_layout_1)
		main_layout.addLayout(options_layout_2)
		main_layout.addLayout(options_layout_3)
		main_layout.addLayout(options_layout_4)

		self.refresh()

		self._close_button.clicked.connect(self._on_close_button_clicked)
		self._title_line_edit.textChanged.connect(self._on_update_anim_clip)
		self._export_checkbox.toggled.connect(self._on_update_anim_clip)
		# self._start_at_origin_checkbox.toggled.connect(self._on_update_anim_clip)
		# self._start_at_frame_zero_checkbox.toggled.connect(self._on_update_anim_clip)
		self._start_frame_line_edit.textChanged.connect(self._on_update_anim_clip)
		self._end_frame_line_edit.textChanged.connect(self._on_update_anim_clip)
		self._frame_rate_combo.currentIndexChanged.connect(self._on_update_anim_clip)
		self._anim_layer_combo.currentIndexChanged.connect(self._on_update_anim_clip)
		self._set_range_button.clicked.connect(self._on_set_range_button_clicked)
		self._playbast_button.clicked.connect(self._on_playbast_button_clicked)
		self._play_button.clicked.connect(self._on_play_button_clicked)
		self._export_button.clicked.connect(self._on_export_button_clicked)
		self.customContextMenuRequested.connect(self._on_custom_context_menu_requested)

	def refresh(self):
		export_node = fu.FbxExportNode.get()
		if not export_node:
			self._clear()
			return

		if not self._game_tools_fbx:
			self._clear()
			return

		root_joint = self._game_tools_fbx.get_root_joint()
		anim_clip_data = export_node.get_animation_clip(root_joint, self._clip_name)

		with pyqt.block_signals(self._title_line_edit):
			self._title_line_edit.setText(anim_clip_data.get('title', 'Untitled'))
		with pyqt.block_signals(self._start_frame_line_edit):
			self._start_frame_line_edit.setText(str(anim_clip_data.get('startFrame', '')))
		with pyqt.block_signals(self._end_frame_line_edit):
			self._end_frame_line_edit.setText(str(anim_clip_data.get('endFrame', '')))
		with pyqt.block_signals(self._frame_rate_combo):
			self._frame_rate_combo.setCurrentIndex(self._frame_rate_combo.findText(anim_clip_data.get('frameRate', '')))
		with pyqt.block_signals(self._export_checkbox):
			self._export_checkbox.setChecked(anim_clip_data.get('enabled', True))
		# with pyqt.block_signals(self._start_at_origin_checkbox):
		# 	self._start_at_origin_checkbox.setChecked(anim_clip_data.get('startOrigin', True))
		# with pyqt.block_signals(self._start_at_frame_zero_checkbox):
		# 	self._start_at_frame_zero_checkbox.setChecked(anim_clip_data.get('frameZero', False))

		with pyqt.block_signals(self._anim_layer_combo):
			self._anim_layer_combo.clear()
			# TODO: Maybe we should filter display layers that are set with override mode?
			anim_layers = fu.all_anim_layers_ordered(include_base_animation=False)
			self._anim_layer_combo.addItems(['None'] + anim_layers)
			self._anim_layer_combo.setCurrentText(anim_clip_data.get('animLayer', 'None'))

	def set_enabled(self, flag):
		self._export_checkbox.setChecked(flag)

	def toggle_enabled(self):
		self._export_checkbox.setChecked(not self._export_checkbox.isChecked())

	def _clear(self):
		self._title_line_edit.setText('Untitled')
		self._start_frame_line_edit.setText('')
		self._end_frame_line_edit.setText('')
		self._frame_rate_combo.setCurrentIndex(0)
		self._export_checkbox.setChecked(False)
		# self._start_at_origin_checkbox.setChecked(False)
		# self._start_at_frame_zero_checkbox.setChecked(False)

	def _on_close_button_clicked(self):
		export_node = fu.FbxExportNode.get()
		if not export_node:
			return

		root_joint = self._game_tools_fbx.get_root_joint() if self._game_tools_fbx else None
		if not root_joint:
			return

		export_node.delete_animation_clip(root_joint, self._clip_name)

		self.setParent(None)
		self.deleteLater()

	def _on_update_anim_clip(self):

		root_joint = self._game_tools_fbx.get_root_joint() if self._game_tools_fbx else None
		if not root_joint:
			return

		export_node = fu.FbxExportNode.get()
		if not export_node:
			return

		anim_clip_data = fu.FbxExportNode.ANIM_CLIP_DATA.copy()
		anim_clip_data['title'] = self._title_line_edit.text()
		# anim_clip_data['path'] = self._export_path_line_edit.text()
		anim_clip_data['enabled'] = self._export_checkbox.isChecked()
		# anim_clip_data['startOrigin'] = self._start_at_origin_checkbox.isChecked()
		# anim_clip_data['frameZero'] = self._start_at_frame_zero_checkbox.isChecked()
		anim_clip_data['frameRate'] = self._frame_rate_combo.currentText()
		anim_clip_data['startFrame'] = int(self._start_frame_line_edit.text())
		anim_clip_data['endFrame'] = int(self._end_frame_line_edit.text())
		anim_layer = self._anim_layer_combo.currentText()
		anim_clip_data['animLayer'] = anim_layer if anim_layer and anim_layer != 'None' else ''

		export_node.update_animation_clip(root_joint, self._previous_name, anim_clip_data)
		self._previous_name = anim_clip_data['title']

	def _on_delete_anim_clip(self):
		export_node = fu.FbxExportNode.get()
		if not export_node:
			return

		result = export_node.delete_animation_clip(self._root_joint, self._clip_name)
		if not result:
			return

		self.setParent(None)
		self.deleteLater()

	def _on_set_range_button_clicked(self):

		start_frame, end_frame = int(self._start_frame_line_edit.text()), int(self._end_frame_line_edit.text())
		cmds.playbackOptions(
			animationStartTime=start_frame, minTime=start_frame, animationEndTime=end_frame, maxTime=end_frame)
		cmds.currentTime(start_frame, edit=True)

	def _on_playbast_button_clicked(self):

		start_frame, end_frame = int(self._start_frame_line_edit.text()), int(self._end_frame_line_edit.text())
		fu.create_mgear_playblast(
			folder=self._export_path_line_edit.text(), start_frame=start_frame, end_frame=end_frame)

	def _on_play_button_clicked(self):
		start_frame, end_frame = int(self._start_frame_line_edit.text()), int(self._end_frame_line_edit.text())
		cmds.playbackOptions(
			animationStartTime=start_frame, minTime=start_frame, animationEndTime=end_frame, maxTime=end_frame)
		if cmds.play(query=True, state=True):
			cmds.play(state=False)
		else:
			cmds.play(forward=True)

	def _on_export_button_clicked(self):

		root_joint = self._game_tools_fbx.get_root_joint() if self._game_tools_fbx else None
		if not root_joint:
			cmds.error('No valid root joint defined!')
			return False

		export_path = self._game_tools_fbx.get_export_path() if self._game_tools_fbx else ''
		file_name = self._game_tools_fbx.get_file_name() if self._game_tools_fbx else ''
		remove_namespace = self._game_tools_fbx.get_remove_namespace() if self._game_tools_fbx else False
		scene_clean = self._game_tools_fbx.get_scene_clean() if self._game_tools_fbx else False
		anim_layer = self._anim_layer_combo.currentText()
		anim_layer = anim_layer if anim_layer and anim_layer != 'None' else ''

		export_kwargs = {
			'startFrame': int(self._start_frame_line_edit.text()),
			'endFrame': int(self._end_frame_line_edit.text()),
			'enabled': self._export_checkbox.isChecked(),
			# 'startOrigin': self._start_at_origin_checkbox.isChecked(),
			# 'frameZero': self._start_at_frame_zero_checkbox.isChecked(),
			'frameRate': self._frame_rate_combo.currentText(),
			'file_path': export_path,
			'file_name': '{}_{}'.format(file_name, self._title_line_edit.text().replace(' ', '_')),
			'remove_namespace': remove_namespace,
			'scene_clean': scene_clean,
			'anim_layer': anim_layer
		}
		return fu.export_animation_clip(root_joint, **export_kwargs)

	def _on_custom_context_menu_requested(self, pos):

		context_menu = QtWidgets.QMenu(parent=self)
		delete_anim_clip_action = context_menu.addAction('Delete')
		playblast_menu = QtWidgets.QMenu('Playblast', parent=self)
		playblast_25_action = playblast_menu.addAction('25%')
		playblast_50_action = playblast_menu.addAction('50%')
		playblast_75_action = playblast_menu.addAction('75%')
		playblast_100_action = playblast_menu.addAction('100%')
		playblast_menu.addSeparator()
		open_playblasts_folder_action = playblast_menu.addAction('Open in Explorer')

		context_menu.addAction(delete_anim_clip_action)
		context_menu.addMenu(playblast_menu)

		delete_anim_clip_action.triggered.connect(self._on_delete_anim_clip)
		playblast_25_action.triggered.connect(partial(fu.create_mgear_playblast, scale=25))
		playblast_50_action.triggered.connect(partial(fu.create_mgear_playblast, scale=50))
		playblast_75_action.triggered.connect(partial(fu.create_mgear_playblast, scale=75))
		playblast_100_action.triggered.connect(partial(fu.create_mgear_playblast, scale=100))
		open_playblasts_folder_action.triggered.connect(fu.open_mgear_playblast_folder)

		context_menu.exec_(self.mapToGlobal(pos))
