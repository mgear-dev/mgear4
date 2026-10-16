"""Shifter guide import options dialog.

One window that asks how to import a guide template: as a new guide, as a
build, or added under the selected guide element, whole or in part, with
or without snapping. Also hosts the component checklist shared with the
Guide Template Manager.
"""

from maya import cmds

from mgear.core import pyqt
from mgear.shifter import io

from mgear.vendor.Qt import QtWidgets
from mgear.vendor.Qt import QtCore

IMPORT_STYLE = "background-color: #4a7c4e;"
SNAP_STYLE = "background-color: #4a6c7e;"
_HINT_STYLE = "color: #aaa;"


# =================================================================
# COMPONENT CHECKLIST
# =================================================================


class ComponentChecklist(QtWidgets.QWidget):
    """Checkable tree of the components of a guide template.

    Checking a component also checks its children.

    Args:
        components (list): Component info dicts from
            ``mgear.shifter.io.get_template_components``.
        parent (QWidget, optional): Parent widget.
    """

    selection_changed = QtCore.Signal()

    def __init__(self, components, parent=None):
        super(ComponentChecklist, self).__init__(parent)

        self._item_map = {}
        # Components matching the filter, None when there is no filter
        self._matches = None

        self.filter_input = QtWidgets.QLineEdit()
        self.filter_input.setPlaceholderText("Filter components...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.setToolTip(
            "Show only the components whose name or type contains this "
            "text. Their parents stay visible."
        )

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Component", "Type"])
        self.tree.setColumnWidth(0, int(pyqt.dpi_scale(250)))
        self.tree.setStyleSheet(
            "QTreeWidget::indicator:unchecked {"
            "    border: 1px solid #888;"
            "    background-color: #333;"
            "    width: 14px;"
            "    height: 14px;"
            "}"
            "QTreeWidget::indicator:checked {"
            "    border: 1px solid #5285a6;"
            "    background-color: #5285a6;"
            "    width: 14px;"
            "    height: 14px;"
            "}"
        )

        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.select_all_btn.setToolTip(
            "Check every component, or only the ones the filter finds."
        )
        self.deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        self.deselect_all_btn.setToolTip(
            "Uncheck every component, or only the ones the filter finds."
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.filter_input)
        layout.addWidget(self.tree)
        sel_layout = QtWidgets.QHBoxLayout()
        sel_layout.addWidget(self.select_all_btn)
        sel_layout.addWidget(self.deselect_all_btn)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        self._populate_tree(components)

        self.filter_input.textChanged.connect(self.set_filter)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.select_all_btn.clicked.connect(self.select_all)
        self.deselect_all_btn.clicked.connect(self.deselect_all)

    def _populate_tree(self, components):
        """Build the component tree with checkboxes.

        Args:
            components (list): Component info dicts.
        """
        children_of = {}
        for comp in components:
            children_of.setdefault(comp.get("parent"), []).append(comp)

        for comp in children_of.get(None, []):
            self._add_component(comp, self.tree, children_of)

        self.tree.expandAll()

    def _add_component(self, comp, parent_item, children_of):
        """Add a component item and its children to the tree.

        Args:
            comp (dict): Component info dict.
            parent_item (QTreeWidgetItem or QTreeWidget): Parent item.
            children_of (dict): Components by parent name.
        """
        item = QtWidgets.QTreeWidgetItem(parent_item)
        item.setText(0, comp["name"])
        item.setText(1, comp["comp_type"])
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(0, QtCore.Qt.Unchecked)

        self._item_map[comp["name"]] = item

        for child in children_of.get(comp["name"], []):
            self._add_component(child, item, children_of)

    def _on_item_changed(self, item, column):
        """Check or uncheck the children of a changed item.

        Args:
            item (QTreeWidgetItem): Changed item.
            column (int): Changed column.
        """
        if column != 0:
            return
        self.tree.blockSignals(True)
        self._set_children_state(item, item.checkState(0))
        self.tree.blockSignals(False)
        self.selection_changed.emit()

    def _set_children_state(self, item, state):
        """Set the check state of all the children of an item.

        Args:
            item (QTreeWidgetItem): Parent item.
            state (Qt.CheckState): Check state.
        """
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self._set_children_state(child, state)

    def set_checked(self, names, checked=True):
        """Set the check state of some components and their children.

        Args:
            names (list): Component names.
            checked (bool, optional): Check state to set.
        """
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        self.tree.blockSignals(True)
        for name in names:
            item = self._item_map.get(name)
            if item:
                item.setCheckState(0, state)
                self._set_children_state(item, state)
        self.tree.blockSignals(False)
        self.selection_changed.emit()

    def set_filter(self, text):
        """Show only the components whose name or type contains a text.

        The parents of the matches stay visible to keep the hierarchy.
        Hidden components keep their check state.

        Args:
            text (str): Text to search, case insensitive. Empty shows all.
        """
        text = text.strip().lower()
        if not text:
            self._matches = None
            for item in self._item_map.values():
                item.setHidden(False)
            return

        self._matches = []
        for name, item in self._item_map.items():
            item.setHidden(True)
            if text in name.lower() or text in item.text(1).lower():
                self._matches.append(name)
        for name in self._matches:
            item = self._item_map[name]
            while item:
                item.setHidden(False)
                item = item.parent()

    def _get_filtered(self):
        """Get the components Select All and Deselect All act on.

        Returns:
            list: The filter matches, or all the components.
        """
        if self._matches is None:
            return list(self._item_map)
        return list(self._matches)

    def select_all(self):
        """Check all the components, or the filter matches."""
        self.set_checked(self._get_filtered(), True)

    def deselect_all(self):
        """Uncheck all the components, or the filter matches."""
        self.set_checked(self._get_filtered(), False)

    def get_selected_components(self):
        """Get the checked component names.

        Returns:
            list: Component names, in tree order.
        """
        return [
            name
            for name, item in self._item_map.items()
            if item.checkState(0) == QtCore.Qt.Checked
        ]

    def get_root_components(self):
        """Get the checked components whose parent is not checked.

        ``draw_guide`` needs only these, and finds their children itself.

        Returns:
            list: Component names, in tree order.
        """
        roots = []
        for name, item in self._item_map.items():
            if item.checkState(0) != QtCore.Qt.Checked:
                continue
            parent = item.parent()
            if not parent or parent.checkState(0) != QtCore.Qt.Checked:
                roots.append(name)
        return roots


