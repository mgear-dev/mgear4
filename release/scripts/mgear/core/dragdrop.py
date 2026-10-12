"""
drag and drop logic for mGear overrides of maya's default behavior

Dropped files are routed by extension through a registry of drop handlers.
Handlers of the mGear tools are ``"module:function"`` strings, imported only
when such a file is dropped, so this module loads no tool. Tools and studio
scripts can add their own formats with :func:`register_drop_handler`.

Example:
    >>> from mgear.core import dragdrop
    >>> dragdrop.register_drop_handler(
    ...     ".abc_cfg", "studio.abc_tool:import_file", "ABC Config"
    ... )
"""

# Stdlib imports
from __future__ import absolute_import

import collections
import contextlib
import importlib
import logging
import os

# Maya imports
from maya import mel
from maya import cmds
import mgear.pymaya as pm

# mGear
from mgear.core import utils

logger = logging.getLogger("mgear.core.dragdrop")

DropHandler = collections.namedtuple("DropHandler", ("label", "handler", "undo"))

# lower-case extension to DropHandler
_HANDLERS = {}

# mel override procs
MEL_OVERRIDE_CMD = r"""
//  Override the default performFileDropAction with mGears, with user approval
//  Use: Enable from the mGear > Utilities > Enable mGear file drop
//  Shout out Randall Hess

global proc int
performFileDropAction (string $theFile)
{
    string $pycmd = "from mgear.core import dragdrop;dragdrop.mgear_file_drop_action(\"" + encodeString($theFile) + "\")";
    int $result = python($pycmd);
    return($result);
}
"""


# file drop functions ---------------------------------------------------------


def get_original_file_drop_action():
    """get the original performOriginalFileDropAction.mel, but check
    for custom override mel from another source first

    Returns:
        str: path to PerformFileDropAction.mel, custom or AD
    """
    # look for custom performFileDropAction
    mel_string_start = "Mel procedure found in: "
    orig_mel_file_str = mel.eval("whatIs performFileDropAction")
    if orig_mel_file_str.startswith(mel_string_start):
        return orig_mel_file_str.replace(mel_string_start, "")

    # if not custom, find vanilla AD
    mel_string_start = "Script found in: "
    orig_mel_file_str = mel.eval("whatIs performFileDropAction.mel")
    if orig_mel_file_str.startswith(mel_string_start):
        return orig_mel_file_str.replace(mel_string_start, "")


def get_mgear_file_drop_state():
    """get the option variable from maya to check if mGear override
    is requested

    Returns:
        int: 0 or 1, state of override
    """
    if not cmds.optionVar(exists="mgear_file_drop_OV"):
        cmds.optionVar(intValue=("mgear_file_drop_OV", 0))
    return cmds.optionVar(query="mgear_file_drop_OV")


def set_mgear_file_drop_state(state):
    """set the override state with maya option variable

    Args:
        state (bool, int): 0, 1, True, False
    """
    cmds.optionVar(intValue=("mgear_file_drop_OV", int(state)))


def mgear_file_drop_toggle(new_state):
    """toggle the state of the mgear override. False will reuse original

    Args:
        new_state (bool): from checkbox UI
    """
    set_mgear_file_drop_state(new_state)
    if new_state:
        mel_cmd = MEL_OVERRIDE_CMD
    else:
        if _ORIGINAL_FILEDROP_FILEPATH:
            mel_cmd = 'source "{}";'.format(_ORIGINAL_FILEDROP_FILEPATH)
        else:
            mel_cmd = 'source performFileDropAction.mel'
    mel.eval(mel_cmd)


def register_drop_handler(ext, handler, label, undo=True):
    """Register the handler of a dropped file extension.

    An extension that already has a handler gets the new one, so a studio
    tool can replace a built-in.

    Args:
        ext (str): File extension with the dot, i.e. ``".lat"``. Compared
            in lower case.
        handler (callable or str): Function called with the file path, or
            a ``"package.module:function"`` string imported on the first
            drop. It can return False to let Maya import the file.
        label (str): Readable file kind, for the log.
        undo (bool, optional): Run the handler in one undo chunk.
    """
    _HANDLERS[ext.lower()] = DropHandler(label, handler, undo)


def get_drop_handler(ext):
    """Get the drop handler of a file extension.

    Args:
        ext (str): File extension with the dot, any case.

    Returns:
        DropHandler: The handler entry, or None.
    """
    return _HANDLERS.get(ext.lower())


def get_drop_handlers():
    """Get all the drop handlers.

    Returns:
        dict: Lower-case extension to DropHandler.
    """
    return dict(_HANDLERS)


def _resolve_handler(handler):
    """Return the callable of a drop handler.

    Args:
        handler (callable or str): Callable, or ``"module:function"``.

    Returns:
        callable: The handler function.
    """
    if callable(handler):
        return handler
    module_name, _, func_name = handler.partition(":")
    return getattr(importlib.import_module(module_name), func_name)


