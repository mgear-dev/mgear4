import maya.cmds as cmds
import mgear

from mgear.core import string


menuID = "ueGear"


def install():
    """Installs ueGear sub-menu"""

    cmds.setParent(mgear.menu_id, menu=True)
    cmds.menuItem(divider=True)
    commands = (
        (
            "Import Selected Assets from Unreal",
            str_import_selected_assets_from_unreal,
        ),
        (
            "Export Selected Assets to Unreal",
            str_export_selected_assets_to_unreal,
        ),
        ("-----", None),
    )

    mgear.menu.install(menuID, commands, image="UE5.svg")


str_import_selected_assets_from_unreal = """
from mgear.uegear import bridge
uegear_bridge = bridge.UeGearBridge()
uegear_bridge.import_selected_assets_from_unreal()
"""


str_export_selected_assets_to_unreal = """
from mgear.uegear import bridge
uegear_bridge = bridge.UeGearBridge()
uegear_bridge.export_selected_assets_to_unreal()
"""
