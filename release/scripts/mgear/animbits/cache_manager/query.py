
# imports
from __future__ import absolute_import
from datetime import datetime
import os
import json
from maya import cmds

# ==============================================================================
# CONSTANTS
# ==============================================================================

_MANAGER_CACHE_DESTINATION = os.getenv("MGEAR_CACHE_MANAGER_CACHE_DESTINATION")
_MANAGER_MODEL_GROUP = os.getenv("MGEAR_CACHE_MANAGER_MODEL_GROUP")
_MANAGER_PREFERENCE_FILE = "animbits_cache_manager.json"
_MANAGER_PREFERENCE_PATH = "{}/mGear".format(os.getenv("MAYA_APP_DIR"))
_MANAGER_RIG_ATTRIBUTE = os.getenv("MGEAR_CACHE_MANAGER_RIG_ATTRIBUTE")
# ==============================================================================


def find_model_group_inside_rig(geo_node, rig_node):
    """ Finds the given group name inside the hierarchy of a rig

    Args:
        geo_node (str): geometry group transform node containing the shapes to
                        cache
        rig_node (str): Rig root node containing the geo_node

    Returns:
        str or None: Full path to the geo_node if found else None
    """

    try:
        model_group = None
        for x in cmds.ls(cmds.listRelatives(rig_node, allDescendents=True,
                                            fullPath=True), type="transform"):
            if x.split("|")[-1].split(":")[-1] == geo_node:
                model_group = x
                break

        if not model_group:
            for x in cmds.ls(cmds.listRelatives(cmds.listRelatives(
                             rig_node, parent=True)[0], allDescendents=True,
                             fullPath=True), type="transform"):
                if x.split("|")[-1].split(":")[-1] == geo_node:
                    model_group = x
                    break

        if model_group:
            return model_group
        else:
            print("Could not find the geo node inside the rig node.")

    except Exception as e:
        if cmds.objExists("{}_cache".format(rig_node)):
            return
        print("Could not find the geo node inside the rig node. "
              "Contact mGear's developers reporting this issue to get help")
        raise e


def get_cache_destination_path():
    """ Returns the cache destination path

    This methods returns a path pointing to where the cache manager will store
    the GPU caches.

    If the **MGEAR_CACHE_MANAGER_CACHE_DESTINATION** environment
    variable has been set it will return whatever path has been set if valid.
    If none has been set or fails to use that path this method tries then
    to return whatever settings has been set on the **cache manager preferences
    file**.

    Finally if no environment variable or preference file is been set then we
    use the **OS TEMP** folder as destination path.

    Returns:
        str: cache destination path
    """

    # if env variable is set
    if (_MANAGER_CACHE_DESTINATION and
            os.path.exists(_MANAGER_CACHE_DESTINATION)):
        return _MANAGER_CACHE_DESTINATION

    # if pref file exists
    cache_path = get_preference_file_cache_destination_path()
    if cache_path:
        return cache_path

    # returns temp. folder
    return os.getenv("TMPDIR")


def get_time_stamp():
    """ Returns the date and time in a file name friendly way

    This is used to create the cache file name a unique name in order to avoid
    clashing files overwriting other cache files been used on other specific
    file scenes

    Returns:
        str: time stamp (19-05-12_14-10-55) year-month-day_hour-minutes-seconds
    """

    return datetime.now().strftime('%y-%m-%d_%H-%M-%S')


def get_model_group(ignore_selection=False):
    """ Returns the model group name to cache

    This methods returns a string with the name of the transform node to use
    when caching the geometry/model

    If the **MGEAR_CACHE_MANAGER_MODEL_GROUP** environment
    variable has been set it will return the name stored in it.
    If none has been set or fails to use that name this method tries then
    to return whatever settings has been set on the **cache manager preferences
    file**.

    Finally if no environment variable or preference file is been set then we
    fall back to selection.

    This doesn't check if the returner values is a valid value like if the
    transform node exists. This is because we do not know at this stage if the
    asset it inside a namespace or something scene specific. As this is generic
    only checks for that generic part are been made.

    Args:
        ignore_selection (bool): whether it falls back to the selected group

    Returns:
        str or None: group name if anything or None
    """

    # if env variable is set
    if _MANAGER_MODEL_GROUP:
        return _MANAGER_MODEL_GROUP

    # if pref file exists
    model_group = get_preference_file_model_group()
    if model_group:
        return model_group

    # returns selection
    selection = cmds.ls(selection=True)
    if selection and not ignore_selection:
        return selection[0]


