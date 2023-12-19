import os
import json

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from mgear.vendor.Qt import QtGui, QtWidgets
from mgear.core import pyqt, widgets
from mgear.shifter.rig_builder import builder

builder.setup_pyblish()


class RigBuilderUI(MayaQWidgetDockableMixin, QtWidgets.QDialog, pyqt.SettingsMixin):
    """
    A UI class for building mGear rigs from .sgt files.
    """

    def __init__(self):
        super(RigBuilderUI, self).__init__()
        self.setWindowTitle("mGear Rig Builder")
        self.setMinimumWidth(400)
        self.setAcceptDrops(True)
        self.resize(550, 650)

        self.builder = builder.RigBuilder()
        self.create_layout()
        self.create_connections()

    def create_layout(self):
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        # Output Folder UI
        output_folder_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(output_folder_layout)

        self.output_folder_line_edit = QtWidgets.QLineEdit()
        self.output_folder_button = widgets.create_button(icon="mgear_folder", width=25)

        output_folder_layout.addWidget(QtWidgets.QLabel("Output Folder"))
        output_folder_layout.addWidget(self.output_folder_line_edit)
        output_folder_layout.addWidget(self.output_folder_button)

        # Run Validators checkboxes
        run_validators_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(run_validators_layout)

        run_label = QtWidgets.QLabel("Run Pyblish Validators")
        self.run_validators_checkbox = QtWidgets.QCheckBox()
        self.run_validators_checkbox.setChecked(True)
        run_validators_layout.addWidget(run_label)
        run_validators_layout.addWidget(self.run_validators_checkbox)
        run_validators_layout.addStretch()

        self.results_label = QtWidgets.QLabel("Open Results Pop-Up")
        self.results_popup_checkbox = QtWidgets.QCheckBox()
        self.results_popup_checkbox.setChecked(True)
        run_validators_layout.addWidget(self.results_label)
        run_validators_layout.addWidget(self.results_popup_checkbox)
        run_validators_layout.addStretch()

        self.publish_label = QtWidgets.QLabel("Publish Passed Rigs Only")
        self.publish_passed_checkbox = QtWidgets.QCheckBox()
        self.publish_passed_checkbox.setChecked(True)
        run_validators_layout.addWidget(self.publish_label)
        run_validators_layout.addWidget(self.publish_passed_checkbox)
        run_validators_layout.addStretch()

        # File Table UI
        self.table_widget = QtWidgets.QTableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels([".sgt File", "Output Name"])

        self.table_widget.setEditTriggers(QtWidgets.QAbstractItemView.AllEditTriggers)
        # Resize the first column to fit its content
        self.table_widget.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeToContents
        )
        # Make the last column stretch to fill the remaining space
        self.table_widget.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )

        self.layout.addWidget(self.table_widget)

        # Add, Remove, and Build buttons
        self.add_button = QtWidgets.QPushButton("Add")
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.build_button = QtWidgets.QPushButton("Build")

        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.remove_button)
        self.layout.addWidget(self.build_button)

    def create_connections(self):
        self.output_folder_button.clicked.connect(self.on_output_folder_clicked)
        self.run_validators_checkbox.stateChanged.connect(
            self.on_run_validators_checkbox_changed
        )
        self.add_button.clicked.connect(self.on_add_button_clicked)
        self.remove_button.clicked.connect(self.on_remove_button_clicked)
        self.build_button.clicked.connect(self.on_build_button_clicked)

    def on_output_folder_clicked(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder"
        )
        if folder_path:
            self.output_folder_line_edit.setText(folder_path)

    def on_run_validators_checkbox_changed(self):
        runState = self.run_validators_checkbox.isChecked()
        self.results_label.setEnabled(runState)
        self.results_popup_checkbox.setEnabled(runState)
        self.publish_label.setEnabled(runState)
        self.publish_passed_checkbox.setEnabled(runState)

    def on_add_button_clicked(self):
        file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Select .sgt Files", "", "*.sgt"
        )
        if file_paths:
            for file_path in file_paths:
                self.add_file(file_path)

    def on_remove_button_clicked(self):
        """Remove selected .sgt files from the list."""
        selected_ranges = self.table_widget.selectedRanges()

        # Get unique rows to be removed
        rows_to_remove = set()
        for selected_range in selected_ranges:
            rows_to_remove.update(
                range(selected_range.topRow(), selected_range.bottomRow() + 1)
            )

        # Sort in reverse so that removing lower index doesn't affect higher index
        for row in sorted(rows_to_remove, reverse=True):
            self.table_widget.removeRow(row)

    def on_build_button_clicked(self):
        data = self.collect_table_data()
        validate = self.run_validators_checkbox.isChecked()
        passed_rigs_only = self.publish_passed_checkbox.isChecked()
        results_dict = self.builder.execute_build_logic(
            data, validate=validate, passed_only=passed_rigs_only
        )
        if (
            self.run_validators_checkbox.isChecked()
            and self.results_popup_checkbox.isChecked()
        ):
            self.create_results_popup(results_dict)

    def collect_table_data(self):
        """Collect data from the table widget and output as JSON.

        Returns:
            str: A JSON string containing the collected data.
        """
        data = {}
        row_count = self.table_widget.rowCount()
        data["output_folder"] = self.output_folder_line_edit.text().strip()
        data["rows"] = []

        for i in range(row_count):
            file_path_item = self.table_widget.item(i, 0)
            output_name_item = self.table_widget.item(i, 1)

            file_path = file_path_item.text().strip() if file_path_item else ""
            output_name = output_name_item.text().strip() if output_name_item else ""

            data["rows"].append({"file_path": file_path, "output_name": output_name})

        return json.dumps(data)

    def add_file(self, file_path):
        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)

        # For .sgt file path
        file_item = QtWidgets.QTableWidgetItem(file_path)
        self.table_widget.setItem(row_position, 0, file_item)

        # For Output Name
        output_name = os.path.splitext(os.path.basename(file_path))[0]
        output_item = QtWidgets.QTableWidgetItem(output_name)
        self.table_widget.setItem(row_position, 1, output_item)

    def create_results_popup(self, results_dict):
        popup = ResultsPopupDialog(results_dict)
        popup.exec()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            file_path = str(url.toLocalFile())
            if file_path.lower().endswith(".sgt"):
                self.add_file(file_path)


