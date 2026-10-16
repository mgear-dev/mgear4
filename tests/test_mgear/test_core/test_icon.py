"""mgear.core.icon tests

Every icon must keep the shapes it created before the guide draw
performance change: shape names (generic icons only), order, CVs, knots,
degree, form, colours, line width, and no temporary transform left behind.
The expected data is stored gzipped in ``data/`` (``check_golden``).
"""

import pytest

# icon.create types
CREATE_TYPES = (
    "cube",
    "pyramid",
    "square",
    "flower",
    "circle",
    "cylinder",
    "compas",
    "diamond",
    "cubewithpeak",
    "sphere",
    "arrow",
    "crossarrow",
    "cross",
    "null",
    "gear",
    "mgear",
)
# guide icons, whose shape names are free to change
GUIDE_ICONS = ("guideRootIcon", "guideRootIcon2D", "guideLocatorIcon", "guideBladeIcon")


def rotated_matrix():
    """A world matrix with translation and rotation."""
    from maya.api import OpenMaya

    from mgear.pymaya import datatypes

    tm = OpenMaya.MTransformationMatrix()
    tm.setTranslation(OpenMaya.MVector(1, 2, 3), OpenMaya.MSpace.kWorld)
    tm.setRotation(OpenMaya.MEulerRotation(0.3, -0.5, 1.1))
    return datatypes.Matrix(tm.asMatrix())


def describe_icon(node, describe_shapes, names=True):
    """Describe an icon transform and the transforms left in the scene."""
    from maya import cmds

    name = str(node)
    return {
        "name": name.split("|")[-1],
        "matrix": cmds.xform(name, query=True, matrix=True, worldSpace=True),
        "user_attrs": sorted(cmds.listAttr(name, userDefined=True) or []),
        "keyable": sorted(cmds.listAttr(name, keyable=True) or []),
        "shapes": describe_shapes(name, names=names),
        "transforms": sorted(cmds.ls(type="transform")),
    }


@pytest.fixture
def icon_scene(setup_path):
    """New scene with a ``grp`` parent; returns (icon module, parent node)."""
    from maya import cmds

    import mgear.pymaya as pm
    from mgear.core import icon

    cmds.file(new=True, force=True)
    return icon, pm.PyNode(cmds.group(name="grp", empty=True))


@pytest.mark.parametrize("degree", (1, 3))
@pytest.mark.parametrize("color", (17, (0.2, 0.4, 0.6)))
def test_create_icons_unchanged(
    icon_scene, describe_shapes, check_golden, degree, color
):
    from mgear.pymaya import datatypes

    icon, parent = icon_scene
    data = {}
    for icon_type in CREATE_TYPES:
        node = icon.create(
            parent,
            "t_" + icon_type,
            rotated_matrix(),
            list(color) if isinstance(color, tuple) else color,
            icon_type,
            w=1.5,
            h=0.5,
            d=2,
            po=datatypes.Vector(0.1, 0, 0.2),
            ro=datatypes.Vector(0, 0.3, 0),
            degree=degree,
        )
        data[icon_type] = describe_icon(node, describe_shapes)
    color_name = "index" if isinstance(color, int) else "rgb"
    check_golden("icons_create_{}_d{}".format(color_name, degree), data)


def test_axis_icon_unchanged(icon_scene, describe_shapes, check_golden):
    icon, parent = icon_scene
    node = icon.axis(parent, "t_axis", width=0.7, m=rotated_matrix())
    check_golden("icons_axis", describe_icon(node, describe_shapes))


def test_guide_icons_unchanged(icon_scene, describe_shapes, check_golden):
    icon, parent = icon_scene
    data = {}
    colors = {"guideRootIcon": 13, "guideRootIcon2D": 13, "guideLocatorIcon": 17}
    for name in GUIDE_ICONS:
        func = getattr(icon, name)
        if name == "guideBladeIcon":
            node = func(
                parent, "t_" + name, lenX=0.5, color=[0, 0, 1], m=rotated_matrix()
            )
        else:
            node = func(parent, "t_" + name, color=colors[name], m=rotated_matrix())
        data[name] = describe_icon(node, describe_shapes, names=False)
    check_golden("icons_guide", data)


def test_add_icon_shapes(icon_scene, describe_shapes):
    from maya import cmds

    icon, parent = icon_scene
    transforms = set(cmds.ls(type="transform"))

    shapes = icon.add_icon_shapes("grp", "axis", "ref", width=2, scale=(2, 1, 0.5))

    assert set(cmds.ls(type="transform")) == transforms
    assert [s.split("|")[-1] for s in shapes] == ["refShape", "ref1Shape", "ref2Shape"]
    data = describe_shapes("grp")
    assert [d["overrideColor"] for d in data] == [4, 14, 6]
    # x line of width 2 scaled by 2, z line scaled by 0.5
    assert data[0]["cvs"][1] == [2.0, 0.0, 0.0]
    assert data[2]["cvs"][1] == [0.0, 0.0, 0.5]

    with pytest.raises(ValueError):
        icon.add_icon_shapes("grp", "gear")
