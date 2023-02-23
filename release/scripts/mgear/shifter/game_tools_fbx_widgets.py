import copy
import weakref

from mgear.core import pyqt
from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore
from mgear.vendor.Qt import QtGui

import maya.cmds as cmds

# TODO: Remove following dependencies
import maya.app.flux.core as fx
from maya.app.flux.core import pix
from MASH.itemStyle import *

ROW_HEIGHT = 30


class NodeClass(object):
	def __init__(self, node_name, node_type, is_partition, icon, enabled, network_enabled):
		super(NodeClass, self).__init__()

		self._node_name = node_name
		self._node_type = node_type
		self._is_partition = is_partition
		self._icon = icon
		self._enabled = enabled
		self._network_enabled = network_enabled
		self._label_color = QtGui.QColor(241, 90, 91)
		color = QtGui.QColor(0, 0, 0)
		color.setNamedColor('#444444')
		if self._is_partition:
			color.setNamedColor('#5d5d5d')
		self._background_color = color
		self._tooltip = None

	def __repr__(self):
		return 'NODE - {} {}'.format(self._node_name, self._node_type)

	@property
	def node_name(self):
		return self._node_name

	@node_name.setter
	def node_name(self, value):
		self._node_name = value

	@property
	def node_type(self):
		return self._node_type

	@property
	def is_partition(self):
		return self._is_partition

	@property
	def icon(self):
		return self._icon

	@property
	def enabled(self):
		return self._enabled

	@property
	def network_enabled(self):
		return self._network_enabled

	@property
	def label_color(self):
		return self._label_color

	@label_color.setter
	def label_color(self, value):
		self._label_color = value

	@property
	def background_color(self):
		return self._background_color