class ResultsPopupDialog(QtWidgets.QDialog):
    def __init__(self, results):
        super(ResultsPopupDialog, self).__init__()
        self.setWindowTitle("Validator Results")
        self.setSizeGripEnabled(True)
        self.resize(800, 400)

        self.results_dict = results
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.create_results_view()

    def create_results_view(self):
        self.results_tree = QtWidgets.QTreeView()
        self.results_tree.setAlternatingRowColors(True)
        self.layout.addWidget(self.results_tree)

        model = QtGui.QStandardItemModel()
        model.setHorizontalHeaderLabels(["Rig Name", "Check Name", "Result"])
        self.results_tree.setModel(model)

        for rig_name, checks_dict in self.results_dict.items():
            self.add_result_entry(model, rig_name, checks_dict)

        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            self.results_tree.setExpanded(idx, True)

    def add_result_entry(self, model, rig_name, checks_dict):
        group_root = QtGui.QStandardItem(rig_name)
        model.appendRow(group_root)

        for i, (check_name, check_data) in enumerate(checks_dict.items()):
            result_string = "Passed" if check_data.get("success") else "Failed"
            error = check_data.get("error")
            if error is not None:
                result_string += " - {}".format(error)

            check_item = QtGui.QStandardItem(check_name)
            result_item = QtGui.QStandardItem(result_string)
            group_root.setChild(i, 1, check_item)
            group_root.setChild(i, 2, result_item)


def openRigBuilderUI(*args):
    pyqt.showDialog(RigBuilderUI, dockable=True)


if __name__ == "__main__":
    window = RigBuilderUI()
    window.show()
