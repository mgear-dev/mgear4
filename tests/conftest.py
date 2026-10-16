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
    from mgear.core import pyqt
    from mgear.core import selection_bookmarks as module

    cmds.file(new=True, force=True)
    ini = str(tmp_path / "settings.ini")
    # The module imports get_user_settings from pyqt when it needs it
    monkeypatch.setattr(
        pyqt,
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


@pytest.fixture
def lips_face(setup_path, load_repo_plugin):
    """Mouth mesh with a closed lips loop, a head and a jaw joint, in a new scene.

    The mouth is a 20x20 sphere facing +Z, wide in X and flat in Y, with its
    transform frozen. The lips loop is the third vertex ring around the +Z
    pole, so its corners are on the X axis. Skips when mgear_solvers can't
    load.

    Returns:
        dict: "mesh", "head_jnt", "jaw_jnt", "vertices" and "edges" (loop
            indices), and "vertex_loop" and "edge_loop" (component strings).
    """
    from maya import cmds
    from mgear.core import meshNavigation

    cmds.file(new=True, force=True)
    if not load_repo_plugin("mgear_solvers"):
        pytest.skip("mgear_solvers plug-in not available")
    mesh = cmds.polySphere(
        name="mouth",
        radius=1,
        subdivisionsAxis=20,
        subdivisionsHeight=20,
        constructionHistory=False,
    )[0]
    cmds.setAttr(mesh + ".rotateX", 90)
    cmds.setAttr(mesh + ".scale", 1.5, 0.6, 1.0)
    cmds.makeIdentity(mesh, apply=True, translate=True, rotate=True, scale=True)
    cmds.select(clear=True)
    head = cmds.joint(name="head_jnt", position=(0, 0, -0.5))
    jaw = cmds.joint(name="jaw_jnt", position=(0, -0.3, -0.5))
    cmds.select(clear=True)
    vertices = _eye_loop(cmds, mesh, 0.0, 3)
    edges = cmds.ls(
        cmds.polyListComponentConversion(
            ["{}.vtx[{}]".format(mesh, v) for v in vertices],
            toEdge=True,
            internal=True,
        ),
        flatten=True,
    )
    edge_indices = [int(e.split("[")[1][:-1]) for e in edges]
    return {
        "mesh": mesh,
        "head_jnt": head,
        "jaw_jnt": jaw,
        "vertices": vertices,
        "edges": edge_indices,
        "edge_loop": meshNavigation.format_component_string(mesh, "edge", edge_indices),
        "vertex_loop": meshNavigation.format_component_string(mesh, "vertex", vertices),
    }


@pytest.fixture
def brow_face(setup_path, load_repo_plugin):
    """Forehead mesh with three brow paths and a skull surface, in a new scene.

    The forehead is a 2x1 plane facing +Z, 20x10 faces, curved back with
    z = 1 - 0.3 x^2. The brow row is at y = 0.3: the left brow runs from
    x 0.2 to 0.8, the right one from -0.8 to -0.2 and the center one from
    -0.2 to 0.2, sharing the inner ends. The skull surface is a NURBS plane
    with the same curve, 0.1 behind. Skips when mgear_solvers can't load.

    Returns:
        dict: "mesh", "head_jnt", "surface", and per brow ("L", "R", "C")
            "vertices" (path from the inner end, or right to left for C)
            and "vertex_loop" and "edge_loop" (component strings).
    """
    from maya import cmds
    from mgear.core import meshNavigation

    cmds.file(new=True, force=True)
    if not load_repo_plugin("mgear_solvers"):
        pytest.skip("mgear_solvers plug-in not available")
    mesh = cmds.polyPlane(
        name="forehead",
        width=2,
        height=1,
        subdivisionsX=20,
        subdivisionsY=10,
        axis=(0, 0, 1),
        constructionHistory=False,
    )[0]
    count = cmds.polyEvaluate(mesh, vertex=True)
    positions = meshNavigation.get_vertex_world_positions(mesh, range(count))
    for index, (x, y, _) in enumerate(positions):
        cmds.xform(
            "{}.vtx[{}]".format(mesh, index),
            worldSpace=True,
            translation=(x, y, 1.0 - 0.3 * x * x),
        )
    surface = cmds.nurbsPlane(
        name="skull_srf",
        width=3,
        lengthRatio=1.0,
        axis=(0, 0, 1),
        patchesU=8,
        patchesV=8,
        constructionHistory=False,
    )[0]
    for cv in cmds.ls(surface + ".cv[*][*]", flatten=True):
        x, y, _ = cmds.pointPosition(cv, world=True)
        cmds.xform(cv, worldSpace=True, translation=(x, y, 0.9 - 0.3 * x * x))
    cmds.select(clear=True)
    face = {
        "mesh": mesh,
        "head_jnt": cmds.joint(name="head_jnt", position=(0, 0, 0)),
        "surface": surface,
    }
    cmds.select(clear=True)
    row = {round(p[0], 3): i for i, p in enumerate(positions) if abs(p[1] - 0.3) < 1e-4}
    for side, xs in (
        ("L", [0.2 + 0.1 * k for k in range(7)]),
        ("R", [-0.2 - 0.1 * k for k in range(7)]),
        ("C", [-0.2 + 0.1 * k for k in range(5)]),
    ):
        vertices = [row[round(x, 3)] for x in xs]
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
            "vertices": vertices,
            "edge_loop": meshNavigation.format_component_string(
                mesh, "edge", edge_indices
            ),
            "vertex_loop": meshNavigation.format_component_string(
                mesh, "vertex", vertices
            ),
        }
    return face


