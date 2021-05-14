
""" flex.decorators

flex.decorators module contains utility functions that you can use as functions
decorators.

:module: flex.decorators
"""

# imports
from maya import cmds
import time
from mgear.flex import logger
from mgear.flex.flex_widget import FLEX_UI_NAME


def finished_running(function):
    """ Displays a end of process viewport message

    :param function: your decorated function
    :type function: function

    :return: your decorated function
    :rtype: function
    """

    def wrapper_function(*args, **kwars):
        # runs decorated function
        function_exec = function(*args, **kwars)

        cmds.inViewMessage(message="Flex Finished running...", fade=True,
                           position="midCenter", fontSize=30, fadeStayTime=500,
                           fadeOutTime=100, dragKill=True, bkc=0x00154060,
                           alpha=0.7)

        return function_exec
    return wrapper_function


def hold_selection(function):
    """ Holds the current Maya selection after running the function

    :param function: your decorated function
    :type function: function

    :return: your decorated function
    :rtype: function
    """

    def wrapper_function(*args, **kwars):

        # gets selection
        sel = cmds.ls(selection=True)
        logger.debug("Holding selection: {}".format(sel))

        # runs decorated function
        function_exec = function(*args, **kwars)

        # selects back
        cmds.select(sel, replace=True)

        return function_exec
    return wrapper_function


def isolate_view(function):
    """ Isolates the view panels while function is running

    :param function: your decorated function
    :type function: function

    :return: your decorated function
    :rtype: function
    """

    def wrapper_function(*args, **kwars):

        if not cmds.about(batch=True):
            # get panels views
            model_panels = cmds.getPanel(type="modelPanel")

            logger.debug("Isolating views")

            # isolate views
            for model_panel in model_panels:
                cmds.isolateSelect(model_panel, state=True)

                # clear isolated panel set
                isolate_set = cmds.isolateSelect(model_panel, query=True,
                                                 viewObjects=True)
                if isolate_set:
                    cmds.sets(clear=isolate_set)

            # forces view refresh
            cmds.refresh()

        # runs decorated function
        function_exec = function(*args, **kwars)

        return function_exec
    return wrapper_function


def set_focus(function):
    """ Set focus on Flex window

    Sets focus on Flex UI.

    :param function: your decorated function
    :type function: function

    :return: your decorated function
    :rtype: function
    """

    def wrapper_function(*args, **kwars):
        # runs decorated function
        function_exec = function(*args, **kwars)

        if not cmds.about(batch=True):

            logger.debug("Focusing Flex window: {}".format(FLEX_UI_NAME))
            # sets focus on Flex window
            cmds.setFocus(FLEX_UI_NAME)

        return function_exec
    return wrapper_function


def show_view(function):
    """ Shows the isolated views panels after function runs

    :param function: your decorated function
    :type function: function

    :return: your decorated function
    :rtype: function
    """

    def wrapper_function(*args, **kwars):
        # runs decorated function
        function_exec = function(*args, **kwars)

        # get panels and set isolation state to off
        if not cmds.about(batch=True):
            logger.debug("Showing views")

            model_panels = cmds.getPanel(type="modelPanel")
            for model_panel in model_panels:
                cmds.isolateSelect(model_panel, state=False)

        return function_exec
    return wrapper_function


def timer(function):
    """ Function timer

    Simple timer function decorator that you can use on Flex to time your code
    execution

    :param function: your decorated function
    :type function: function

    :return: your decorated function
    :rtype: function
    """

    def wrapper_function(*args, **kwars):
        # gets current time
        t1 = time.time()

        # runs decorated function
        function_exec = function(*args, **kwars)

        # gets new time
        t2 = time.time() - t1

        logger.debug('function: {} took {}'.format(function.__name__, t2))

        return function_exec
    return wrapper_function
