from mgear.core import pyqt
from mgear.vendor.Qt import QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import os
import json


from . import builder


class RigBuilderUI(
    MayaQWidgetDockableMixin, QtWidgets.QDialog, pyqt.SettingsMixin
):
    """
    A UI class for building mGear rigs from .sgt files.
    """

    def __init__(self):
        super(RigBuilderUI, self).__init__()
        self.setWindowTitle("mGear Rig Builder")
        self.setMinimumWidth(400)
        self.setAcceptDrops(True)
        self.resize(550, 650)

        self.layout = QtWidgets.QVBoxLayout()

        # Output Folder UI
        self.output_folder_line_edit = QtWidgets.QLineEdit()
        self.output_folder_button = QtWidgets.QPushButton("Set Output Folder")
        self.output_folder_button.clicked.connect(self.set_output_folder)

        self.layout.addWidget(QtWidgets.QLabel("Output Folder:"))
        self.layout.addWidget(self.output_folder_line_edit)
        self.layout.addWidget(self.output_folder_button)

        # File Table UI
        self.table_widget = QtWidgets.QTableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(
            [".sgt File", "Output Name"]
        )
        self.table_widget.setEditTriggers(
            QtWidgets.QAbstractItemView.AllEditTriggers
        )
        # Resize the first column to fit its content
        self.table_widget.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeToContents
        )

        # Make the last column stretch to fill the remaining space
        self.table_widget.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Stretch
        )

        self.layout.addWidget(self.table_widget)

        # Add and Remove buttons
        self.add_button = QtWidgets.QPushButton("Add")
        self.add_button.clicked.connect(self.add_files)
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_file)

        # Build button
        self.build_button = QtWidgets.QPushButton("Build")
        self.build_button.clicked.connect(self.build_rig)

        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.remove_button)
        self.layout.addWidget(self.build_button)

        self.setLayout(self.layout)

    def set_output_folder(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder"
        )
        if folder_path:
            self.output_folder_line_edit.setText(folder_path)

    def add_files(self):
        file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Select .sgt Files", "", "*.sgt"
        )
        if file_paths:
            for file_path in file_paths:
                self.add_file(file_path)

    def add_file(self, file_path):
        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)

        # For .sgt file path
        file_item = QtWidgets.QTableWidgetItem("  " + file_path + "  ")
        self.table_widget.setItem(row_position, 0, file_item)

        # For Output Name
        output_name = os.path.splitext(os.path.basename(file_path))[0]
        output_item = QtWidgets.QTableWidgetItem("  " + output_name + "  ")
        self.table_widget.setItem(row_position, 1, output_item)

    def remove_file(self):
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

    def collect_data(self):
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
            output_name = (
                output_name_item.text().strip() if output_name_item else ""
            )

            data["rows"].append(
                {"file_path": file_path, "output_name": output_name}
            )

        return json.dumps(data)

    def build_rig(self):
        data = self.collect_data()
        builder.execute_build_logic(data)


def openRigBuilderUI(*args):
    pyqt.showDialog(RigBuilderUI, dockable=True)


if __name__ == "__main__":
    window = RigBuilderUI()
    window.show()
