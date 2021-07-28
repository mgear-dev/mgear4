
""" flex.menu

Flex menu handles adding the Flex menu item inside the Maya mGear menu.

:module: flex.menu
"""

# imports
from __future__ import absolute_import
from maya import cmds
import mgear


def install():
    """ Installs Flex sub-menu
    """

    cmds.setParent(mgear.menu_id, menu=True)
    cmds.menuItem(divider=True)
    cmds.menuItem(label="Flex", command=str_flex, image="mgear_flex.svg")


str_flex = """
from mgear.flex.flex import Flex
flex = Flex()
flex.launch()
"""
