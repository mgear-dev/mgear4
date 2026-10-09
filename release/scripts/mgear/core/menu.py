import mgear.menu


def skinning_menu_commands():
    """Get the Skin and Weights submenu commands.

    Commands are source strings, not callables, so the menu items can be
    dragged to a shelf and re-run with Repeat Last.

    Returns:
        tuple: (label, command, image) entries, with ("-----", None) dividers.
    """
    return (
        ("Copy Skin", str_skinCopy, "mgear_copy.svg"),
        ("Copy Skin Add", str_skinCopyAdd, "mgear_copy-add.svg"),
        ("Copy Skin Partial", str_skinCopyPartial, "mgear_copy-partial.svg"),
        (
            "Select Skin Deformers",
            str_selectDeformers,
            "mgear_mouse-pointer.svg",
        ),
        ("-----", None),
        (
            "Skin Cluster Selector",
            str_openSkinClusterSelector,
            "mgear_list.svg",
        ),
        ("Skin Cluster Rename", str_renameSkinClusters, "mgear_edit-3.svg"),
        ("-----", None),
        ("Import Skin", str_importSkin, "mgear_log-in.svg"),
        ("Import Skin Pack", str_importSkinPack, "mgear_package_in.svg"),
        ("-----", None),
        ("Export Skin", str_exportSkin, "mgear_log-out.svg"),
        (
            "Export Skin Pack Binary",
            str_exportSkinPack,
            "mgear_package_out.svg",
        ),
        (
            "Export Skin Pack ASCII",
            str_exportJsonSkinPack,
            "mgear_package_out.svg",
        ),
        (
            "Export Skin Pack ASCII with Position Data",
            str_exportJsonSkinPackWithPositions,
            "mgear_package_out_positions.svg",
        ),
        ("-----", None),
        ("Get Names in gSkin File", str_getObjsFromSkinFile),
        ("-----", None),
        (
            "Import Deformer Weight Map",
            str_importWeightMap,
            "mgear_log-in.svg",
        ),
        (
            "Export Deformer Weight Map",
            str_exportWeightMap,
            "mgear_log-out.svg",
        ),
    )


def install_skinning_menu():
    """Install Skinning submenu"""
    mgear.menu.install(
        "Skin and Weights", skinning_menu_commands(), image="mgear_skin.svg"
    )


def install_utils_menu(m):
    """Install core utils submenu.

    Kept for backwards compatibility. The only item, "Compile PyQt ui", was
    for Maya versions older than 2022, which mGear no longer supports.

    Args:
        m (str): Parent utilities menu.
    """
    return


str_skinCopy = """
from mgear.core import skin
skin.skinCopy()
"""

str_skinCopyAdd = """
from mgear.core import skin
skin.skin_copy_add()
"""

str_skinCopyPartial = """
from mgear.core import skin
skin.skinCopyPartial()
"""

str_selectDeformers = """
from mgear.core import skin
skin.selectDeformers()
"""

str_openSkinClusterSelector = """
from mgear.core import skin
skin.openSkinClusterSelector()
"""

str_renameSkinClusters = """
from mgear.core import skin
skin.rename_skin_clusters()
"""

str_importSkin = """
from mgear.core import skin
skin.importSkin(on_missing="ui")
"""

str_importSkinPack = """
from mgear.core import skin
skin.importSkinPack(on_missing="ui")
"""

str_exportSkin = """
from mgear.core import skin
skin.exportSkin()
"""

str_exportSkinPack = """
from mgear.core import skin
skin.exportSkinPack()
"""

str_exportJsonSkinPack = """
from mgear.core import skin
skin.exportJsonSkinPack()
"""

str_exportJsonSkinPackWithPositions = """
from mgear.core import skin
skin.exportJsonSkinPackWithPositions()
"""

str_getObjsFromSkinFile = """
from mgear.core import skin
skin.getObjsFromSkinFile()
"""

str_importWeightMap = """
from mgear.core import wmap
wmap.import_weights_selected()
"""

str_exportWeightMap = """
from mgear.core import wmap
wmap.export_weights_selected()
"""
