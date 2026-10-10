"""Fixtures shared by the core tests that need a built Shifter rig."""

import pytest


def _require_rig_plugins(load_repo_plugin):
    """Skip the test when the plug-ins a Shifter build needs can't load."""
    for name in ("mgear_solvers", "mGearWeightDriver"):
        if not load_repo_plugin(name):
            pytest.skip("{} plug-in not available".format(name))


def _import_with_namespaces(path, namespaces):
    """Import a Maya file once per namespace in a new scene."""
    from maya import cmds

    cmds.file(new=True, force=True)
    for namespace in namespaces:
        cmds.file(path, i=True, namespace=namespace)
    return cmds


@pytest.fixture
def import_rig_file():
    """Function importing a Maya file once per namespace in a new scene."""
    return _import_with_namespaces


@pytest.fixture
def anim_utils(setup_path):
    """The mgear.core.anim_utils module."""
    from mgear.core import anim_utils

    return anim_utils


@pytest.fixture
def shifter_rig(load_repo_plugin, setup_path):
    """A small Shifter rig in a new scene.

    The guide has a ``control_C0`` root with an ``arm_C0`` (arm_2jnt_01)
    and a ``control_C1`` (control_01) below it. Both have two IK
    references, so the UI host ``global_C0_ctl`` gets ``arm_blend``,
    ``arm_ikref`` and ``control_ikref``.

    Returns:
        module: maya.cmds.
    """
    from maya import cmds

    _require_rig_plugins(load_repo_plugin)

    import mgear.pymaya as pm
    from mgear import shifter
    from mgear.shifter import guide

    cmds.file(new=True, force=True)
    guide.Rig().drawNewComponent(None, "control_01", showUI=False)
    root = pm.PyNode("control_C0_root")
    guide.Rig().drawNewComponent(root, "arm_2jnt_01", showUI=False)
    guide.Rig().drawNewComponent(root, "control_01", showUI=False)
    cmds.setAttr(
        "control_C1_root.ikrefarray",
        "control_C0_root,arm_C0_root",
        type="string",
    )
    cmds.setAttr(
        "arm_C0_root.ikrefarray",
        "control_C0_root,control_C1_root",
        type="string",
    )
    cmds.select("guide")
    shifter.Rig().buildFromSelection()
    cmds.select(clear=True)
    return cmds


@pytest.fixture
def namespaced_rig(shifter_rig, tmp_path):
    """The shifter_rig fixture imported under the "char" namespace."""
    cmds = shifter_rig
    path = str(tmp_path / "rig.ma").replace("\\", "/")
    cmds.delete("guide")
    cmds.file(path, exportAll=True, type="mayaAscii", force=True)
    return _import_with_namespaces(path, ("char",))


class MenuRecorder(object):
    """Records ``cmds.menuItem`` calls, as Maya UI is not available in batch.

    Each entry is a dict with ``path`` (submenu labels and the item label
    joined with "/"), ``label``, ``divider``, ``kwargs`` and ``command``.
    """

    def __init__(self):
        self.entries = []
        self._submenus = {}
        self._count = 0

    def menu_item(self, *args, **kwargs):
        """Stand-in for cmds.menuItem.

        Returns:
            str: A fake menu path for submenus, else None.
        """
        parent = kwargs.get("parent")
        prefix = self._submenus.get(parent)
        if kwargs.get("divider"):
            label = "---"
        else:
            label = kwargs.get("label")
        path = "{}/{}".format(prefix, label) if prefix else label
        self.entries.append(
            {
                "path": path,
                "label": label,
                "divider": bool(kwargs.get("divider")),
                "parent": parent,
                "kwargs": kwargs,
                "command": kwargs.get("command"),
            }
        )
        if kwargs.get("subMenu"):
            self._count += 1
            name = "fake_submenu_{}".format(self._count)
            self._submenus[name] = path
            return name
        return None

    def paths(self, dividers=True):
        """Recorded item paths.

        Args:
            dividers (bool, optional): Include "---" divider entries.

        Returns:
            list: The paths in creation order.
        """
        return [e["path"] for e in self.entries if dividers or not e["divider"]]

    def entry(self, path):
        """Get the first entry with the given path.

        Args:
            path (str): Item path, e.g. "Reset Option/Reset all".

        Returns:
            dict: The entry.
        """
        for e in self.entries:
            if e["path"] == path:
                return e
        raise KeyError(path)

    def clear(self):
        """Forget all recorded entries."""
        self.entries = []
        self._submenus = {}
        self._count = 0


@pytest.fixture
def menu_recorder(monkeypatch, run_with_maya_standalone):
    """Patch maya.cmds menu commands with a MenuRecorder.

    Returns:
        MenuRecorder: The recorder.
    """
    from maya import cmds

    recorder = MenuRecorder()
    monkeypatch.setattr(cmds, "menuItem", recorder.menu_item)
    monkeypatch.setattr(cmds, "radioMenuItemCollection", lambda *args, **kwargs: None)
    return recorder


@pytest.fixture(scope="session")
def biped_rig_file(load_repo_plugin, setup_path, tmp_path_factory):
    """A Shifter biped rig built once per session, saved without its guide.

    Returns:
        str: Path of the saved Maya ASCII file.
    """
    from maya import cmds

    _require_rig_plugins(load_repo_plugin)

    from mgear import shifter
    from mgear.shifter import io

    cmds.file(new=True, force=True)
    io.import_sample_template("biped.sgt")
    cmds.select("guide")
    shifter.Rig().buildFromSelection()
    cmds.delete("guide")
    path = str(tmp_path_factory.mktemp("biped") / "biped.ma").replace("\\", "/")
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii", force=True)
    return path


@pytest.fixture
def biped_rig(biped_rig_file):
    """The session biped rig, opened in a new scene.

    Returns:
        module: maya.cmds.
    """
    from maya import cmds

    cmds.file(biped_rig_file, open=True, force=True)
    cmds.select(clear=True)
    return cmds


@pytest.fixture
def two_biped_rigs(biped_rig_file):
    """The session biped rig imported twice, as "charA" and "charB".

    Returns:
        module: maya.cmds.
    """
    return _import_with_namespaces(biped_rig_file, ("charA", "charB"))


@pytest.fixture
def eight_biped_rigs(biped_rig_file):
    """The session biped rig imported eight times, "c0" to "c7".

    Returns:
        module: maya.cmds.
    """
    namespaces = ["c{}".format(i) for i in range(8)]
    return _import_with_namespaces(biped_rig_file, namespaces)
