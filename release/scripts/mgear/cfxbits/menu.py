import pymel.core as pm
import mgear.menu
import mgear


def install():
    """Install CFXbits submenu
    """
    pm.setParent(mgear.menu_id, menu=True)
    commands = (
        ("Xgen IGS Boost", str_openXgenBoost),
        ("-----", None)
    )

    mgear.menu.install("CFXbits", commands, image="mgear_cfxbits.svg")


str_openXgenBoost = """
from mgear.cfxbits.xgenboost import ui
ui.openXgenBoost()
"""