def get_preference_file():
    """ Returns the preference file path and name

    Returns:
        str: preference file path and name
    """

    return "{}/{}".format(_MANAGER_PREFERENCE_PATH, _MANAGER_PREFERENCE_FILE)


def get_preference_file_cache_destination_path():
    """ Returns the folder path set on the preference file

    Returns:
        str or None: The path stored in the preference file or None if invalid
    """

    return read_preference_key(search_key="cache_manager_cache_path")


def get_preference_file_model_group():
    """ Returns the model group name set on the preference file

    Returns:
        str or None: Model group name stored in the preference file
                     or None if invalid
    """

    return read_preference_key(search_key="cache_manager_model_group")


def get_scene_rigs():
    """ The rigs from current Maya session

    This method search for rigs in your current Maya scene.
    If the MGEAR_CACHE_MANAGER_RIG_ATTRIBUTE has been set it will try to find
    rigs based on the attribute set on the environment variable. Otherwise
    it will use the attribute **gear_version** in order to find rigs in scene.

    Returns:
        list or None: mGear rig top node or None
    """

    if _MANAGER_RIG_ATTRIBUTE:
        try:
            rigs = [x.split(".")[0] for x in cmds.ls(
                "*.{}".format(_MANAGER_RIG_ATTRIBUTE), recursive=True)]
        except RuntimeError:
            raise ValueError("Invalid attribute key: {} - is not a valid "
                             "attribute key to set on the "
                             "MGEAR_CACHE_MANAGER_RIG_ATTRIBUTE variable"
                             .format(_MANAGER_RIG_ATTRIBUTE))
    else:
        rigs = [x.split(".")[0] for x in cmds.ls("*.is_rig", recursive=True)]

    # we query the gpu caches node rig_link custom attribute in the scene
    # in order to keep the returned value accurate.
    # If we have a scene in which a rig has already been cached and the
    # reference unloaded we can't find the rig node anymore on the scene so
    # we use the custom attribute added by the load_gpu_cache method to query
    # caches been created by the cache manager.
    [rigs.append(cmds.getAttr("{}.rig_link".format(x)))
     for x in cmds.ls(type="gpuCache")
     if cmds.objExists("{}.rig_link".format(x))
     and cmds.getAttr("{}.rig_link".format(x)) not in rigs]

    return rigs or None


def get_timeline_values():
    """ Returns the min and max keyframe values from the current playback range

    In order to give more freedom to the artist we always evaluate the playback
    range and not the animation range so that artists can choose what range
    to use when creating the GPU cache

    Returns:
        float, float: min and max value
    """

    # get user timeline playback frame range
    _min = cmds.playbackOptions(query=True, minTime=True)
    _max = cmds.playbackOptions(query=True, maxTime=True)

    return _min, _max


def is_rig(rig_node):
    """ Returns whether the given rig node is in srig state or caching state

    Args:
        rig_node (str): rig node name
    """

    if not cmds.objExists(rig_node) or (
            cmds.objExists("{}_cache".format(rig_node))):
        return False

    return True


def read_preference_key(search_key):
    """ Returns the preference stored on the pref file for the given key

    Returns:
        str or None: The path stored in the preference file or None if invalid
    """

    # preference file
    pref_file = get_preference_file()

    try:
        with open(pref_file, 'r') as file_r:
            # reads json file and get the preference
            json_dict = json.load(file_r)
            value = json_dict[search_key]

            if type(value) == int:
                return value

            if len(value) and type(value) != int:
                return value

            print("Key -{}- saved on preference file is invalid for {}"
                  .format(value, search_key))

    except Exception as e:
        message = "Contact mGear's developers reporting this issue to get help"
        print("{} - {} / {}".format(type(e).__name__, e,
                                    message))
        return
