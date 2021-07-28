import pymel.core as pm
import mgear

menuId = "mGear"


def create(menuId=menuId):
    """Create mGear main menu

    Args:
        menuId (str, optional): Main menu name

    Returns:
        str: main manu name
    """

    if pm.menu(menuId, exists=True):
        pm.deleteUI(menuId)

    pm.menu(menuId,
            parent="MayaWindow",
            tearOff=True,
            allowOptionBoxes=True,
            label=menuId)

    return menuId


def install_help_menu(menuId=menuId):
    """Install help menu section

    Args:
        menuId (str, optional): Main menu name
    """

    # Help
    pm.setParent(menuId, menu=True)
    pm.menuItem(divider=True)
    pm.menuItem(parent=menuId,
                subMenu=True,
                tearOff=True,
                label="Help",
                image="mgear_help-circle.svg")
    pm.menuItem(label="Web", command=str_web, image="mgear_globe.svg")
    pm.menuItem(label="Forum",
                command=str_forum,
                image="mgear_message-circle.svg")
    pm.menuItem(divider=True)
    pm.menuItem(label="Documentation",
                command=str_docs,
                image="mgear_book.svg")
    pm.menuItem(divider=True)
    pm.menuItem(label="About", command=str_about, image="mgear_smile.svg")


def install_utils_menu():
    """Install Utilities submenu
    """
    pm.setParent(mgear.menu_id, menu=True)
    pm.menuItem(divider=True)
    commands = [("Reload", str_reload, "mgear_refresh-cw.svg")]

    m = install("Utilities", commands, image="mgear_tool.svg")
    return m


def install(label, commands, parent=menuId, image=""):
    """Installer Function for sub menus

    Args:
        label (str): Name of the sub menu
        commands (list): List of commands to install
        parent (str, optional): Parent menu for the submenu
    """
    try:
        m = pm.menuItem(parent=parent,
                        subMenu=True,
                        tearOff=True,
                        label=label,
                        image=image)
        for conf in commands:
            if len(conf) == 3:
                label, command, img = conf
            else:
                label, command = conf
                img = ""
            if not command:
                pm.menuItem(divider=True)
                continue
            if not label:
                command(m)
                pm.setParent(m, menu=True)
                continue

            pm.menuItem(label=label, command=command, image=img)

        return m

    except Exception as ex:
        template = ("An exception of type {0} occured. "
                    "Arguments:\n{1!r}")
        message = template.format(type(ex).__name__, ex.args)
        pm.displayError(message)


str_web = """
import webbrowser
webbrowser.open("http://www.mgear-framework.com/")
"""

str_forum = """
import webbrowser
webbrowser.open("http://forum.mgear-framework.com/")
"""

str_docs = """
import webbrowser
webbrowser.open("https://www.mgear-framework.com/mgear_dist/")
"""

str_about = """
import mgear
mgear.core.aboutMgear()
"""


str_reload = """
import mgear
mgear.reloadModule("mgear")
"""
