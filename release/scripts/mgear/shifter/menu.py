import mgear.menu


def install():
    """Install Shifter submenu
    """
    commands = (
        ("Guide Manager", str_show_guide_manager, "mgear_list.svg"),
        ("-----", None),
        ("Settings", str_inspect_settings, "mgear_sliders.svg"),
        ("Duplicate", str_duplicate, "mgear_copy.svg"),
        ("Duplicate Sym", str_duplicateSym, "mgear_duplicate_sym.svg"),
        ("Extract Controls", str_extract_controls, "mgear_move.svg"),
        ("-----", None),
        ("Build from Selection", str_build_from_selection, "mgear_play.svg"),
        ("Build From Guide Template File",
         str_build_from_file,
         "mgear_play-circle.svg"),
        ("-----", None),
        ("Import Guide Template",
         str_import_guide_template,
         "mgear_log-in.svg"),
        ("Export Guide Template",
         str_export_guide_template,
         "mgear_log-out.svg"),
        ("-----", None),
        (None, guide_template_samples_submenu),
        ("-----", None),
        ("Auto Fit Guide (BETA)", str_auto_fit_guide),
        ("-----", None),
        ("Plebes...", str_plebes),
        ("-----", None),
        (None, mocap_submenu),
        ("Game Tools", str_openGameTools),
        ("-----", None),
        ("Update Guide", str_updateGuide, "mgear_loader.svg"),
        ("-----", None),
        ("Reload Components", str_reloadComponents, "mgear_refresh-cw.svg")
    )

    mgear.menu.install("Shifter", commands, image="mgear_shifter.svg")


def mocap_submenu(parent_menu_id):
    """Create the mocap submenu

    Args:
        parent_menu_id (str): Parent menu. i.e: "MayaWindow|mGear|menuItem355"
    """
    commands = (
        ("Import Mocap Skeleton Biped", str_mocap_importSkeletonBiped),
        ("Characterize Biped", str_mocap_characterizeBiped),
        ("Bake Mocap Biped", str_mocap_bakeMocap)
    )

    mgear.menu.install("Mocap", commands, parent_menu_id)


def guide_template_samples_submenu(parent_menu_id):
    """Create the guide sample templates submenu

    Args:
        parent_menu_id (str): Parent menu. i.e: "MayaWindow|mGear|menuItem355"
    """
    commands = (
        ("Biped Template", str_biped_template),
        ("Quadruped Template", str_quadruped_template),
        ("-----", None),
        ("EPIC MetaHuman Template, Z-up", str_epic_metahuman_z_template),
        ("EPIC Mannequin Template, Z-up", str_epic_mannequin_z_template),
        ("-----", None),
        ("EPIC MetaHuman Snap", str_epic_metahuman_snap)
    )

    mgear.menu.install("Guide Template Samples",
                       commands,
                       parent_menu_id,
                       image="mgear_users.svg")


str_show_guide_manager = """
from mgear.shifter import guide_manager_gui
guide_manager_gui.show_guide_manager()
"""

str_inspect_settings = """
from mgear.shifter import guide_manager
guide_manager.inspect_settings(0)
"""

str_duplicate = """
from mgear.shifter import guide_manager
guide_manager.duplicate(False)
"""

str_duplicateSym = """
from mgear.shifter import guide_manager
guide_manager.duplicate(True)
"""

str_extract_controls = """
from mgear.shifter import guide_manager
guide_manager.extract_controls()
"""

str_build_from_selection = """
from mgear.shifter import guide_manager
guide_manager.build_from_selection()
"""

str_build_from_file = """
from mgear.shifter import io
io.build_from_file(None)
"""

str_import_guide_template = """
from mgear.shifter import io
io.import_guide_template(None)
"""

str_export_guide_template = """
from mgear.shifter import io
io.export_guide_template(None, None)
"""

str_plebes = """
from mgear.shifter import plebes
plebes.plebes_gui()
"""

str_auto_fit_guide = """
from mgear.shifter import afg_tools_ui
afg_tools_ui.show()
"""

str_openGameTools = """
from mgear.shifter import game_tools
game_tools.openGameTools()
"""

str_updateGuide = """
from mgear.shifter import guide_template
guide_template.updateGuide()
"""

str_reloadComponents = """
from mgear import shifter
shifter.reloadComponents()
"""

str_biped_template = """
from mgear.shifter import io
io.import_sample_template("biped.sgt")
"""

str_quadruped_template = """
from mgear.shifter import io
io.import_sample_template("quadruped.sgt")
"""

str_epic_metahuman_z_template = """
from mgear.shifter import io
io.import_sample_template("EPIC_metahuman_z_up.sgt")
io.metahuman_snap()
"""

str_epic_metahuman_snap = """
from mgear.shifter import io
io.metahuman_snap()
"""

str_epic_mannequin_z_template = """
from mgear.shifter import io
io.import_sample_template("EPIC_mannequin_z_up.sgt")
"""

str_mocap_importSkeletonBiped = """
from mgear.shifter import mocap_tools
mocap_tools.importSkeletonBiped()
"""

str_mocap_characterizeBiped = """
from mgear.shifter import mocap_tools
mocap_tools.characterizeBiped()
"""

str_mocap_bakeMocap = """
from mgear.shifter import mocap_tools
mocap_tools.bakeMocap()
"""
