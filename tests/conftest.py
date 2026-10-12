"""Pytest conftest module

Shared fixtures for the mGear tests.

Importing ``mgear`` needs Maya, so run the tests with ``mayapy``::

    mayapy -m pytest -v

Without Maya (for example on the GitHub Actions runners) every test that
uses the ``setup_path`` or ``run_with_maya_standalone`` fixtures is skipped.
"""

# Stdlib imports
import os
import sys

# Pytest imports
import pytest

_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "release", "scripts")
)
_PLATFORMS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "release", "platforms")
)


def pytest_configure(config):
    """Create the GUI QApplication before Maya starts.

    Widget tests need a GUI QApplication, and maya.standalone.initialize()
    creates a non-GUI one if none exists yet. This hook runs before test
    collection, so before the run_with_maya_standalone fixture. Skipped when
    no PySide binding is installed (e.g. CI without Maya).
    """
    try:
        from PySide6 import QtWidgets
    except ImportError:
        try:
            from PySide2 import QtWidgets
        except ImportError:
            return
    config._mgear_qt_app = QtWidgets.QApplication.instance() or (
        QtWidgets.QApplication([])
    )


@pytest.fixture(scope="session")
def run_with_maya_standalone():
    """Initialize maya.standalone for the test session.

    Skips the test when Maya is not available.
    """
    standalone = pytest.importorskip("maya.standalone")
    standalone.initialize(name="python")
    yield
    standalone.uninitialize()


@pytest.fixture(scope="session")
def setup_path(run_with_maya_standalone):
    """Make ``mgear`` importable from this repository.

    Adds ``release/scripts`` to ``sys.path``. Importing ``mgear`` needs
    Maya, so this also starts maya.standalone.
    """
    if _SCRIPTS not in sys.path:
        sys.path.insert(0, _SCRIPTS)


@pytest.fixture(scope="session")
def scripts_path():
    """Path of the release/scripts folder of this repository."""
    return _SCRIPTS


@pytest.fixture(scope="session")
def load_repo_plugin(run_with_maya_standalone):
    """Function loading a plug-in built in this repository.

    The plug-in built for the running Maya in ``release/platforms`` is
    loaded first, else the installed plug-in with the same name.

    Returns:
        callable: Called with the plug-in name without extension, returns
            True if the plug-in is loaded.
    """
    from maya import cmds

    def load(name):
        if cmds.pluginInfo(name, query=True, loaded=True):
            return True
        version = cmds.about(majorVersion=True)
        path = os.path.join(
            _PLATFORMS, version, "windows", "x64", "plug-ins", name + ".mll"
        )
        try:
            cmds.loadPlugin(path if os.path.exists(path) else name)
        except RuntimeError:
            return False
        return True

    return load


@pytest.fixture
def dagmenu(setup_path):
    """The mgear.core.dagmenu package."""
    from mgear.core import dagmenu

    return dagmenu


@pytest.fixture
def qt_app(setup_path):
    """GUI QApplication running alongside maya.standalone.

    Skips the test when only a non-GUI application is available.
    """
    from mgear.vendor.Qt import QtWidgets

    app = QtWidgets.QApplication.instance()
    if not isinstance(app, QtWidgets.QApplication):
        pytest.skip("No GUI QApplication available")
    yield app


@pytest.fixture
def clean_settings(qt_app):
    """mGear user settings, restored to their prior state after the test.

    Yields the shared settings object (mgear.core.pyqt.get_user_settings).
    """
    from mgear.core import pyqt

    settings = pyqt.get_user_settings()
    saved = {key: settings.value(key) for key in settings.allKeys()}
    yield settings
    for key in settings.allKeys():
        if key not in saved:
            settings.remove(key)
    for key, value in saved.items():
        settings.setValue(key, value)
    settings.sync()


@pytest.fixture(scope="session")
def rig_plugins(load_repo_plugin):
    """Load the plug-ins a Shifter build needs, or skip the test."""
    for name in ("mgear_solvers", "mGearWeightDriver"):
        if not load_repo_plugin(name):
            pytest.skip("{} plug-in not available".format(name))


@pytest.fixture
def count_calls(monkeypatch):
    """Function recording the calls made to a patched function.

    Returns:
        callable: Called with ``owner`` (module, class or object), ``name``
            (attribute name of the function to patch) and optionally
            ``record`` (callable taking the call args and kwargs and
            returning the value to record, or None to skip the call) and
            ``patcher`` (a monkeypatch to patch with, e.g. from
            ``monkeypatch.context()``). Returns the list of recorded values,
            the call args by default.
    """

    def count(owner, name, record=None, patcher=None):
        calls = []
        original = getattr(owner, name)

        def counting(*args, **kwargs):
            value = record(args, kwargs) if record else args
            if value is not None:
                calls.append(value)
            return original(*args, **kwargs)

        (patcher or monkeypatch).setattr(owner, name, counting)
        return calls

    return count