# Rounding keeps golden comparisons stable across Maya versions.
_GOLDEN_DECIMALS = 6
_GOLDEN_UPDATE_ENV = "MGEAR_UPDATE_GOLDEN"


def _normalize(value):
    """Return a JSON-compatible copy of a value with rounded floats.

    Args:
        value (object): The value to normalize (dict, list, float...).

    Returns:
        object: The normalized value.
    """
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, float):
        rounded = round(value, _GOLDEN_DECIMALS)
        return 0.0 if rounded == 0 else rounded
    return value


def _first_difference(expected, actual, path="root"):
    """Return the path of the first difference between two values.

    Args:
        expected (object): The expected value.
        actual (object): The actual value.
        path (str, optional): Path of the values, used in the message.

    Returns:
        str: A message naming the first difference, or None if equal.
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in actual:
                return "{}[{!r}] missing".format(path, key)
            if key not in expected:
                return "{}[{!r}] unexpected".format(path, key)
            diff = _first_difference(
                expected[key], actual[key], "{}[{!r}]".format(path, key)
            )
            if diff:
                return diff
        return None
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return "{} length {} != {}".format(path, len(expected), len(actual))
        for index, (exp, act) in enumerate(zip(expected, actual)):
            diff = _first_difference(exp, act, "{}[{}]".format(path, index))
            if diff:
                return diff
        return None
    if expected != actual:
        return "{}: {!r} != {!r}".format(path, expected, actual)
    return None


@pytest.fixture
def check_golden(request):
    """Function comparing data with a stored golden file, or recording it.

    Golden files are gzipped JSON in a ``data`` folder next to the test
    module. Floats are rounded, tuples become lists. With the
    ``MGEAR_UPDATE_GOLDEN`` environment variable set, the data is recorded
    and the test is skipped.

    Returns:
        callable: Called with the golden file name (without extension) and
            the data. Fails the test naming the first difference.
    """
    import gzip
    import json

    folder = os.path.join(os.path.dirname(str(request.fspath)), "data")

    def check(name, data):
        path = os.path.join(folder, name + ".json.gz")
        data = _normalize(data)
        if os.environ.get(_GOLDEN_UPDATE_ENV):
            os.makedirs(folder, exist_ok=True)
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(data, f, sort_keys=True)
            pytest.skip("Recorded {}".format(path))
        with gzip.open(path, "rt", encoding="utf-8") as f:
            expected = json.load(f)
        diff = _first_difference(expected, data)
        assert diff is None, diff

    return check


@pytest.fixture
def describe_shapes():
    """Function describing the shapes of a transform for comparisons.

    Returns:
        callable: Called with a transform name and ``names`` (bool, optional,
            default True) to include the shape names. Returns a list with one
            dict per shape, in order: name, type, degree, form, knots,
            object space CVs, override colour settings, line width,
            isHistoricallyInteresting and the source of alwaysDrawOnTop.
    """
    from maya import cmds
    from maya.api import OpenMaya

    def describe(transform, names=True):
        shapes = []
        for shape in cmds.listRelatives(transform, shapes=True, fullPath=True) or []:
            data = {"type": cmds.nodeType(shape)}
            if names:
                data["name"] = shape.split("|")[-1]
            if data["type"] == "nurbsCurve":
                sel = OpenMaya.MSelectionList()
                sel.add(shape)
                fn = OpenMaya.MFnNurbsCurve(sel.getDagPath(0))
                data["degree"] = fn.degree
                data["form"] = fn.form
                data["knots"] = list(fn.knots())
                data["cvs"] = [
                    [p.x, p.y, p.z] for p in fn.cvPositions(OpenMaya.MSpace.kObject)
                ]
            for attr in (
                "overrideEnabled",
                "overrideRGBColors",
                "overrideColor",
                "overrideDisplayType",
                "lineWidth",
                "isHistoricallyInteresting",
                "visibility",
            ):
                if cmds.attributeQuery(attr, node=shape, exists=True):
                    data[attr] = cmds.getAttr(shape + "." + attr)
            data["overrideColorRGB"] = cmds.getAttr(shape + ".overrideColorRGB")[0]
            for attr in ("alwaysDrawOnTop", "visibility"):
                if cmds.attributeQuery(attr, node=shape, exists=True):
                    src = cmds.listConnections(
                        shape + "." + attr, source=True, destination=False, plugs=True
                    )
                    data[attr + "_input"] = src or None
            shapes.append(data)
        return shapes

    return describe
