import pymel.core as pm
import mgear


def install():
    """Install synotic menu
    """
    pm.setParent(mgear.menu_id, menu=True)
    pm.menuItem(divider=True)
    pm.menuItem(label="Synoptic", command=str_open_synoptic)


str_open_synoptic = """
from mgear import synoptic
synoptic.open()
"""
