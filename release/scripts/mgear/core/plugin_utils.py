import os, sys
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

                    # Check if filetype exists, and removes it
                    if file.find('.') > -1:
                        parts = file.split('.')
                        name = ".".join(parts[:-1])

                    plugins.append((name, os.path.join(path, file)))

    return plugins


def get_available_plugin(plugin_name):
    """
    Returns any available plugin paths that match the plugin_name specified.
    """
    all_plugins = get_all_available_plugins()
    available_plugins = []

    for plugin in all_plugins:
        if plugin[0] == plugin_name:
            available_plugins.append(plugin)

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


def unload_plugin(plugin_name, plugin_path=None):
    """
    Unloads a plugin.
    If plugin_path is not None, then a check is performed to make sure the plugin found, 
    is the same plugin at the path. As it is possible to have multiple plugins with the same name at differnt locations.
    """
    if cmds.pluginInfo(plugin_name, q=True, loaded=True):
        found_plugin_path = cmds.pluginInfo(plugin_name, query=True, path=True)

        # Checks if the plugin path is the correct path for the loaded plugin
        if plugin_path:
            if plugin_path != found_plugin_path:
                print("Unable to unload, plugin path was not loaded to begin with.")
                print("   Path: "+ plugin_path)
                return

        try:
            cmds.unloadPlugin(plugin_name)
            print("Unloaded plugin: ", plugin_name, "from path:", found_plugin_path)
        except RuntimeError as e:
            print("Failed to unload plugin: ", plugin_name)
            print("Error:", e)


def load_plugin(plugin_name, plugin_path):
    # Check if plugin already exists and is loaded
    if cmds.pluginInfo(plugin_name, q=True, loaded=True):
        loaded_path = cmds.pluginInfo(plugin_name, q=True, path=True)
        #print(loaded_path)
        if loaded_path.lower() == plugin_path.lower():
            msg = "The plugin is already loaded from the correct path: {}"
            print(msg.format(plugin_name))
            return True
        else:
            unload_plugin(plugin_name, loaded_path)

    # Load specified plugin
    try:
        cmds.loadPlugin(plugin_path)
        print(
            "Loaded plugin: ", plugin_name, "from path:", plugin_path
        )
        return True
    except RuntimeError as e:
        print("Failed to load plugin: ", plugin_name)
        print("Error:", e)
        return False


# Function to load a plugin based on the path
def load_plugin_with_path(plugin_tuples, dir_name):
    # Check if the desired plugin is already loaded
    for plugin_name, plugin_path in plugin_tuples:
        if dir_name.lower() in plugin_path.lower() and cmds.pluginInfo(
            plugin_name, q=True, loaded=True
        ):
            loaded_path = cmds.pluginInfo(plugin_name, q=True, path=True)
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
                cmds.loadPlugin(plugin_path)
                print(
                    "Loaded plugin: ", plugin_name, "from path:", plugin_path
                )
                return True
            except RuntimeError as e:
                print("Failed to load plugin: ", plugin_name)
                print("Error:", e)
    return False


def get_plugin_version(plugin_name):
    if cmds.pluginInfo(plugin_name, q=True, loaded=True):
        return cmds.pluginInfo(plugin_name, q=True, version=True)
    else:
        return None