@pytest.fixture
def blue_pencil(run_with_maya_standalone):
    """Function loading the bluePencil plug-in, a known slow plug-in.

    bluePencil is unloaded before and after the test, so it can't slow down
    the rest of the suite. Skips the test when it can't load.

    Returns:
        callable: Loads bluePencil.
    """
    from maya import cmds

    def unload():
        if cmds.pluginInfo("bluePencil", query=True, loaded=True):
            cmds.unloadPlugin("bluePencil", force=True)

    def load():
        try:
            cmds.loadPlugin("bluePencil", quiet=True)
        except RuntimeError:
            pytest.skip("bluePencil plug-in not available")

    unload()
    yield load
    unload()


@pytest.fixture
def selection_bookmarks(setup_path, tmp_path, monkeypatch):
    """The selection bookmarks module in a new scene.

    Its settings go to a temporary INI file and its tool registry starts
    empty, so tests never touch the user's settings.
    """
    from maya import cmds
    from mgear.vendor.Qt import QtCore
    from mgear.core import selection_bookmarks as module

    cmds.file(new=True, force=True)
    ini = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        module,
        "get_user_settings",
        lambda: QtCore.QSettings(ini, QtCore.QSettings.IniFormat),
    )
    monkeypatch.setattr(module, "_registered_tools", {})
    return module


def _eye_loop(cmds, mesh, center_x, ring):
    """Vertex ring around the +Z pole of a face sphere at center_x."""
    from mgear.core import meshNavigation

    count = cmds.polyEvaluate(mesh, vertex=True)
    points = meshNavigation.get_vertex_world_positions(mesh, range(count))
    pole = max(
        range(count),
        key=lambda i: points[i][2] - abs(points[i][0] - center_x),
    )
    return meshNavigation.get_concentric_vertex_rings(mesh, [pole], ring)[ring]


@pytest.fixture
def eye_face(setup_path, load_repo_plugin):
    """Symmetric face mesh with a left and a right eye, in a new scene.

    The face is two 20x20 spheres facing +Z at x=1 and x=-1, combined. Each
    eyelid loop is the third vertex ring around a sphere pole, and each
    eyeball sits behind it. Skips when mgear_solvers can't load.

    Returns:
        dict: "mesh", "head_jnt", and per side ("L", "R") the eyeball,
            "vertices" and "edges" (loop indices), and "vertex_loop" and
            "edge_loop" (component strings).
    """
    from maya import cmds
    from mgear.core import meshNavigation

    cmds.file(new=True, force=True)
    if not load_repo_plugin("mgear_solvers"):
        pytest.skip("mgear_solvers plug-in not available")
    parts = []
    for x in (1.0, -1.0):
        part = cmds.polySphere(
            radius=1,
            subdivisionsAxis=20,
            subdivisionsHeight=20,
            constructionHistory=False,
        )[0]
        cmds.setAttr(part + ".rotateX", 90)
        cmds.setAttr(part + ".translateX", x)
        parts.append(part)
    mesh = cmds.polyUnite(parts, name="face", constructionHistory=False)[0]
    cmds.select(clear=True)
    face = {"mesh": mesh, "head_jnt": cmds.joint(name="head_jnt")}
    for side, x in (("L", 1.0), ("R", -1.0)):
        eyeball = cmds.polySphere(
            name="eye_{}_geo".format(side), radius=0.3, constructionHistory=False
        )[0]
        cmds.setAttr(eyeball + ".translate", x, 0, 0.75)
        vertices = _eye_loop(cmds, mesh, x, 3)
        edges = cmds.ls(
            cmds.polyListComponentConversion(
                ["{}.vtx[{}]".format(mesh, v) for v in vertices],
                toEdge=True,
                internal=True,
            ),
            flatten=True,
        )
        edge_indices = [int(e.split("[")[1][:-1]) for e in edges]
        face[side] = {
            "eyeball": eyeball,
            "vertices": vertices,
            "edges": edge_indices,
            "edge_loop": meshNavigation.format_component_string(
                mesh, "edge", edge_indices
            ),
            "vertex_loop": meshNavigation.format_component_string(
                mesh, "vertex", vertices
            ),
        }
    return face
