"""HumanIK Mapper entry point, kept for menus and user scripts.

The tool lives in :mod:`mgear.animbits.human_ik_mapper`. This module keeps
``show()`` and the ``HumanIKMapper`` class of the previous version, whose
class methods now delegate to the package. The mapping is no longer cached:
``char_config`` is refreshed by :meth:`HumanIKMapper.refresh_char_configuration`.
"""

from mgear.animbits.human_ik_mapper import batch
from mgear.animbits.human_ik_mapper import constants
from mgear.animbits.human_ik_mapper import core

from maya import cmds


def _names(nodes):
    return [str(node) for node in nodes]


def _ask_path(mode):
    paths = cmds.fileDialog2(fileMode=mode, fileFilter=constants.MAPPING_FILTER)
    return paths[0] if paths else None


class HumanIKMapper(object):
    """Backward compatible facade over :mod:`human_ik_mapper.core`."""

    HEAD_NAMES = list(constants.HEAD)
    SPINE_NAMES = list(constants.SPINE)
    LEFT_ARM_NAMES = list(constants.LEFT_ARM)
    LEFT_UPPER_ARM_ROLLS = list(constants.LEFT_UPPER_ARM_ROLLS)
    LEFT_LOWER_ARM_ROLLS = list(constants.LEFT_LOWER_ARM_ROLLS)
    LEFT_HAND = list(constants.LEFT_HAND)
    LEFT_LEG_NAMES = list(constants.LEFT_LEG)
    LEFT_UPPER_LEG_ROLLS = list(constants.LEFT_UPPER_LEG_ROLLS)
    LEFT_LOWER_LEG_ROLLS = list(constants.LEFT_LOWER_LEG_ROLLS)
    CHAR_NAME = constants.CHAR_NAME

    # last mapping read by refresh_char_configuration
    char_config = {}

    @classmethod
    def initialize_character(cls):
        """Create the character with the last selected control as Reference."""
        selection = cmds.ls(selection=True)
        if not selection:
            cmds.error("Must have reference bone selected")
        return core.initialize_character(selection[-1], unlock_channels=True)

    @classmethod
    def is_initialized(cls):
        return core.get_character()

    @classmethod
    def refresh_char_configuration(cls):
        """Read the mapping from the scene.

        Returns:
            dict: ``{bone: {"target": control, "sub_ik": [controls]}}``.
        """
        cls.char_config = core.get_mapping()
        return cls.char_config

    @classmethod
    def set_list_of_bones_from_selection(cls, bones_list, ctrls, do_mirror=False):
        pairs, _ = core.pair_selection(list(bones_list), _names(ctrls), do_mirror)
        return core.map_bones(core.require_character(), pairs, unlock_channels=True)

    @classmethod
    def get_locked_ctrls(cls, ctrl_list):
        return core.get_locked_controls(_names(ctrl_list))

    @classmethod
    def unlock_ctrls_srt(cls, ctrl_list):
        core.unlock_controls(_names(ctrl_list))

    @classmethod
    def export_char_configuration(cls, file_path=None):
        """Export the mapping to a ``.hikm`` file (asks when no path)."""
        file_path = file_path or _ask_path(0)
        if not file_path:
            return None
        core.export_mapping(file_path)
        return file_path

    @classmethod
    def import_char_configuration(cls, file_path=None, namespace=None):
        """Import a ``.hikm`` file (asks when no path)."""
        file_path = file_path or _ask_path(1)
        if not file_path:
            return None
        core.import_mapping(file_path, namespace=namespace, unlock_channels=True)
        return cls.refresh_char_configuration()

    @classmethod
    def set_sub_ik(cls, bone_target, sub_ik_ctls, do_mirror=False):
        return core.set_sub_ik(
            str(bone_target), _names(sub_ik_ctls), do_mirror, unlock_channels=True
        )

    @classmethod
    def clear_sub_ik(cls, bone_target):
        return core.clear_sub_ik(str(bone_target))

    @classmethod
    def sub_iks_binding(cls, activate=True):
        mapping = core.get_mapping()
        if activate:
            return core.bind_sub_iks(mapping)[0]
        core.unbind_sub_iks(mapping)

    @classmethod
    def get_sub_ik_bake_attrs(cls):
        mapping = core.get_mapping()
        constraints, plugs = core.bind_sub_iks(mapping)
        if constraints:
            cmds.delete(constraints)
        return plugs

    @classmethod
    def get_all_controls(cls):
        return core.mapped_controls(core.get_mapping())

    @classmethod
    def bake(cls, *args):
        """Bake the current source over the playback range."""
        return core.bake(unlock_channels=True)

    @classmethod
    def batch_bake(cls, file_list, timeline=False):
        mode = batch.MODE_TIMELINE if timeline else batch.MODE_LAYERS
        return batch.batch_bake(file_list, mode=mode, unlock_channels=True)


def show(*args):
    """Open the HumanIK Mapper window."""
    from mgear.animbits.human_ik_mapper import ui

    return ui.show()
