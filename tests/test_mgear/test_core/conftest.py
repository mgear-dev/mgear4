"""Fixtures shared by the core tests that need a built Shifter rig."""

import pytest


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

    for name in ("mgear_solvers", "mGearWeightDriver"):
        if not load_repo_plugin(name):
            pytest.skip("{} plug-in not available".format(name))

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
    cmds.file(new=True, force=True)
    cmds.file(path, i=True, namespace="char")
    return cmds


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
