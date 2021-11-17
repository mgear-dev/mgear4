
import sys

from mgear.core import pyqt


import pymel.core as pm

import mgear
from mgear import shifter

##############################
# Helper Functions
##############################
__guide_settings_window__ = None

def draw_comp(comp_type, parent=None, showUI=True):
    """Draw a new component of a given name

    Args:
        comp_type (str): Name of the component to draw
        *args: Description
    """
    guide = shifter.guide.Rig()
    if not parent and pm.selected():
        parent = pm.selected()[0]

    if parent:
        if not parent.hasAttr("isGearGuide") and not parent.hasAttr("ismodel"):
            pm.displayWarning(
                "{}: is not valid Shifter guide elemenet".format(parent))
            return

    guide.drawNewComponent(parent, comp_type, showUI)


def duplicate(sym, *args):
    """Duplicate a component by drawing a new one and setting the same
    properties values

    Args:
        sym (bool): If True, will create a symmetrical component
        *args: None

    """
    oSel = pm.selected()
    if oSel:
        root = oSel[0]
        guide = shifter.guide.Rig()
        guide.duplicate(root, sym)
    else:
        mgear.log("Select one component root to edit properties",
                  mgear.sev_error)


def build_from_selection(*args):
    """Build rig from current selection

    Args:
        *args: None
    """
    shifter.log_window()
    rg = shifter.Rig()
    rg.buildFromSelection()


def inspect_settings(tabIdx=0, *args):
    """Open the component or root setting UI.

    Args:
        tabIdx (int, optional): Tab index to be open when open settings
        *args: None

    Returns:
        None: None if nothing is selected
    """
    oSel = pm.selected()
    if oSel:
        root = oSel[0]
    else:
        pm.displayWarning(
            "please select one object from the componenet guide")
        return

    comp_type = False
    guide_root = False
    while root:
        if pm.attributeQuery("comp_type", node=root, ex=True):
            comp_type = root.attr("comp_type").get()
            break
        elif pm.attributeQuery("ismodel", node=root, ex=True):
            guide_root = root
            break
        root = root.getParent()
        pm.select(root)

    settings = None
    if comp_type:
        guide = shifter.importComponentGuide(comp_type)
        settings = guide.componentSettings

    elif guide_root:
        module_name = "mgear.shifter.guide"
        level = -1 if sys.version_info < (3, 3) else 0
        guide = __import__(module_name, globals(), locals(), ["*"], level)
        settings = guide.guideSettings

    if not settings:
        pm.displayError(
            "The selected object is not part of component guide")
        return
    
    wind = globals().get("__guide_settings_window__")
    is_valid = wind and isinstance(wind,pyqt.QtWidgets.QWidget)
    is_valid = is_valid and pyqt.QtCompat.isValid(wind)

    if is_valid and wind.isVisible():
        widget = settings()
        layout = wind.layout()
        for child in wind.children():
            if isinstance(child,pyqt.QtWidgets.QWidget):
                child.deleteLater()
        layout.addWidget(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        wind = widget
    else:
        wind and pyqt.QtCompat.isValid(wind) and wind.deleteLater()
        wind = pyqt.showDialog(settings, dockable=True)
        globals()["__guide_settings_window__"] = wind
    wind.window().setWindowTitle("%s - %s" % (wind.windowTitle(), root))
    wind.tabs.setCurrentIndex(tabIdx)
    

def extract_controls(*args):
    """Extract the selected controls from the rig to use it in the new build

    The controls shapes are stored under the controller_org group.
    The controls are renamed witht "_controlBuffer" suffix

    Args:
        *args: None
    """
    oSel = pm.selected()

    try:
        cGrp = pm.PyNode("controllers_org")
    except TypeError:
        cGrp = False
        mgear.log(
            "Not controller group in the scene or the group is not unique",
            mgear.sev_error)
    for x in oSel:
        try:
            old = pm.PyNode(cGrp.name() + "|"
                            + x.name().split("|")[-1] + "_controlBuffer")
            pm.delete(old)
        except TypeError:
            pass
        new = pm.duplicate(x)[0]
        pm.parent(new, cGrp, a=True)
        pm.rename(new, x.name() + "_controlBuffer")
        toDel = new.getChildren(type="transform")
        pm.delete(toDel)
        try:
            pm.sets("rig_controllers_grp", remove=new)
        except TypeError:
            pass