# =================================================================
# GUIDE IMPORT DIALOG
# =================================================================


class GuideImportDialog(QtWidgets.QDialog):
    """Ask how to import a guide template.

    The choice page offers Import, Build (optional) and Cancel. With a
    target guide element it also offers Add, Add & Snap and Partial...,
    which shows a component checklist page in the same window.

    Args:
        file_name (str): Template file name shown in the dialog.
        components (list, optional): Template components for the
            partial page, from ``io.get_template_components``.
        target_name (str, optional): Name of the selected guide element.
            If None, the add options are hidden.
        allow_build (bool, optional): If True, shows the Build button.
        parent (QWidget, optional): Parent widget.
    """

    def __init__(
        self,
        file_name,
        components=None,
        target_name=None,
        allow_build=True,
        parent=None,
    ):
        super(GuideImportDialog, self).__init__(parent)

        self._file_name = file_name
        self._target_name = target_name
        self._action = io.IMPORT_CANCEL
        self._partial = None
        self._snap = False

        self.stack = QtWidgets.QStackedWidget()
        self.import_btn = self._button(
            "Import", "Import the template as a new guide.", IMPORT_STYLE
        )
        self.build_btn = None
        if allow_build:
            self.build_btn = self._button(
                "Build",
                "Build the rig from the template without drawing the guide.",
            )
        self.cancel_btn = self._button("Cancel", "Close without importing.")

        # Add options, only with a target
        self.add_btn = None
        self.add_snap_btn = None
        self.partial_btn = None
        self.checklist = None
        self.back_btn = None
        self.add_selected_btn = None
        self.add_selected_snap_btn = None

        self.setWindowTitle("mGear Guide Import")
        self.setMinimumWidth(int(pyqt.dpi_scale(420)))
        if cmds.about(ntOS=True):
            # Clear the flag, XOR would add it on Qt6 where it is off
            self.setWindowFlags(
                self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
            )

        self._create_choice_page()
        if target_name:
            self._create_add_options(components or [])

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.stack)

    # =================================================================
    # UI SETUP
    # =================================================================

    def _button(self, label, tooltip, style=None):
        """Create a push button with a tooltip.

        Args:
            label (str): Button label.
            tooltip (str): Button tooltip.
            style (str, optional): Style sheet of the button.

        Returns:
            QPushButton: The button.
        """
        button = QtWidgets.QPushButton(label)
        button.setToolTip(tooltip)
        button.setAutoDefault(False)
        if style:
            button.setStyleSheet(style)
        return button

    def _label(self, text, hint=False):
        """Create a label.

        Args:
            text (str): Label text, rich text allowed.
            hint (bool, optional): If True, uses the dimmed hint style.

        Returns:
            QLabel: The label.
        """
        label = QtWidgets.QLabel(text)
        if hint:
            label.setStyleSheet(_HINT_STYLE)
        return label

    def _create_choice_page(self):
        """Create the choice page with the new guide buttons."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label("<b>{}</b>".format(self._file_name)))

        new_row = QtWidgets.QHBoxLayout()
        new_row.addWidget(self.import_btn)
        if self.build_btn:
            new_row.addWidget(self.build_btn)
        new_row.addStretch()

        if self._target_name:
            layout.addWidget(
                self._label(
                    "Selected guide element: <b>{}</b>".format(self._target_name)
                )
            )
            layout.addWidget(self._label("New guide", hint=True))
        else:
            layout.addWidget(
                self._label(
                    "Nothing selected. The template will be drawn as a new " "guide.",
                    hint=True,
                )
            )
            new_row.addWidget(self.cancel_btn)
        layout.addLayout(new_row)
        self.stack.addWidget(page)

        self.import_btn.clicked.connect(lambda: self._finish(io.IMPORT_NEW))
        if self.build_btn:
            self.build_btn.clicked.connect(lambda: self._finish(io.IMPORT_BUILD))
        self.cancel_btn.clicked.connect(self.reject)

    def _create_add_options(self, components):
        """Create the add buttons and the partial page for the target.

        Args:
            components (list): Template components for the checklist.
        """
        target = self._target_name

        self.add_btn = self._button(
            "Add",
            "Add the whole template under {}, keeping the template "
            "positions.".format(target),
        )
        self.add_snap_btn = self._button(
            "Add && Snap",
            "Add the whole template under {0} and move the new components "
            "so the first root sits on {0}.".format(target),
            SNAP_STYLE,
        )
        self.partial_btn = self._button(
            "Partial...",
            "Choose which components of the template to add under "
            "{}.".format(target),
        )
        self.partial_btn.setEnabled(bool(components))

        choice_layout = self.stack.widget(0).layout()
        choice_layout.addWidget(self._label("Add to {}".format(target), hint=True))
        add_row = QtWidgets.QHBoxLayout()
        add_row.addWidget(self.add_btn)
        add_row.addWidget(self.add_snap_btn)
        add_row.addWidget(self.partial_btn)
        add_row.addStretch()
        add_row.addWidget(self.cancel_btn)
        choice_layout.addLayout(add_row)

        # Partial page
        self.checklist = ComponentChecklist(components)
        self.back_btn = self._button("Back", "Return to the import options.")
        self.add_selected_btn = self._button(
            "Add Selected",
            "Add the checked components (and their children) under "
            "{}.".format(target),
            IMPORT_STYLE,
        )
        self.add_selected_snap_btn = self._button(
            "Add Selected && Snap",
            "Add the checked components under {0} and move them so the "
            "first root sits on {0}.".format(target),
            SNAP_STYLE,
        )
        self._update_partial_buttons()

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(
            self._label(
                "<b>{}</b> - Add under <b>{}</b>".format(self._file_name, target)
            )
        )
        layout.addWidget(
            self._label(
                "Pick the components to add. Their children are included.",
                hint=True,
            )
        )
        layout.addWidget(self.checklist, stretch=1)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.back_btn)
        row.addStretch()
        row.addWidget(self.add_selected_btn)
        row.addWidget(self.add_selected_snap_btn)
        layout.addLayout(row)
        self.stack.addWidget(page)

        self.add_btn.clicked.connect(lambda: self._finish(io.IMPORT_ADD))
        self.add_snap_btn.clicked.connect(
            lambda: self._finish(io.IMPORT_ADD, snap=True)
        )
        self.partial_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.add_selected_btn.clicked.connect(lambda: self._finish_partial())
        self.add_selected_snap_btn.clicked.connect(
            lambda: self._finish_partial(snap=True)
        )
        self.checklist.selection_changed.connect(self._update_partial_buttons)

    # =================================================================
    # RESULT
    # =================================================================

    def _update_partial_buttons(self):
        """Enable the partial Add buttons only when something is checked."""
        enabled = bool(self.checklist.get_selected_components())
        self.add_selected_btn.setEnabled(enabled)
        self.add_selected_snap_btn.setEnabled(enabled)

    def _finish(self, action, partial=None, snap=False):
        """Store the choice and close the dialog.

        Args:
            action (str): One of the ``io.IMPORT_*`` constants.
            partial (list, optional): Root components to add.
            snap (bool, optional): If True, snap the new roots.
        """
        self._action = action
        self._partial = partial
        self._snap = snap
        self.accept()

    def _finish_partial(self, snap=False):
        """Add the checked components.

        Args:
            snap (bool, optional): If True, snap the new roots.
        """
        roots = self.checklist.get_root_components()
        if roots:
            self._finish(io.IMPORT_ADD, partial=roots, snap=snap)

    def get_result(self):
        """Get the chosen import options.

        Returns:
            tuple: The action (one of the ``io.IMPORT_*`` constants), the
                root components to add or None, and the snap flag.
        """
        return self._action, self._partial, self._snap


def ask_import_choice(file_name, components, target_name, allow_build):
    """Show the guide import dialog and wait for the choice.

    Args:
        file_name (str): Template file name shown in the dialog.
        components (list): Template components for the partial page.
        target_name (str): Name of the selected guide element, or None.
        allow_build (bool): If True, offers to build the rig.

    Returns:
        tuple: The action (one of the ``io.IMPORT_*`` constants), the root
            components to add or None, and the snap flag.
    """
    dialog = GuideImportDialog(
        file_name,
        components=components,
        target_name=target_name,
        allow_build=allow_build,
        parent=pyqt.maya_main_window(),
    )
    dialog.exec_()
    result = dialog.get_result()
    dialog.deleteLater()
    return result
