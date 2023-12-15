import os
import subprocess
from typing import Callable
import tempfile
import shlex
import datetime

from mgear.vendor.Qt.QtCore import QThread, Signal
from mgear.core import (
    pyFBX as pfbx,
    string,
    utils as coreUtils,
)

import maya.cmds as cmds


class PartitionThread(QThread):
    """ Thread that handles the creation of fbx partitions"""

    completed = Signal(object, bool)
    progress_signal = Signal(float)

    def __init__(self, export_config):
        """
        Initializes the thread.
        """
        super().__init__()

        # self.log_message = log_message_function

        self.export_config = export_config

        # Makes sure the Thread removes itself
        self.finished.connect(self.deleteLater)

    def run(self):
        """
        Main function that gets called when the thread starts.
        """
        # Show the Thread is starting
        self.progress_signal.emit(20)

        success = self.export_skeletal_mesh()
        self.onComplete(success)

    def onComplete(self, success):
        """
        Cleans up the thread when the thread is finished.
        """
        self.completed.emit(self.export_config, success)

    def export_skeletal_mesh(self):
        """
        Triggers the batch process
        """
        export_data = self.export_config

        geo_roots = export_data.get("geo_roots", "")
        joint_roots = [export_data.get("joint_root", "")]
        file_path = export_data.get("file_path", "")
        file_name = export_data.get("file_name", "")
        remove_namespaces = export_data.get("remove_namespace", True)
        scene_clean = export_data.get("scene_clean", True)
        skinning = export_data.get("skinning", True)
        blendshapes = export_data.get("blendshapes", True)
        use_partitions = export_data.get("use_partitions", True)

        if not file_name.endswith(".fbx"):
            file_name = "{}.ma".format(file_name)
        else:
            file_name = "{}.ma".format(os.path.splitext(file_name)[0])

        export_path = string.normalize_path(os.path.join(file_path, file_name))

        log_path = os.path.normpath(os.path.join(file_path, "logs_{}.txt".format(datetime.datetime.now().strftime("%m%d%Y%H%M"))))
        print("\t>>> Export Path: {}".format(export_path))

        path_is_valid = os.path.exists(export_path)

        # "master" .ma file does not exist, exit early.
        if not path_is_valid:
            return False

        # Creates a MEL temporary job file..
        script_content = """
python "from mgear.shifter.game_tools_fbx import fbx_batch";
python "master_path='{master_path}'";
python "root_joint='{joint_root}'";
python "root_geos={geo_roots}";
python "export_data={e_data}";
python "fbx_batch.perform_fbx_condition({ns}, {sc}, master_path, root_joint, root_geos, {sk}, {bs}, {ps}, export_data)";
""".format(
            ns=remove_namespaces,
            sc=scene_clean,
            master_path=export_path,
            geo_roots=geo_roots,
            joint_root= joint_roots[0],
            sk=skinning,
            bs=blendshapes,
            ps=use_partitions,
            e_data=export_data)

        script_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.mel')
        script_file.write(script_content)
        script_file_path = script_file.name
        script_file.close()

        mayabatch_dir = coreUtils.get_maya_path()
        mayabatch_path = None
        mayabatch_args = None
        mayabatch_shell = False

        # Depending on the os we would need to change from maya, to maya batch
        # windows uses mayabatch
        if str(coreUtils.get_os()) == "win64" or str(coreUtils.get_os()) == "nt":
            option = "mayabatch"
        else:
            option = "maya"

        if option == "maya":
            mayabatch_command = 'maya'
            mayabatch_path = os.path.join(mayabatch_dir, mayabatch_command)
            mayabatch_args = [shlex.quote(mayabatch_path)]
            mayabatch_args.append("-batch")
            mayabatch_shell = False
            mayabatch_args.append("-script")
            mayabatch_args.append(shlex.quote(script_file_path))
            mayabatch_args.append("-log")
            mayabatch_args.append(shlex.quote(log_path))

            print("-------------------------------------------")
            print("[Launching] MayaBatch")
            print("   {}".format(mayabatch_args))
            print("   {}".format(" ".join(mayabatch_args)))
            print("-------------------------------------------")

        else:
            mayabatch_command = "maya"
            mayabatch_path = os.path.join(mayabatch_dir, mayabatch_command)
            mayabatch_args = ['"'+mayabatch_path+'"']
            mayabatch_args.append("-batch")
            mayabatch_shell = True
            mayabatch_args.append("-script")
            mayabatch_args.append('"'+script_file_path+'"')
            mayabatch_args.append("-log")
            mayabatch_args.append('"'+log_path+'"')

            mayabatch_args = "{}".format(" ".join(mayabatch_args))

            print("-------------------------------------------")
            print("[Launching] MayaBatch")
            print("   {}".format(mayabatch_args))
            print("-------------------------------------------")

        self.progress_signal.emit(50)

        try:
            with subprocess.Popen(mayabatch_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=mayabatch_shell,
                universal_newlines=True,
                bufsize=1
                ) as process:

                # Process each line (sentence) from the subprocess output
                # Looks for specific sentences in the logs and uses those as progress milestones.
                for line in process.stdout:
                    line = line.strip()
                    print(line)
                    if line.find("Conditioned file:") >= 0:
                        self.progress_signal.emit(60)
                    if line.find("Removing Namespace..") >= 0:
                        self.progress_signal.emit(65)
                    if line.find("Cleaning Scene..") >= 0:
                        self.progress_signal.emit(75)
                    if line.find("[Partitions]") >= 0:
                        self.progress_signal.emit(80)

                # Capture the output and errors
                stdout, stderr = process.communicate()

                # Check the return code
                #returncode = process.returncode
                returncode = process.wait()
                print("Return Code: {}".format(returncode))

                # Check the result
                if returncode == 0:
                    print("Mayabatch process completed successfully.")
                    print("-------------------------------------------")
                    # print("Output:", stdout)
                    #print("-------------------------------------------")
                else:
                    print("Mayabatch process failed.")
                    print("Error:", stderr)
                    print("-------------------------------------------")
                    return False
        except FileNotFoundError as error:
            print("Error:", error)
            return False

        # Clean up Mel batch file
        if os.path.exists(script_file_path):
            print("[Removing File] {}".format(script_file_path))
            os.remove(script_file_path)

        # If all goes well return the export path location, else None
        return True

    def init_data(self):
        """
        Initialises the Master .ma files that will be needed by the Thread and Maya batcher.

        This process exports the geometry roots and skeleton as an .ma, which will
        then be passed to the Thread for Maya batching.

        Note: This process cannot be run in the thread as Maya commands are not thread safe,
        This causes Maya to become partially unresponsive.
        """
        # Export initial FBX Master, from current Maya scene
        file_path = self.export_config.get("file_path", "")
        file_name = self.export_config.get("file_name", "")

        if not file_name.endswith(".fbx"):
            file_name = "{}.ma".format(file_name)
        else:
            file_name = "{}.ma".format(os.path.splitext(file_name)[0])

        # The location where the temoprary maya file will be saved to
        master_path = string.normalize_path(os.path.join(file_path, file_name))

        # Get the current scene path
        current_scene_path = cmds.file(query=True, sceneName=True)

        # Save the current scene to the new location
        cmds.file(rename=master_path)
        cmds.file(save=True, type="mayaAscii")

        # Revert the scene name to the original path
        cmds.file(rename=current_scene_path)

        # Set progress to 15% - at this point the master FBX has been exported
        self.progress_signal.emit(15)

        print("Temporary Master file: {}".format(master_path))

        return
