import traceback


import pymel.core as pm

import mgear

from mgear.vendor.Qt import QtCore

from mgear.core.anim_utils import *

# =============================================================================
# constants
# =============================================================================

SYNOPTIC_WIDGET_NAME = "synoptic_view"


##################################################
#
##################################################

def getSynopticWidget(widget, max_iter=20):
    """Return the widget where the synoptic panel is attach

    Arguments:
        widget (QWidget): The widget to get the parent
        max_iter (int, optional): Iteration limit to find the paretn widget

    Returns:
        widget: The Parent widget
    """
    parent = widget.parentWidget()
    for i in range(max_iter):
        if parent.objectName() == SYNOPTIC_WIDGET_NAME:
            return parent
        parent = parent.parentWidget()

    return False


def getModel(widget):
    """Get the model Name

    Args:
        widget (QWidget): Synoptic widget

    Returns:
        PyNode: The rig model name
    """
    syn_widget = getSynopticWidget(widget, max_iter=20)
    model_name = syn_widget.model_list.currentText()

    if not pm.ls(model_name):
        return None

    try:
        model = pm.PyNode(model_name)

    except pm.general.MayaNodeError:
        mes = traceback.format_exc()
        mes = "Can't find model {0} for widget: {1}\n{2}".format(
            model_name, widget, mes)
        mgear.log(mes, mgear.sev_error)
        return None

    return model


##################################################
# SELECT
##################################################
# ================================================
def selectObj(model, object_names, mouse_button, key_modifier):
    """Select an object

    Args:
        model (PyNode): The rig top node
        object_names (list): The names of the objects to select
        mouse_button (QtSignal): Clicked mouse button signal
        key_modifier (QtSignal): Modifier button signal

    Returns:
        None
    """
    if not model:
        return

    nameSpace = getNamespace(model)

    with pm.UndoChunk():
        nodes = []
        for name in object_names:
            if nameSpace:
                node = getNode(nameSpace + ":" + name)
            else:
                node = getNode(name)

            if not node:
                continue

            if not node and nameSpace:
                mgear.log("Can't find object : %s:%s" % (nameSpace, name),
                          mgear.sev_error)
            elif not node:
                mgear.log("Can't find object : %s" % (name), mgear.sev_error)
            nodes.append(node)

        if not nodes:
            return
        if mouse_button == QtCore.Qt.RightButton:
            mirrorPose(False, nodes)
            return
        if mouse_button == QtCore.Qt.MiddleButton:
            mirrorPose(True, nodes)
            return
        # Key pressed
        if key_modifier is None:
            pm.select(nodes)
        elif key_modifier == QtCore.Qt.NoModifier:  # No Key
            pm.select(nodes)
        elif key_modifier == QtCore.Qt.ControlModifier:  # ctrl
            pm.select(nodes, deselect=True)
        elif key_modifier == QtCore.Qt.ShiftModifier:  # shift
            pm.select(nodes, toggle=True)
        elif int(key_modifier) == (QtCore.Qt.ControlModifier
                                   | QtCore.Qt.ShiftModifier):  # ctrl + shift
            pm.select(nodes, add=True)
        elif key_modifier == QtCore.Qt.AltModifier:  # alt
            pm.select(nodes)
        elif int(key_modifier) == (QtCore.Qt.ControlModifier
                                   | QtCore.Qt.AltModifier):  # ctrl + alt
            pm.select(nodes, deselect=True)
        elif int(key_modifier) == (QtCore.Qt.ShiftModifier
                                   | QtCore.Qt.AltModifier):  # shift + alt
            pm.select(nodes, toggle=True)

            # Ctrl + alt + shift
        elif int(key_modifier) == (QtCore.Qt.ControlModifier
                                   | QtCore.Qt.AltModifier
                                   | QtCore.Qt.ShiftModifier):
            pm.select(nodes, add=True)
        else:
            pm.select(nodes)
