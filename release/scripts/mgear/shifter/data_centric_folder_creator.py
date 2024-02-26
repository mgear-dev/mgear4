import os
import json
import pymel.core as pm

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

from mgear.vendor.Qt import QtGui, QtWidgets, QtCore
from mgear.core import pyqt, widgets


class FolderStructureCreatorUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):
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
        self.create_actions()
        self.init_ui()
        self.setMinimumWidth(200)
        self.setAcceptDrops(True)
        self.resize(550, 200)
        self.connect_signals()

    def create_actions(self):
        self.import_action = QtWidgets.QAction("Import Config")
        self.export_action = QtWidgets.QAction("Export Config")

    def init_ui(self):
        # menu bar
        self.menu_bar = QtWidgets.QMenuBar()
        self.file_menu = self.menu_bar.addMenu("File")
        self.file_menu.addAction(self.import_action)
        self.file_menu.addAction(self.export_action)

        # main layout
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setMenuBar(self.menu_bar)

        # Configuration Path UI
        self.config_path_le = QtWidgets.QLineEdit(self.config_path)
        self.config_path_btn = widgets.create_button(
            icon="mgear_folder", width=25
        )
        config_path_layout = QtWidgets.QHBoxLayout()
        config_path_layout.addWidget(self.config_path_le)
        config_path_layout.addWidget(self.config_path_btn)

        config_path_groupbox = QtWidgets.QGroupBox("Configuration Path")
        config_path_groupbox.setLayout(config_path_layout)

        # Main Path UI
        self.path_le = QtWidgets.QLineEdit(self.config.get("path", ""))
        self.path_btn = widgets.create_button(icon="mgear_folder", width=25)
        main_path_layout = QtWidgets.QHBoxLayout()
        main_path_layout.addWidget(self.path_le)
        main_path_layout.addWidget(self.path_btn)
        main_path_groupbox = QtWidgets.QGroupBox("Root Path")
        main_path_groupbox.setLayout(main_path_layout)

        # root folder names
        self.custom_step_name_le = QtWidgets.QLineEdit(self.config["custom_step_folder"])
        self.data_name_le = QtWidgets.QLineEdit(self.config["data_folder"])
        folder_names_layout = QtWidgets.QVBoxLayout()
        folder_names_layout.addWidget(QtWidgets.QLabel("Custom Step Folder:"))
        folder_names_layout.addWidget(self.custom_step_name_le)
        folder_names_layout.addWidget(QtWidgets.QLabel("Data Folder:"))
        folder_names_layout.addWidget(self.data_name_le)
        folder_names_groupbox = QtWidgets.QGroupBox("Root Folders Names")
        folder_names_groupbox.setLayout(folder_names_layout)

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

        # settings layout
        settings_layout = QtWidgets.QVBoxLayout()
        settings_layout.addWidget(QtWidgets.QLabel("Type:"))
        settings_layout.addWidget(self.type_le)
        settings_layout.addWidget(QtWidgets.QLabel("Name:"))
        settings_layout.addWidget(self.name_le)
        settings_layout.addWidget(QtWidgets.QLabel("Variant:"))
        settings_layout.addWidget(self.variant_le)
        settings_layout.addWidget(QtWidgets.QLabel("Target:"))
        settings_layout.addWidget(self.target_le)
        settings_layout.addWidget(self.create_btn)
        settings_groupbox = QtWidgets.QGroupBox("Settings")
        settings_groupbox.setLayout(settings_layout)

        # Vertical expander (spacer)
        vertical_spacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        # Layout setup
        self.layout.addWidget(config_path_groupbox)
        self.layout.addWidget(main_path_groupbox)
        self.layout.addWidget(folder_names_groupbox)
        self.layout.addWidget(settings_groupbox)
        self.layout.addItem(vertical_spacer)

    def connect_signals(self):
        self.import_action.triggered.connect(self.import_config)
        self.export_action.triggered.connect(self.export_config)

        self.create_btn.clicked.connect(self.create_folder_structure)
        self.config_path_btn.clicked.connect(self.set_config_path)
        self.path_btn.clicked.connect(self.set_main_path)

        # update confing
        self.custom_step_name_le.editingFinished.connect(self.update_config_custom_step)
        self.data_name_le.editingFinished.connect(self.update_config_data)
        self.type_le.editingFinished.connect(self.update_config_type)
        self.name_le.editingFinished.connect(self.update_config_name)
        self.variant_le.editingFinished.connect(self.update_config_variant)
        self.target_le.editingFinished.connect(self.update_config_target)

    def update_config_custom_step(self):
        self.config["custom_step_folder"] = self.custom_step_name_le.text()
    
    def update_config_data(self):
        self.config["data_folder"] = self.data_name_le.text()

    def update_config_type(self):
        self.config["type"] = self.type_le.text()

    def update_config_name(self):
        self.config["name"] = self.name_le.text()

    def update_config_variant(self):
        variants = [v.strip() for v in self.variant_le.text().split(",")]
        self.config["variant"] = variants

    def update_config_target(self):
        targets = [t.strip() for t in self.target_le.text().split(",")]
        self.config["target"] = targets

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
                "custom_step_folder": "custom_step",
                "data_folder": "data",
            }
        return config

    # def save_config(self):
    #     with open(self.config_path, "w") as f:
    #         json.dump(self.config, f, indent=4)

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
        base_path = self.config["path"]
        custom_step_folder_name = self.config["custom_step_folder"]
        data_folder_name = self.config["data_folder"]
        asset_type = self.config["type"]
        name = self.config["name"]
        if not name:
            pm.displayWarning("Please set the name of the asset")
            return
        variants = self.config["variant"]
        targets = self.config["target"]

        def create_folder(path):
            # determines sub_folders based on whether data_folder_name is in path 
            sub_dirs = ["data", "assets"] if data_folder_name in path else ["pre", "post"]
            for sub_dir in sub_dirs:
                sub_dir_path = os.path.join(path, sub_dir)
                if not os.path.exists(sub_dir_path):
                    os.makedirs(sub_dir_path)


        for root_folder in [custom_step_folder_name, data_folder_name]:
            root_shared = os.path.join(base_path, root_folder, "_shared")
            create_folder(root_shared)
            
            asset_type_shared = os.path.join(base_path, root_folder, asset_type, "_shared")
            create_folder(asset_type_shared)

            name_shared = os.path.join(base_path, root_folder, asset_type, name, "_shared")
            create_folder(name_shared)

            for variant in variants:
                variant_shared = os.path.join(base_path, root_folder, asset_type, name, variant, "_shared")
                create_folder(variant_shared)

                for target in targets:

                    path = os.path.join(base_path, root_folder, asset_type, name, variant, target)
                    create_folder(path)

        QtWidgets.QMessageBox.information(
            self,
            "Success",
            "Data Centric Folder structure created successfully.",
        )

       


def openFolderStructureCreator(*args):
    pyqt.showDialog(FolderStructureCreatorUI, dockable=True)


if __name__ == "__main__":
    openFolderStructureCreator()
