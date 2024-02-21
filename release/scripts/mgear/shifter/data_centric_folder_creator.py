import os
import json

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from mgear.vendor.Qt import QtGui, QtWidgets, QtCore
from mgear.core import pyqt, widgets


class FolderStructureCreatorUI(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(FolderStructureCreatorUI, self).__init__(parent)
        self.setWindowTitle("Data-Centric Folder Structure Creator")
        self.default_config_path = os.path.join(
            os.path.expanduser("~"), "data_centric_folder_creator_config.json"
        )
        self.config_path = (
            self.load_last_config_path() or self.default_config_path
        )
        self.config = self.load_config()
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)

        # Configuration Path UI
        self.config_path_le = QtWidgets.QLineEdit(self.config_path)
        self.config_path_btn = QtWidgets.QPushButton("Set Config Path")
        config_path_layout = QtWidgets.QHBoxLayout()
        config_path_layout.addWidget(self.config_path_le)
        config_path_layout.addWidget(self.config_path_btn)

        # Main Path UI
        self.path_le = QtWidgets.QLineEdit(self.config.get("path", ""))
        self.path_btn = QtWidgets.QPushButton("...")
        main_path_layout = QtWidgets.QHBoxLayout()
        main_path_layout.addWidget(self.path_le)
        main_path_layout.addWidget(self.path_btn)

        # Other Inputs
        self.type_le = QtWidgets.QLineEdit(self.config.get("type", "char"))
        self.name_le = QtWidgets.QLineEdit(self.config.get("name", ""))
        self.variant_le = QtWidgets.QLineEdit(
            ", ".join(self.config.get("variant", ["default"]))
        )
        self.target_le = QtWidgets.QLineEdit(
            ", ".join(self.config.get("target", ["layout", "anim"]))
        )

        # Buttons
        self.create_btn = QtWidgets.QPushButton("Create Folder Structure")
        self.export_btn = QtWidgets.QPushButton("Export Config")
        self.import_btn = QtWidgets.QPushButton("Import Config")

        # Layout setup
        self.layout.addLayout(config_path_layout)
        self.layout.addWidget(QtWidgets.QLabel("Path:"))
        self.layout.addLayout(main_path_layout)
        self.layout.addWidget(QtWidgets.QLabel("Type:"))
        self.layout.addWidget(self.type_le)
        self.layout.addWidget(QtWidgets.QLabel("Name:"))
        self.layout.addWidget(self.name_le)
        self.layout.addWidget(QtWidgets.QLabel("Variant:"))
        self.layout.addWidget(self.variant_le)
        self.layout.addWidget(QtWidgets.QLabel("Target:"))
        self.layout.addWidget(self.target_le)
        self.layout.addWidget(self.create_btn)
        self.layout.addWidget(self.export_btn)
        self.layout.addWidget(self.import_btn)

    def connect_signals(self):
        self.create_btn.clicked.connect(self.create_folder_structure)
        self.export_btn.clicked.connect(self.export_config)
        self.import_btn.clicked.connect(self.import_config)
        self.config_path_btn.clicked.connect(self.set_config_path)
        self.path_btn.clicked.connect(self.set_main_path)

    def load_last_config_path(self):
        settings_file = os.path.join(
            os.path.expanduser("~"), ".data_centric_fs_creator_settings"
        )
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                return f.read().strip()
        return None

    def save_last_config_path(self):
        settings_file = os.path.join(
            os.path.expanduser("~"), ".data_centric_fs_creator_settings"
        )
        with open(settings_file, "w") as f:
            f.write(self.config_path)

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                config = json.load(f)
        else:
            config = {
                "path": "",
                "type": "char",
                "name": "",
                "variant": ["default"],
                "target": ["layout", "anim"],
            }
        return config

    def save_config(self):
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    def set_config_path(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Set Config Path", self.config_path, "JSON Files (*.json)"
        )
        if file_name:
            self.config_path = file_name
            self.config_path_le.setText(self.config_path)
            self.save_last_config_path()
            self.config = self.load_config()
            self.update_ui()

    def set_main_path(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Folder"
        )
        if directory:
            self.path_le.setText(directory)
            self.config["path"] = directory

    def export_config(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Config", "", "JSON Files (*.json)"
        )
        if file_name:
            with open(file_name, "w") as f:
                json.dump(self.config, f, indent=4)

    def import_config(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Config", "", "JSON Files (*.json)"
        )
        if file_name:
            self.config_path = file_name
            self.config_path_le.setText(self.config_path)
            self.config = self.load_config()
            self.update_ui()
            self.save_last_config_path()

    def update_ui(self):
        self.path_le.setText(self.config.get("path", ""))
        self.type_le.setText(self.config.get("type", "char"))
        self.name_le.setText(self.config.get("name", ""))
        self.variant_le.setText(
            ", ".join(self.config.get("variant", ["default"]))
        )
        self.target_le.setText(
            ", ".join(self.config.get("target", ["layout", "anim"]))
        )

    def create_folder_structure(self):
        base_path = self.path_le.text()
        asset_type = self.type_le.text()
        name = self.name_le.text()
        variants = [v.strip() for v in self.variant_le.text().split(",")]
        targets = [t.strip() for t in self.target_le.text().split(",")]

        for variant in variants:
            for target in targets:
                # Define paths for data and custom_step directories
                data_paths = [
                    os.path.join(
                        base_path,
                        "data",
                        asset_type,
                        name,
                        variant,
                        target,
                        subdir,
                    )
                    for subdir in ["data", "assets"]
                ]
                custom_step_paths = [
                    os.path.join(
                        base_path,
                        "custom_step",
                        asset_type,
                        name,
                        variant,
                        target,
                        subdir,
                    )
                    for subdir in ["pre", "post"]
                ]
                shared_data_path = os.path.join(
                    base_path, "data", asset_type, name, "_shared"
                )
                shared_custom_path = os.path.join(
                    base_path, "custom_step", asset_type, name, "_shared"
                )

                # Create directories
                for path in data_paths + custom_step_paths:
                    if not os.path.exists(path):
                        os.makedirs(path)

                # Create _shared directories
                for subdir in ["data", "assets"]:
                    path = os.path.join(shared_data_path, subdir)
                    if not os.path.exists(path):
                        os.makedirs(path)
                for subdir in ["pre", "post"]:
                    path = os.path.join(shared_custom_path, subdir)
                    if not os.path.exists(path):
                        os.makedirs(path)

        QtWidgets.QMessageBox.information(
            self,
            "Success",
            "Data Centric Folder structure created successfully.",
        )


def openFolderStructureCreator(*args):
    pyqt.showDialog(FolderStructureCreatorUI, dockable=True)


if __name__ == "__main__":
    window = FolderStructureCreatorUI()
    window.show()
