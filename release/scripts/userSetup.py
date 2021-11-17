
# imports
from maya import cmds
from pymel import mayautils
# from cvwrap.menu import create_menuitems

print("""
 ____________________________________
|             _____                  |
|            / ____|                 |
|  _ __ ___ | |  __  ___  __ _ _ __  |
| | '_ ` _ \| | |_ |/ _ \/ _` | '__| |
| | | | | | | |__| |  __/ (_| | |    |
| |_| |_| |_|\_____|\___|\__,_|_|    |
|____________________________________|

""")

def settings_switch_callback():
    from mgear.shifter import guide_manager
    from mgear.core import pyqt
    
    state = cmds.optionVar(query="mgear_guide_switch_OV")
    selections = cmds.ls(sl=1)
    if not state or len(selections) != 1:
        return
    sel = selections[0]
    
    has_attr = cmds.attributeQuery("comp_type", node=sel, ex=True)
    has_attr |= cmds.attributeQuery("ismodel", node=sel, ex=True)
    
    wind = guide_manager.__guide_settings_window__
    is_valid = wind and isinstance(wind,pyqt.QtWidgets.QWidget)
    is_valid &= pyqt.QtCompat.isValid(wind)
    if has_attr and is_valid:
        if wind.isVisible():
            guide_manager.inspect_settings()
        else:
            wind.deleteLater()

def install_settings_switch(menu_id):
    # setup guide switch
    if not cmds.optionVar(exists="mgear_guide_switch_OV"):
        cmds.optionVar(intValue=("mgear_guide_switch_OV", 0))
    
    state = cmds.optionVar(query="mgear_guide_switch_OV")
    cmds.setParent(menu_id, menu=True)
    cmds.menuItem(
        "mgear_guide_switch_menuitem",
        label="Auto Guide Settings Switch",
        command=lambda s: cmds.optionVar(intValue=("mgear_guide_switch_OV", int(s))),
        checkBox=state,
    )
                  
    # regsiter event
    jobNum = cmds.scriptJob( e=["SelectionChanged",settings_switch_callback], pro=True)

def mGear_menu_loader():
    """Create mGear menu"""

    # Install mGear Menu
    import mgear
    mgear.install()
    install_settings_switch(mgear.menu_id)

    # Install Dag Menu option
    import mgear.core.dagmenu
    mgear.core.dagmenu.install()

    # Install Shifter Menu
    import mgear.shifter.menu
    mgear.shifter.menu.install()

    # Install Simple Rig Menu
    import mgear.simpleRig.menu
    mgear.simpleRig.menu.install()

    # Install Skinning Menu
    import mgear.core.menu
    mgear.core.menu.install_skinning_menu()

    # Install Rigbits Menu
    import mgear.rigbits.menu
    mgear.rigbits.menu.install()

    # Install Animbits Menu
    import mgear.animbits.menu
    mgear.animbits.menu.install()

    # Install CFXbits Menu
    import mgear.cfxbits.menu
    mgear.cfxbits.menu.install()

    # Install Crank Menu
    import mgear.crank.menu
    mgear.crank.menu.install()

    # Install Anim Picker Menu
    import mgear.anim_picker.menu
    mgear.anim_picker.menu.install()

    # Install Synoptic Menu
    import mgear.synoptic.menu
    mgear.synoptic.menu.install()

    # Install Flex Menu
    import mgear.flex.menu
    mgear.flex.menu.install()

    # Install Utilities Menu
    import mgear.menu
    m = mgear.menu.install_utils_menu()
    mgear.core.menu.install_utils_menu(m)
    mgear.rigbits.menu.install_utils_menu(m)

    # install dragdrop override in utilities
    import mgear.core.dragdrop
    mgear.core.dragdrop.install_utils_menu(m)

    # Install Help Menu
    mgear.menu.install_help_menu()


if not cmds.about(batch=True):
    mayautils.executeDeferred(mGear_menu_loader)
    # mayautils.executeDeferred(create_menuitems)
