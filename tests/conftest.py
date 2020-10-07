
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
