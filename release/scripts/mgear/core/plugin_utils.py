import os, sys
import pymel.core as pm
import maya.mel as mel
import maya.cmds as cmds


def get_os():
    """
    Detects the current OS
    """
    if os.name == "posix":
        return "Linux" if "linux" in sys.platform else "macOS"
    elif os.name == "nt":
        return "Windows"
    else:
        return "Unknown"


def get_all_plugins():
    """
    Gets all loaded plugins
    """
    plugins = []

    plugin_names = cmds.pluginInfo(query=True, listPlugins=True)
    plugin_paths = cmds.pluginInfo(query=True, listPluginsPath=True)

    for name, path in zip(plugin_names, plugin_paths):
        plugins.append((name, path))

    return plugins


def get_all_available_plugins():
    """
    Gets all available plugins, that exist in the environment variables paths.
    """
    # System paths are structured differently on OSs
    if get_os == "Windows":
        plugin_paths = mel.eval("getenv MAYA_PLUG_IN_PATH").split(";")
    else:
        plugin_paths = mel.eval("getenv MAYA_PLUG_IN_PATH").split(":")

    plugins = []

    for path in plugin_paths:
        if os.path.exists(path):
            for file in os.listdir(path):
                # Check if the filename contains the name you're looking for
                if (file.endswith(".mll") or file.endswith(".so") or file.endswith(".bundle")):
                    # Create a tuple with the plugin name and path, and add it to the list
                    plugins.append((file, os.path.join(path, file)))

    return plugins


def get_available_plugin(plugin_name):
    """
    Returns any available plugin paths that match the plugin_name specified.
    """
    all_plugins = get_all_available_plugins()
    available_plugins = []

    for plugin in all_plugins:
        name = plugin[0]

        # Check if filetype exists, and removes it
        if plugin[0].find('.') > -1:
            parts = plugin[0].split('.')
            name = ".".join(parts[:-1])

        if name == plugin_name:
            available_plugins.append((name, plugin[1]))

    return available_plugins


def get_not_loaded_plugins():
    # Get all available and loaded plugins
    all_plugins = get_all_plugins()
    all_available_plugins = get_all_available_plugins()

    # Get a list of plugins that are available but not currently loaded
    not_loaded_plugins = [
        plugin for plugin in all_available_plugins if plugin not in all_plugins
    ]

    return not_loaded_plugins


# Function to unload a plugin
def unload_plugin(plugin_name, plugin_path):
    if pm.pluginInfo(plugin_name, q=True, loaded=True):
        try:
            pm.unloadPlugin(plugin_name)
            print("Unloaded plugin: ", plugin_name, "from path:", plugin_path)
        except RuntimeError as e:
            print("Failed to unload plugin: ", plugin_name)
            print("Error:", e)


# Function to load a plugin based on the path
def load_plugin_with_path(plugin_tuples, dir_name):
    # Check if the desired plugin is already loaded
    for plugin_name, plugin_path in plugin_tuples:
        if dir_name.lower() in plugin_path.lower() and pm.pluginInfo(
            plugin_name, q=True, loaded=True
        ):
            loaded_path = pm.pluginInfo(plugin_name, q=True, path=True)
            if loaded_path.lower() == plugin_path.lower():
                print(
                    "The plugin is already loaded from the correct path: ",
                    plugin_name,
                )
                return True
            else:
                unload_plugin(plugin_name, plugin_path)

    # If the desired plugin is not loaded, unload all plugins before trying to load it
    for plugin_name, plugin_path in plugin_tuples:
        unload_plugin(plugin_name, plugin_path)

    # Try to load the desired plugin
    for plugin_name, plugin_path in plugin_tuples:
        if dir_name.lower() in plugin_path.lower():
            try:
                pm.loadPlugin(plugin_path)
                print(
                    "Loaded plugin: ", plugin_name, "from path:", plugin_path
                )
                return True
            except RuntimeError as e:
                print("Failed to load plugin: ", plugin_name)
                print("Error:", e)
    return False


def get_plugin_version(plugin_name):
    if pm.pluginInfo(plugin_name, q=True, loaded=True):
        return pm.pluginInfo(plugin_name, q=True, version=True)
    else:
        return None
