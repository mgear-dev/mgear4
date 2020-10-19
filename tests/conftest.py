"""Pytest conftest module

In this file you will find all **fixtures** that you are used while running
mgear tests.

Github Actions workflow will run Pytest but because their clusters will not have
Autodesk Maya install / neither PyMel, most of the tests will be skip.

In order to ensure all tests are correctly executed you must run them locally
with both Maya and PyMel installed.
"""

# Stdlib imports
import sys
import os

# Pytest imports
import pytest


@pytest.fixture(scope='session')
def mock_maya_module():
    """Mocks Maya python module
    """

    def maya_module():
        return

    maya = type(sys)('maya')
    maya.cmds = maya_module
    maya.standalone = maya_module
    sys.modules['maya'] = maya


@pytest.fixture(scope='session')
def setup_path():
    """ Adds python dependencies to sys.path

    Note:
        Add here python path packages if needed.
    """

    # adds anim_scene_builder to python path
    sys.path.insert(0, os.path.abspath("./python"))
    sys.path.insert(0, os.path.abspath("./mgear4/python"))


@pytest.fixture(scope='session')
def run_with_maya_standalone():
    from maya import standalone
    standalone.initialize(name="python")
    yield
    standalone.uninitialize()


@pytest.fixture(scope='session')
def run_with_maya_pymel():
    import pymel.core as pm
    yield