def _mel_string(text):
    """Escape a text for a double-quoted MEL string.

    Args:
        text (str): Text, i.e. a file path.

    Returns:
        str: The text with backslashes and double quotes escaped.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _default_import(theFile):
    """Run Maya's default import on a dropped file.

    Args:
        theFile (str): filepath from the maya drop action
    """
    mel.eval('performFileImportAction("{}");'.format(_mel_string(theFile)))


def mgear_file_drop_action(theFile):
    """This action is called from the mGearFileDropAction.mel override

    The file goes to the handler of its extension, in one undo chunk and
    an error guard, or to Maya's default import when no handler matches or
    the handler returns False.

    Args:
        theFile (str): filepath from the maya drop action

    Returns:
        int: always return 1, to accept the drop action
    """
    entry = get_drop_handler(os.path.splitext(theFile)[1])
    if not entry:
        _default_import(theFile)
        return 1
    print("Import mGear {} file: {}".format(entry.label, theFile))
    if entry.undo:
        context = utils.undo_chunk("mGearFileDrop")
    else:
        context = contextlib.nullcontext()
    try:
        func = _resolve_handler(entry.handler)
        with context:
            result = func(theFile)
    except Exception as e:
        logger.exception("mGear file drop failed: %s", theFile)
        cmds.warning(
            "Could not import {} file {}: {}".format(entry.label, theFile, e)
        )
        return 1
    if result is False:
        _default_import(theFile)
    return 1


def guide_file_prompt(guide_filePath):
    """prompt dialogue for what to do with the .sgt, guide file

    Kept for older calls, see ``mgear.shifter.io.guide_file_drop``.

    Args:
        guide_filePath (str): filepath to guide
    """
    from mgear.shifter import io

    io.guide_file_drop(guide_filePath)


def wire_to_skinning_file_prompt(wts_filePath):
    """Prompt dialogue for importing a .wts wire to skinning config file.

    Kept for older calls, see ``mgear.rigbits.wire_to_skinning.core.drop_file``.

    Args:
        wts_filePath (str): filepath to .wts configuration file
    """
    from mgear.rigbits.wire_to_skinning import core

    core.drop_file(wts_filePath)


def gimmick_file_import(gst_filePath):
    """Import a .gst gimmick joints file in one undo step.

    Kept for older calls, see ``mgear.rigbits.gimmick_tool.core.import_file``.

    Args:
        gst_filePath (str): filepath to .gst gimmick joints file
    """
    from mgear.rigbits.gimmick_tool import core

    with utils.undo_chunk("importGimmickJoints"):
        core.import_file(gst_filePath)


def install_utils_menu(m):
    """Install core utils submenu

    Args:
        m (pymel.ui): where to parent the menuItem
    """

    # get state
    state = get_mgear_file_drop_state()
    if state:
        mgear_file_drop_toggle(state)

    pm.setParent(m, menu=True)
    pm.menuItem(divider=True)
    cmds.menuItem("mgear_file_drop_menuitem",
                  label="Enable mGear file drop",
                  command=mgear_file_drop_toggle,
                  checkBox=state)
    cmds.menuItem(divider=True)


# Built-in drop handlers, as register_drop_handler arguments
_BUILTIN_HANDLERS = (
    (".sgt", "mgear.shifter.io:guide_file_drop", "Guide", False),
    (".gSkinPack", "mgear.core.skin:drop_file", "Skin Pack"),
    (".gSkin", "mgear.core.skin:drop_file", "Skin"),
    (".jSkin", "mgear.core.skin:drop_file", "Skin"),
    (".rbf", "mgear.rigbits.rbf_io:importRBFs", "RBF config"),
    (
        ".wts",
        "mgear.rigbits.wire_to_skinning.core:drop_file",
        "Wire to Skinning config",
    ),
    (".gst", "mgear.rigbits.gimmick_tool.core:import_file", "Gimmick Joints"),
    (".lat", "mgear.rigbits.lattice_io.core:import_lattices", "Lattice config"),
    (
        ".shw",
        "mgear.rigbits.shrinkwrap_io.core:import_shrinkwraps",
        "Shrink Wrap config",
    ),
    (
        ".pxw",
        "mgear.rigbits.proximitywrap_io.core:import_proximitywraps",
        "Proximity Wrap config",
    ),
    (
        ".cwc",
        "mgear.rigbits.channelWrangler:applyChannelConfig",
        "Channel Wrangler config",
    ),
    (
        ".cmc",
        "mgear.animbits.channel_master_node:drop_file",
        "Channel Master config",
    ),
    (".pkr", "mgear.anim_picker:drop_file", "Anim Picker"),
    (".sbk", "mgear.animbits.bookmarks:drop_file", "Bookmarks", False),
)

for _args in _BUILTIN_HANDLERS:
    register_drop_handler(*_args)


try:
    # The variable is declared when the module is sourced
    # The idea being to find the performFilePathAction.mel preceeding
    # the mgear override
    _ORIGINAL_FILEDROP_FILEPATH
except NameError as e:
    _ORIGINAL_FILEDROP_FILEPATH = get_original_file_drop_action()
