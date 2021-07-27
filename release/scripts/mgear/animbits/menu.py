import mgear.menu


def install():
    """Install Skinning submenu
    """
    commands = (
        ("Channel Master", str_openChannelMaster),
        ("-----", None),
        ("Soft Tweaks", str_openSoftTweakManager),
        ("Cache Manager", str_run_cache_mamanger),
        ("-----", None),
        ("Smart Reset Attribute/SRT", str_smart_reset)
    )

    mgear.menu.install("Animbits", commands, image="mgear_animbits.svg")


str_openChannelMaster = """
from mgear.animbits import channel_master
channel_master.openChannelMaster()
"""

str_openSoftTweakManager = """
from mgear.animbits import softTweaks
softTweaks.openSoftTweakManager()
"""

str_run_cache_mamanger = """
from mgear.animbits.cache_manager.dialog import run_cache_mamanger
run_cache_mamanger()
"""

str_smart_reset = """
from mgear.core import attribute
attribute.smart_reset()
"""
