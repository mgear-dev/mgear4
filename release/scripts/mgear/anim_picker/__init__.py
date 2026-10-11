from . import gui
from . import version

__version__ = version.__version__


# =============================================================================
# Load user interface function
# =============================================================================
def load(edit=False, dockable=False, *args, **kwargs):
    """To launch the ui and not get the same instance

    Returns:
        Anim_picker: instance

    Args:
        edit (bool, optional): Description
        dockable (bool, optional): Description

    """
    return gui.load(edit=edit, dockable=dockable)


def drop_file(file_path):
    """Create a picker from a .pkr file dropped on Maya and open the picker.

    When the scene has namespaces, the user chooses the one the picker
    drives (or Root). A picker node of the same name is replaced.

    Args:
        file_path (str): Anim Picker (.pkr) file path.

    Returns:
        str: The picker data node, None if cancelled.
    """
    from mgear.vendor.Qt import QtWidgets
    from mgear.core import node_remap
    from mgear.core import pyqt

    from . import picker_node

    namespace = None
    namespaces = node_remap.scene_namespaces()
    if namespaces:
        namespace, ok = QtWidgets.QInputDialog.getItem(
            pyqt.maya_main_window(),
            "Anim Picker",
            "Namespace of the rig this picker drives:",
            ["Root"] + namespaces,
            1,
            False,
        )
        if not ok:
            return None
    node = picker_node.create_picker_from_file(file_path, namespace=namespace)
    load()
    return node
