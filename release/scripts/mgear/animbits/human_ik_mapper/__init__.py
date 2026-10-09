"""HumanIK Mapper: retarget HumanIK sources (mocap, characters) to mGear rigs.

Modules:
    constants: HumanIK bone groups, names and file format.
    core: character, mapping, Sub IK, mapping files, source and bake.
    batch: batch bake of animation files.
    ui: the tool window.
"""


def show(*args):
    """Open the HumanIK Mapper window.

    Returns:
        QDialog: The window.
    """
    from . import ui

    return ui.show()
