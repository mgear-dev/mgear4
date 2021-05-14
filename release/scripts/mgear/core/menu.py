from functools import partial
import mgear
import mgear.menu
from mgear.core import pyqt
from mgear.core import skin
from mgear.core import wmap
import pymel.core as pm
from pymel import versions


def install_skinning_menu():
    """Install Skinning submenu
    """
    commands = (
        ("Copy Skin", partial(skin.skinCopy, None, None)),
        ("Select Skin Deformers", skin.selectDeformers),
        ("-----", None),
        ("Import Skin", partial(skin.importSkin, None)),
        ("Import Skin Pack", partial(skin.importSkinPack, None)),
        ("-----", None),
        ("Export Skin", partial(skin.exportSkin, None, None)),
        ("Export Skin Pack Binary", partial(skin.exportSkinPack, None, None)),
        ("Export Skin Pack ASCII", partial(skin.exportJsonSkinPack,
                                           None,
                                           None)),
        ("-----", None),
        ("Get Names in gSkin File", partial(skin.getObjsFromSkinFile, None)),
        ("-----", None),
        ("Import Deformer Weight Map", partial(wmap.import_weights_selected,
                                               None)),
        ("Export Deformer Weight Map", partial(wmap.export_weights_selected,
                                               None)),
    )

    mgear.menu.install("Skin and Weights", commands)


def install_utils_menu(m):
    """Install core utils submenu
    """
    if versions.current() < 20220000:
        pm.setParent(m, menu=True)
        pm.menuItem(divider=True)
        pm.menuItem(label="Compile PyQt ui", command=pyqt.ui2py)
