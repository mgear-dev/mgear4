"""Utilitie functions"""


import os
import sys
import timeit
from functools import wraps

from maya import cmds
import pymel.core as pm
from maya import mel
from .six import string_types, PY2

import mgear


##########################################################
# UTILS
##########################################################

def as_pynode(obj):
    """Check and convert a given string to Pynode

    If the object is not str or unicode or PyNode will raise type error

    Args:
        obj (str, unicode, PyNode): Object to check and/or convert to PyNode

    Returns:
        PyNode: the pynode object
    """
    if isinstance(obj, str) or isinstance(obj, string_types):
        obj = pm.PyNode(obj)

    if not isinstance(obj, pm.PyNode):
        raise TypeError("{} is type {} not str, unicode or PyNode".format(
            str(obj), type(obj)))

    return obj


def is_odd(num):
    """Check if the number is odd.

    Arguments:
    num (int): the number

    Returns:
        bool: True or False
    """
    return num % 2


def gatherCustomModuleDirectories(envvarkey,
                                  defaultModulePath,
                                  component=False):
    """returns component directory

    Arguments:
        envvarkey: The environment variable key name, that is searched
        defaultModulePath: The default module path for search in.

    Returns:
        Dict{string: []string}

    """
    results = {}

    # from default path
    if not isinstance(defaultModulePath, list):
        defaultModulePath = [defaultModulePath]
    for dp in defaultModulePath:
        if not os.path.exists(dp):
            message = "= GEAR RIG SYSTEM ====== notify:"
            message += "\n  default module directory is not " \
                       "found at {}".format(dp)
            message += "\n\n check your mGear installation"
            message += " or call your system administrator."
            message += "\n"
            mgear.log(message, mgear.sev_error)
            return {}

        results[dp] = sorted(os.listdir(dp))

    # from environment variables
    envvarval = os.environ.get(envvarkey, "")
    for path in envvarval.split(os.pathsep):

        if not path or not os.path.exists(path):
            continue
        if component:
            init_py_path = os.path.join(path, "__init__.py")
            if not os.path.exists(init_py_path):
                message = "= GEAR RIG SYSTEM ====== notify:"
                message += "\n  __init__.py for custom component not " \
                           "found {}".format(init_py_path)
                message += "\n\n check your module definition file or " \
                           "environment variable 'MGEAR_COMPONENTS_PATH'"
                message += " or call your system administrator."
                message += "\n"
                mgear.log(message, mgear.sev_error)
                continue

        modules = sorted(os.listdir(path))
        modules = [x for x in modules if os.path.isdir(os.path.join(path, x))]

        results[path] = modules

    return results


def getModuleBasePath(directories, moduleName):
    """search component path"""

    if PY2:
        dic_items = directories.iteritems
    else:
        dic_items = directories.items
    for basepath, modules in dic_items():
        if moduleName in modules:
            # moduleBasePath = os.path.basename(basepath)
            moduleBasePath = basepath
            break
    else:
        moduleBasePath = ""
        message = "= GEAR RIG SYSTEM ======"
        message += "component base directory not found " \
                   " for {}".format(moduleName)
        mgear.log(message, mgear.sev_error)

    return moduleBasePath


def importFromStandardOrCustomDirectories(directories,
                                          defaultFormatter,
                                          customFormatter,
                                          moduleName):
    """Return imported module

    Arguments:
        directories: the directories for search in. this is got by
            gatherCustomModuleDirectories
        defaultFormatter: this represents module structure for default
            module. for example "mgear.core.shifter.component.{}"
        customFormatter:  this represents module structure for custom
            module. for example "{0}.{1}"

    Returns:
        module: imported module

    """
    # Import module and get class
    level = -1 if sys.version_info < (3, 3) else 0
    try:
        module_name = defaultFormatter.format(moduleName)
        module = __import__(module_name, globals(), locals(), ["*"], level)

    except ImportError:
        moduleBasePath = getModuleBasePath(directories, moduleName)
        module_name = customFormatter.format(moduleName)
        if pm.dirmap(cd=moduleBasePath) not in sys.path:
            sys.path.append(pm.dirmap(cd=moduleBasePath))
        module = __import__(module_name, globals(), locals(), ["*"], level)

    return module


# -----------------------------------------------------------------------------
# Decorators
# -----------------------------------------------------------------------------
def viewport_off(func):
    """Decorator - Turn off Maya display while func is running.

    if func will fail, the error will be raised after.

    type: (function) -> function

    """
    @wraps(func)
    def wrap(*args, **kwargs):
        # type: (*str, **str) -> None

        # Turn $gMainPane Off:
        gMainPane = mel.eval('global string $gMainPane; $temp = $gMainPane;')
        cmds.paneLayout(gMainPane, edit=True, manage=False)

        try:
            return func(*args, **kwargs)

        except Exception as e:
            raise e

        finally:
            cmds.paneLayout(gMainPane, edit=True, manage=True)

    return wrap


def one_undo(func):
    """Decorator - guarantee close chunk.

    type: (function) -> function

    """
    @wraps(func)
    def wrap(*args, **kwargs):
        # type: (*str, **str) -> None

        try:
            cmds.undoInfo(openChunk=True)
            return func(*args, **kwargs)

        except Exception as e:
            raise e

        finally:
            cmds.undoInfo(closeChunk=True)

    return wrap


def timeFunc(func):
    """Use as a property to time any desired function
    """
    @wraps(func)
    def wrap(*args, **kwargs):
        start = timeit.default_timer()
        try:
            return func(*args, **kwargs)

        except Exception as e:
            raise e

        finally:
            end = timeit.default_timer()
            timeConsumed = end - start
            print(("{} time elapsed running {}".format(timeConsumed,
                                                       func.__name__)))

    return wrap

# -----------------------------------------------------------------------------
# selection Decorators
# -----------------------------------------------------------------------------


def _filter_selection(selection, sel_type="nurbsCurve"):
    filtered_sel = []
    for node in selection:
        if node.getShape().type() == sel_type:
            filtered_sel.append(node)
    return filtered_sel


def filter_nurbs_curve_selection(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        args = list(args)
        args[0] = _filter_selection(args[0])
        return func(*args, **kwargs)

    return wrap