class OutlinerTreeView(QtWidgets.QTreeWidget):

	EXPAND_WIDTH = pix(60)

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
		self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

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

	@property
	def last_hit_action(self):
		return self._last_hit_action

	@last_hit_action.setter
	def last_hit_action(self, value):
		self._last_hit_action = value

	def mousePressEvent(self, event):
		"""Triggers actions based on mouse press"""

		self._button_pressed = event.button()

		if event.button() == QtCore.Qt.LeftButton:
			index = self.indexAt(event.pos())
			if index.row() == -1:
				self._action_button_pressed = False
				super(OutlinerTreeView, self).mousePressEvent(event)
				self.clearSelection()
				self.window().repaint()
				return

			item = self._get_corresponding_item(index)
			action = self._get_current_action(event.pos(), item)

			self.setCurrentItem(item)
			if item.node.node_type != 'Partition':
				self._selection_parent = item.parent().get_name()
				self._selection_node = item.get_name()
			self.selectionModel().setCurrentIndex(index, QtCore.QItemSelectionModel.NoUpdate)

			if action is not None:
				if action == 'ExpandCollapse':
					if item.node.node_type == 'Partition':
						self._toggle_expand_collapse()
			event.accept()
		elif event.button() == QtCore.Qt.MiddleButton:
			super(OutlinerTreeView, self).mousePressEvent(event)

		self.clearSelection()
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

	def populate_items(self, add_callbacks=True):

		if add_callbacks:
			self.cleanup()

		partitions = {
			'Body': ['Boy_Mesh'],
			'Props': ['Knife']
		}

		for partition_name, partition_data in partitions.items():
			partition_item = self._create_partition_item(partition_name)
			partition_item.setFlags(partition_item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDropEnabled)
			partition_item.setFlags(partition_item.flags() & ~QtCore.Qt.ItemIsDragEnabled)
			self.addTopLevelItem(partition_item)

			for partition_node in partition_data:
				child = self._add_partition_item(partition_node, partition_item)
				child.setFlags(child.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDropEnabled)
				partition_item.addChild(child)
				if add_callbacks:
					pass


	def cleanup(self):
		self._registered_node_callbacks = list()

	def _create_partition_item(self, partition):

		node_icon = pyqt.get_icon('mgear_package')
		partition_node = NodeClass(partition, 'Partition', True, node_icon, True, True)

		item = TreeItem(partition_node, partition, True, None)

		return item

	def _add_partition_item(self, node, partition_item):

		node_icon = pyqt.get_icon('mgear_box')
		item_node = NodeClass(node, 'Geometry', False, node_icon, True, partition_item.node.network_enabled)

		item = TreeItem(item_node, '', False, partition_item)

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

	def _toggle_expand_collapse(self):
		"""Expands and collaps the partition nodes"""

		item = self.currentItem()
		self.collapseItem(item) if item.isExpanded() else self.expandItem(item)


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
		new_name = cmds.rename(self.get_name(), name)
		self.node.node_name = new_name

	def get_node_type(self):
		return self.node.node_type

	def get_icon(self):
		return self.node.icon

	def get_background_color(self):
		return self.node.background_color

	def get_window_background_color(self):
		return QtGui.QColor(43, 43, 43)

	def get_inactive_color(self):
		return QtGui.QColor(150, 150, 150)

	def is_enabled(self):
		return self.node.enabled

	def network_enabled(self):
		return self.parent().node.network_enabled

	def is_partition(self):
		return self.node.is_partition

	def get_label_color(self):
		return self.node.label_color

	def get_action_button_count(self):
		return 7 if self.node.is_partition else 3

	def has_enable_toggle(self):
		return self._show_enabled

	def get_action_button(self, index):
		if self.node.is_partition:
			if index >= 0 and index <= 6:
				return ['Enabled', None, 'Add', None, None, None, None][index]
		else:
			if index >= 0 and index <= 2:
				return ['Enabled', None, None][index]

		return None


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
			option.backgroundBrush = qt.QBrush(QtCore.Qt.red)

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
		"""Draws the cell background color/image"""

		if self.item.is_partition() or self.item.network_enabled():
			color = self._highlight_color if self._is_highlighted else self.item.get_background_color()
			self._painter.fillRect(self._rect, color)
		else:
			pixmap = self.DISABLED_HIGHLIGHT_IMAGE if self._is_highlighted else self.DISABLED_BACKGROUND_IMAGE
			self.painter.drawTiledPixmap(self._rect, pixmap, QtCore.QPoint(self._rect.left(), 0))

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
		"""Draws the expansion arrow on the nodes that need it"""

		self._painter.save()
		arrow = None
		old_brush = self._painter.brush()
		if self.item.is_partition():
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
		"""Draws node name"""

		old_pen = self._painter.pen()
		draw_enabled = True
		if not self.item.node.is_partition and not self.item.network_enabled():
			draw_enabled = False
		if self.item.node.enabled and draw_enabled:
			self._painter.setPen(QtGui.QPen(self.parent().palette().text().color(), pix(1)))
		else:
			self._painter.setPen(QtGui.QPen(self.item.get_inactive_color(), pix(1)))
		text_rect = copy.deepcopy(self._rect)
		text_rect.setBottom(text_rect.bottom() + pix(2))
		text_rect.setLeft(text_rect.left() + pix(40) + self.ICON_PADDING)
		text_rect.setRight(text_rect.right() - pix(11))
		self._painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.item.get_name())
		self._painter.setPen(old_pen)
		old_pen = self._painter.pen()

		return text_rect

	def _draw_icon(self, text_rect):
		"""Draws the node icon"""

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
			if not self.item.node.is_partition and not self.item.network_enabled():
				draw_enabled = False
			if not self.item.node.enabled or not draw_enabled:
				self._painter.setOpacity(0.5)
			self._painter.drawPixmap(new_rect, icon)

	def _draw_action(self, action_name, pixmap, left, top):
		"""Draws the icons for this node"""

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
		"""Draws the icons, buttons and tags on the right hand side of the cell"""

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
				if not self.item.is_partition() and not self.item.network_enabled():
					pixmap = self.INACTIVE_ENABLED_IMAGE
				checked = self.item.is_enabled()
				if not checked:
					pixmap = self.DISABLED_IMAGE
				if self._is_highlighted and checked:
					pixmap = self.ENABLED_SELECTED_IMAGE
			elif action_name == 'Add':
				pixmap = self.ADD_IMAGE

			start += self.ACTION_WIDTH + extra_padding
			self._draw_action(action_name, pixmap, self._rect.right() - start, top)





class AnimClipWidget(QtWidgets.QWidget):
	def __init__(self, parent=None):
		super(AnimClipWidget, self).__init__(parent)
