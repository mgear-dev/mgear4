# Shifter guides IO utility functions
import copy
import os
import json
import sys
import re
import logging

from typing import List, Tuple, Sequence, Optional

from maya import cmds

import mgear.pymaya as pm
from mgear import shifter
from mgear.shifter import utils as shifter_utils
from mgear.core import curve
from mgear.core import string
from mgear.core import utils

if sys.version_info[0] == 2:
    string_types = (basestring, )
else:
    string_types = (str,)


logger = logging.getLogger("mgear.shifter.io")
logger.setLevel(logging.INFO)


# -- Pair lists kept separate for readability and future edits
_MH_SPINE: List[Tuple[str, str]] = [("root_C0_root", "root"),
                                    ("body_C0_root", "pelvis"),
                                    ("spine_C0_spineBase", "spine_01"),
                                    ("spine_C0_tan0", "spine_02"),
                                    ("spine_C0_spineTop", "spine_04"),
                                    ("spine_C0_tan1", "spine_03"),
                                    ("spine_C0_chest", "spine_05")
                                    ]

_MH_LEG: List[Tuple[str, str]] = [("leg_L0_root", "thigh_l"),
                                  ("leg_L0_knee", "calf_l"),
                                  ("leg_L0_ankle", "foot_l"),
                                  ("foot_L0_0_loc", "ball_l")
                                  ]

_MH_ARM: List[Tuple[str, str]] = [("clavicle_L0_root", "clavicle_l"),
                                  ("clavicle_L0_tip", "upperarm_l"),
                                  ("arm_L0_elbow", "lowerarm_l"),
                                  ("arm_L0_wrist", "hand_l")
                                  ]

_MH_HAND: List[Tuple[str, str]] = [("index_metacarpal_L0_root", "index_metacarpal_l"),
                                   ("middle_metacarpal_L0_root", "middle_metacarpal_l"),
                                   ("ring_metacarpal_L0_root", "ring_metacarpal_l"),
                                   ("pinky_metacarpal_L0_root", "pinky_metacarpal_l"),
                                   ("thumb_L0_root", "thumb_01_l"),
                                   ("thumb_L0_0_loc", "thumb_02_l"),
                                   ("thumb_L0_1_loc", "thumb_03_l"),
                                   ("index_L0_root", "index_01_l"),
                                   ("index_L0_0_loc", "index_02_l"),
                                   ("index_L0_1_loc", "index_03_l"),
                                   ("middle_L0_root", "middle_01_l"),
                                   ("middle_L0_0_loc", "middle_02_l"),
                                   ("middle_L0_1_loc", "middle_03_l"),
                                   ("ring_L0_root", "ring_01_l"),
                                   ("ring_L0_0_loc", "ring_02_l"),
                                   ("ring_L0_1_loc", "ring_03_l"),
                                   ("pinky_L0_root", "pinky_01_l"),
                                   ("pinky_L0_0_loc", "pinky_02_l"),
                                   ("pinky_L0_1_loc", "pinky_03_l")
                                   ]

_MH_NECK: List[Tuple[str, str]] = [("neck_C0_root", "neck_01"),
                                   ("neck_C0_neck", "head"),
                                   ("neck_C0_tan0", "neck_02")
                                   ]

_MH_IKS: List[Tuple[str, str]] = [("ik_foot_L0_root", "foot_l"),
                                  ("ik_hand_gun_C0_root", "hand_r"),
                                  ("ik_hand_L0_root", "hand_l")
                                  ]


# -- Compiled once, used to discover skeleton root and mirroring
_RE_ROOT_NAME = re.compile(r"(^|_)root($|_|$)", re.IGNORECASE)
_RE_SUFFIX_FROM_ROOT = re.compile(r"root(_[A-Za-z0-9]+)?$", re.IGNORECASE)


def get_guide_template_dict(guide_node, meta=None):
    """Get the guide template dictionary from a guide node.

    Args:
        guide_node (PyNode): The guide node to start the parsing from.
        meta (dict, optional): Arbitraty metadata dictionary. This can
            be use to store any custom information in a dictionary format.

    Returns:
        dict: the parsed guide dictionary
    """
    try:
        rig = shifter.Rig()
        rig.guide.setFromHierarchy(guide_node)
        return rig.guide.get_guide_template_dict(meta)
    except TypeError:
        pm.displayWarning("The selected object is not a valid guide element")


def get_template_from_selection(meta=None):
    """Get the guide template dictionary from a selected guide element.

    Args:
        meta (dict, optional): Arbitraty metadata dictionary. This can
            be use to store any custom information in a dictionary format.

    Returns:
        dict: the parsed guide dictionary

    """
    if pm.selected():
        return get_guide_template_dict(pm.selected()[0], meta)
    else:
        pm.displayWarning("Guide root or guide component must be selected")


def _get_file(write=False):
    """Convinience function to retrive the guide file in at export or import.

    Args:
        write (bool, optional): If true, will set the dialog to write.
            If false will se the dialog to read.

    Returns:
        str: the file path
    """
    if write:
        mode = 0
    else:
        mode = 1
    filePath = pm.fileDialog2(
        fileMode=mode,
        fileFilter='Shifter Guide Template .sgt (*%s)' % ".sgt")

    if not filePath:
        return
    if not isinstance(filePath, string_types):
        filePath = filePath[0]

    return filePath


def export_guide_template(filePath=None, meta=None, conf=None, *args):
    """Export the guide template to a file.

    Args:
        filePath (str, optional): Path to save the file.
        meta (dict, optional): Arbitrary metadata dictionary. This can
            be used to store any custom information in a dictionary format.
    """
    if not conf:
        selection = pm.selected()
        if selection:
            rig = shifter.Rig()
            rig.guide.setFromHierarchy(selection[0])
            rig.guide.refresh_user_metadata()

            # Progress bar for data collection. Its redraw is throttled, a
            # redraw per component is slow on big guides.
            num_comps = len(rig.guide.componentsIndex)
            with utils.main_progress_bar(
                "Exporting guide template...", num_comps + 1, redraw_interval=0.1
            ) as step:
                conf = rig.guide.get_guide_template_dict(
                    meta,
                    progress_callback=lambda name: step("Exporting: {}".format(name)),
                )
        else:
            pm.displayWarning(
                "Guide root or guide component must be selected"
            )
            return
    if conf:
        data_string = json.dumps(conf, indent=4, sort_keys=True)
        if not filePath:
            filePath = _get_file(True)
            if not filePath:
                return

        with open(filePath, 'w') as f:
            f.write(data_string)


def _import_guide_template(filePath=None):
    """Summary

    Args:
        filePath (str, optional): Path to the template file to import

    Returns:
        dict: the parsed guide dictionary
    """
    if not filePath:
        filePath = _get_file()
    if not filePath:
        pm.displayWarning("File path to template is None")
        return
    conf = None
    with open(filePath, 'r') as f:
        if f:
            conf = json.load(f)

    return conf


def import_partial_guide(
        filePath=None, partial=None, initParent=None, conf=None):
    """Import a partial part of a template

    Limitations:
        - The UI host and space switch references are not updated. This may
        affect the configuration if the index change. I.e. Import 2 times same
        componet with internal UI host in the childs. the second import will
        point to the original UI host.

    Args:
        filePath (str, optional): Path to the template file to import
        partial (str or list of str, optional): If Partial starting
            component is defined, will try to add the guide to a selected
            guide part of an existing guide.
        initParent (dagNode, optional): Initial parent. If None, will
            create a new initial heirarchy

    Returns:
        list: Long names of the component roots drawn directly under
            ``initParent``, or under the new guide when it is None.
    """
    if not conf:
        conf = _import_guide_template(filePath)
    if conf:
        rig = shifter.Rig()
        rig.guide.set_from_dict(conf)
        drawn = rig.guide.draw_guide(partial, initParent)
        if drawn is None:
            # Not a valid initial parent, draw_guide warned
            return []
        partial_names, partial_idx = drawn

        # controls shapes buffer
        if not partial and conf["ctl_buffers_dict"]:
            curve.create_curve_from_data(conf["ctl_buffers_dict"],
                                         replaceShape=True,
                                         rebuildHierarchy=True,
                                         model=rig.guide.model)

        elif partial and conf["ctl_buffers_dict"]:
            # we need to match the ctl buffer names with the new
            # component index
            for crv in conf["ctl_buffers_dict"]["curves_names"]:
                if crv.startswith(tuple(partial_names)):
                    comp_name = "_".join(crv.split("_")[:2])
                    i = partial_names.index(comp_name)
                    pi = partial_idx[i]
                    scrv = crv.split("_")
                    crv = "_".join(scrv)
                    scrv[1] = scrv[1][0] + str(pi)
                    ncrv = "_".join(scrv)
                    curve.create_curve_from_data_by_name(
                        crv,
                        conf["ctl_buffers_dict"],
                        replaceShape=True,
                        rebuildHierarchy=True,
                        rplStr=[crv, ncrv],
                        model=rig.guide.model)

        # Drawing leaves the last component guide selected
        pm.select(clear=True)
        return rig.guide.drawn_roots
    return []


def import_guide_template(filePath=None, conf=None, **kwargs):
    """Import a guide template

    Args:
        filePath (str, optional): Path to the template file to import

    Returns:
        list: Long names of the drawn top component roots.
    """
    return import_partial_guide(filePath, conf=conf, **kwargs)


def build_from_file(filePath=None, conf=False, *args):
    """Build a rig from a template file.
    The rig will be build from a previously exported guide template, without
    creating the guide in the scene.

    Args:
        filePath (None, optional): Guide template file path

    """
    if not conf:
        conf = _import_guide_template(filePath)
    if conf:
        rig = shifter.Rig()
        rig.buildFromDict(conf)

        # controls shapes buffer
        if conf["ctl_buffers_dict"]:
            curve.update_curve_from_data(conf["ctl_buffers_dict"],
                                         rplStr=["_controlBuffer", ""])
        return rig


# Import choices returned by the guide import options dialog
IMPORT_NEW = "import"
IMPORT_ADD = "add"
IMPORT_BUILD = "build"
IMPORT_CANCEL = "cancel"


def get_selected_guide_element():
    """Get the selected guide element to import a template into.

    A guide element is a transform under a guide top node, like a
    component root or a locator. The guide top node itself is not one.

    Returns:
        PyNode: The first selected guide element, or None.
    """
    selection = cmds.ls(selection=True, type="transform", long=True)
    if not selection:
        return None
    node = selection[0]
    top = "|" + node.split("|")[1]
    if top == node or not cmds.attributeQuery("ismodel", node=top, exists=True):
        return None
    return pm.PyNode(node)


def get_template_components(conf):
    """Get the component information of a guide template.

    Args:
        conf (dict): Guide template dictionary.

    Returns:
        list: Dicts with the keys name, comp_type, parent and children,
            in template order.
    """
    components = []
    comp_dict = conf.get("components_dict", {})
    for name in conf.get("components_list", []):
        comp_data = comp_dict.get(name, {})
        params = comp_data.get("param_values", {})
        components.append(
            {
                "name": name,
                "comp_type": params.get("comp_type", "unknown"),
                "parent": comp_data.get("parent_fullName"),
                "children": comp_data.get("child_components", []),
            }
        )
    return components


def snap_guide_roots(roots, target):
    """Move guide roots so the first one sits on the target.

    Every root moves by the same world-space offset, so several roots
    keep their spacing.

    Args:
        roots (list): Names of the guide roots to move.
        target (str or PyNode): Node to snap the first root to.
    """
    if not roots:
        return
    target_pos = cmds.xform(str(target), query=True, worldSpace=True, translation=True)
    first_pos = cmds.xform(roots[0], query=True, worldSpace=True, translation=True)
    offset = [t - f for t, f in zip(target_pos, first_pos)]
    for root in roots:
        pos = cmds.xform(root, query=True, worldSpace=True, translation=True)
        cmds.xform(
            root,
            worldSpace=True,
            translation=[p + o for p, o in zip(pos, offset)],
        )


def import_guide_into(init_parent, filePath=None, conf=None, partial=None, snap=False):
    """Import a guide template under an element of an existing guide.

    Args:
        init_parent (str or PyNode): Guide element to draw the template
            under, like a component root or a locator.
        filePath (str, optional): Path to the template file to import.
        conf (dict, optional): Guide template dictionary. Used instead of
            reading ``filePath``.
        partial (list, optional): Names of the components to import, with
            their children. If None, imports the whole template.
        snap (bool, optional): If True, moves the new roots so the first
            one sits on ``init_parent``.

    Returns:
        list: Long names of the new component roots under ``init_parent``.
    """
    roots = import_partial_guide(
        filePath, partial=partial, initParent=pm.PyNode(init_parent), conf=conf
    )
    if snap:
        snap_guide_roots(roots, init_parent)
    return roots


def _ask_import_choice(file_name, components, target_name, allow_build):
    """Show the guide import options dialog.

    Args:
        file_name (str): Template file name shown in the dialog.
        components (list): Template components from
            ``get_template_components``, for the partial page.
        target_name (str): Name of the selected guide element, or None.
        allow_build (bool): If True, offers to build the rig.

    Returns:
        tuple: The action (one of the ``IMPORT_*`` constants), the root
            components picked for a partial import or None, and the snap
            flag.
    """
    if cmds.about(batch=True):
        return IMPORT_CANCEL, None, False
    from mgear.shifter import guide_import_dialog

    return guide_import_dialog.ask_import_choice(
        file_name, components, target_name, allow_build
    )


def import_guide_interactive(filePath=None, allow_build=False):
    """Import a guide template, asking where when a guide is selected.

    With a guide element selected, the options dialog offers to import
    a new guide, or to add the whole template or some components under
    the element, with or without snapping. With nothing selected and
    ``allow_build`` off, imports a new guide without asking.

    Args:
        filePath (str, optional): Path to the template file. If None,
            asks for it with a file browser.
        allow_build (bool, optional): If True, always shows the dialog
            and offers to build the rig without drawing the guide.
    """
    if not filePath:
        filePath = _get_file()
        if not filePath:
            return

    target = get_selected_guide_element()
    if not target and not allow_build:
        import_guide_template(filePath=filePath)
        return

    conf = None
    components = []
    if target:
        conf = _import_guide_template(filePath)
        if not conf:
            return
        components = get_template_components(conf)

    action, partial, snap = _ask_import_choice(
        os.path.basename(filePath),
        components,
        target.name() if target else None,
        allow_build,
    )
    if action == IMPORT_NEW:
        import_guide_template(filePath=filePath, conf=conf)
    elif action == IMPORT_ADD:
        import_guide_into(target, conf=conf, partial=partial, snap=snap)
    elif action == IMPORT_BUILD:
        build_from_file(filePath=filePath, conf=conf)


def guide_file_drop(filePath):
    """Ask what to do with a guide template file dropped on Maya.

    Used by the mGear file drop. Offers Import and Build, and the add
    options when a guide element is selected.

    Args:
        filePath (str): Guide template (.sgt) file path.
    """
    import_guide_interactive(filePath, allow_build=True)


def _component_full_name(param_values, index=None):
    """Get the full name of a component from its parameter values.

    Args:
        param_values (dict): Component parameter values.
        index (int, optional): Index to use instead of ``comp_index``.

    Returns:
        str: The full name, like ``arm_L0``.
    """
    if index is None:
        index = param_values["comp_index"]
    return "{}_{}{}".format(param_values["comp_name"], param_values["comp_side"], index)


def _longest_component_prefix(components, name):
    """Get the component whose ``<full name>_`` starts a node name.

    Args:
        components (iterable): Component full names.
        name (str): Node name, like ``arm_L0_wrist``.

    Returns:
        str: The longest matching component full name, or None.
    """
    matches = [
        comp
        for comp in components
        if name.startswith(comp + "_") and len(name) > len(comp) + 1
    ]
    return max(matches, key=len) if matches else None


def resolve_guide_element(guide_dict, name):
    """Get the component and local name of a guide element name.

    Args:
        guide_dict (dict): Guide template dictionary.
        name (str): Guide element name, like ``arm_L0_wrist``.

    Returns:
        tuple: The component full name and the local name, like
            ``("arm_L0", "wrist")``.

    Raises:
        ValueError: No component of the guide matches the name.
    """
    comp = _longest_component_prefix(guide_dict["components_dict"], name)
    if not comp:
        raise ValueError("Guide element {} is not in the guide".format(name))
    return comp, name[len(comp) + 1 :]


def _get_element_position(comp_dict, local_name):
    """Get the stored world position of a component guide element.

    Args:
        comp_dict (dict): Component guide dictionary.
        local_name (str): Local name of the element, like ``wrist``.

    Returns:
        list: The world position.

    Raises:
        ValueError: The component has no element with that name.
    """
    if local_name in comp_dict["tra"]:
        return list(comp_dict["tra"][local_name][3][:3])
    if local_name in comp_dict["pos"]:
        return list(comp_dict["pos"][local_name])
    raise ValueError("Guide element {} not found".format(local_name))


def _offset_component(comp_dict, offset):
    """Move all the stored transforms of a component guide.

    Args:
        comp_dict (dict): Component guide dictionary, changed in place.
        offset (list): World offset to add.
    """

    def moved_vector(vector):
        return [v + o for v, o in zip(vector, offset)] + list(vector[3:])

    def moved_matrix(matrix):
        rows = [list(row) for row in matrix]
        rows[3] = moved_vector(rows[3])
        return rows

    for key in ("tra", "blade"):
        comp_dict[key] = {
            name: moved_matrix(matrix) for name, matrix in comp_dict[key].items()
        }
    comp_dict["atra"] = [moved_matrix(matrix) for matrix in comp_dict["atra"]]
    comp_dict["pos"] = {
        name: moved_vector(vector) for name, vector in comp_dict["pos"].items()
    }
    comp_dict["apos"] = [moved_vector(vector) for vector in comp_dict["apos"]]


def _select_template_components(template_dict, partial):
    """Get the template components to merge, in template order.

    Args:
        template_dict (dict): Guide template dictionary.
        partial (list): Root component names, or None for all.

    Returns:
        list: Component full names.
    """
    comp_list = template_dict["components_list"]
    if not partial:
        return list(comp_list)
    comp_dict = template_dict["components_dict"]
    selected = set()
    pending = list(partial)
    while pending:
        name = pending.pop()
        if name in selected or name not in comp_dict:
            continue
        selected.add(name)
        pending.extend(comp_dict[name]["child_components"])
    return [name for name in comp_list if name in selected]


def _rename_prefix(name, rename):
    """Rename a node name that starts with a renamed component name.

    Args:
        name (str): Node name, like ``arm_C0_fk0_ctl_controlBuffer``.
        rename (dict): New full names by old component full name.

    Returns:
        str: The renamed name, or None if no component matches.
    """
    comp = _longest_component_prefix(rename, name)
    if not comp:
        return None
    return rename[comp] + name[len(comp) :]


def _merge_ctl_buffers(guide_buffers, template_buffers, rename):
    """Merge the control buffers of renamed components.

    Args:
        guide_buffers (dict): Control buffers of the guide, or None.
            Changed in place when it is not None.
        template_buffers (dict): Control buffers of the template, or None.
        rename (dict): New full names by template full name.

    Returns:
        dict: The merged control buffers, or None if there are none.
    """
    if not template_buffers:
        return guide_buffers
    merged = guide_buffers or {"curves_names": []}
    for crv in template_buffers["curves_names"]:
        new_crv = _rename_prefix(crv, rename)
        if not new_crv:
            continue
        crv_dict = copy.deepcopy(template_buffers[crv])
        shape_names = {
            shape: _rename_prefix(shape, rename) or shape
            for shape in crv_dict["shapes"]
        }
        crv_dict["shapes"] = {
            shape_names[shape]: data for shape, data in crv_dict["shapes"].items()
        }
        crv_dict["shapes_names"] = [
            shape_names.get(shape, shape) for shape in crv_dict["shapes_names"]
        ]
        if new_crv not in merged:
            merged["curves_names"].append(new_crv)
        merged[new_crv] = crv_dict
    return merged


def merge_guide_template(guide_dict, template_dict, target, partial=None, snap=False):
    """Merge a guide template into a guide dictionary under an element.

    The dictionary version of ``import_guide_into``. Used to add guide
    parts at build time, when the guide may only exist as a dictionary.

    Limitations:
        - The UI host and space switch references of the merged
        components are not updated, like ``import_partial_guide``.

    Args:
        guide_dict (dict): Guide template dictionary to merge into.
        template_dict (dict): Guide template dictionary to merge.
        target (str): Guide element to add the template under, like
            ``arm_L0_wrist``.
        partial (list, optional): Names of the template components to
            merge, with their children. If None, merges all of them.
        snap (bool, optional): If True, moves the merged components so
            the first root sits on the target.

    Returns:
        dict: A new guide dictionary. The inputs are not changed.

    Raises:
        ValueError: The target is not in the guide.
    """
    result = copy.deepcopy(guide_dict)
    merge_guide_template_into(result, template_dict, target, partial, snap)
    return result


def merge_guide_template_into(
    guide_dict, template_dict, target, partial=None, snap=False
):
    """Merge a guide template into a guide dictionary, in place.

    Same as ``merge_guide_template``, without copying the guide first.
    Use it to fold several templates into one copy of a guide.

    Args:
        guide_dict (dict): Guide template dictionary, changed in place.
        template_dict (dict): Guide template dictionary to merge. Not
            changed.
        target (str): Guide element to add the template under.
        partial (list, optional): Names of the template components to
            merge, with their children. If None, merges all of them.
        snap (bool, optional): If True, moves the merged components so
            the first root sits on the target.

    Raises:
        ValueError: The target is not in the guide.
    """
    target_comp, target_local = resolve_guide_element(guide_dict, target)
    comp_dict = guide_dict["components_dict"]
    names = _select_template_components(template_dict, partial)

    # Lowest free index from the template index, like setIndex
    rename = {}
    new_index = {}
    taken = set(comp_dict)
    for name in names:
        values = template_dict["components_dict"][name]["param_values"]
        index = values["comp_index"]
        while _component_full_name(values, index) in taken:
            index += 1
        new_name = _component_full_name(values, index)
        taken.add(new_name)
        rename[name] = new_name
        new_index[name] = index

    roots = []
    for name in names:
        c_dict = copy.deepcopy(template_dict["components_dict"][name])
        new_name = rename[name]
        c_dict["param_values"]["comp_index"] = new_index[name]
        comp_dict[new_name] = c_dict
        guide_dict["components_list"].append(new_name)
        c_dict["child_components"] = [
            rename[child] for child in c_dict["child_components"] if child in rename
        ]
        parent = c_dict.get("parent_fullName")
        if parent in rename:
            c_dict["parent_fullName"] = rename[parent]
        else:
            c_dict["parent_fullName"] = target_comp
            c_dict["parent_localName"] = target_local
            comp_dict[target_comp]["child_components"].append(new_name)
            roots.append(new_name)

    if snap and roots:
        target_pos = _get_element_position(comp_dict[target_comp], target_local)
        root_pos = _get_element_position(comp_dict[roots[0]], "root")
        offset = [t - r for t, r in zip(target_pos, root_pos)]
        for name in names:
            _offset_component(comp_dict[rename[name]], offset)

    guide_dict["ctl_buffers_dict"] = _merge_ctl_buffers(
        guide_dict.get("ctl_buffers_dict"),
        template_dict.get("ctl_buffers_dict"),
        rename,
    )


# Sample import command
def import_sample_template(name, *args):
    """Import the sample guide templates from _template folder

    Args:
        name (str): Name of the guide template file. with extension.
        *args: Maya Dummy
    """
    shifter_path = os.path.dirname(shifter.__file__)
    path = os.path.join(shifter_path, "component", "_templates", name)
    import_guide_template(path)


def _find_guide_root_name() -> Optional[str]:
    """
    Return the mGear guide model name from utils.get_guide() or None.
    """
    _guide = shifter_utils.get_guide()
    if not _guide:
        logger.warning("No guide found. Select a guide root or component.")
        return None
    return _guide[0].node().name()


def _snap_translation(src: pm.PyNode, dst: pm.PyNode) -> None:
    """
    Snap source world translation to destination world translation.
    """
    src.setTranslation(dst.getTranslation(space="world"), space="world")


def _get_suffix(root_nodes: List) -> str:
    """
    Get the suffix (e.g. '_drv') from the first root joint in the list.

    :param list[str] root_nodes: List of joint names containing 'root'.
    :return: The detected suffix or an empty string if none is found.
    :rtype: str
    """
    root_short = root_nodes[0].split("|")[-1]
    m = _RE_SUFFIX_FROM_ROOT.search(root_short)

    return m.group(1) if (m and m.group(1)) else ""


def _set_roll_divisions_zero() -> None:
    """
    Set roll division to 0 on upper and lower leg and arm components.

    There is already rig logic from MetaHuman driving the twists, so there is
    no need for mGear to build its own twist logic when driving a built MetaHuman.

    :return: None
    """
    for side in "LR":
        for comp_name in ["arm", "leg"]:
            comp_roots = [f"{comp_name}_{side}0_root.div0",
                          f"{comp_name}_{side}0_root.div1"]

            for comp in comp_roots:
                if not pm.objExists(comp_name):
                    continue
                # -- Set upper and lower values to zero
                pm.setAttr(comp, 0)


# Epic Metahuman snap to skeleton utility function
def metahuman_snap():
    """
    Snap the MetaHuman guide to align with its corresponding skeleton.

    Finds the skeleton root to extract the suffix - if there is one (e.g., `_drv`),
    then snaps guide locators to their matching driver joints in world space.
    Left-side elements are mirrored to the right automatically. Finally, updates
    the joint naming rule and sets roll divisions for correct deformation.

    :return: None
    """

    guide_name = _find_guide_root_name()

    # -- Exit early, if no guide in the scene.
    if not guide_name:
        logger.error("No guide found in the scene.")
        return

    all_joints = pm.ls(long=True, type="joint")
    root_nodes = [n for n in all_joints if _RE_ROOT_NAME.search(n.split("|")[-1])]

    # -- Exit early if no root node is found
    if not root_nodes:
        logger.error("No root or root_drv found in the scene.")
        return

    # -- extract suffix if there is one (backwards compatibility)
    suffix = _get_suffix(root_nodes=root_nodes)

    # -- Create one list with all paired items to match
    # -- Build mapping once
    left_pairs: Sequence[Tuple[str, str]] = (_MH_SPINE + _MH_LEG + _MH_ARM + _MH_HAND + _MH_NECK + _MH_IKS)
    processed: List[Tuple[str, str]] = []

    for src_left, tgt_left in left_pairs:
        # -- Left pair - Adding the corrected suffix to the target skeleton
        processed.append((src_left, f"{tgt_left}{suffix}"))

        # -- Only mirror if the SOURCE actually has an L/R token
        src_right = string.convertRLName(src_left)
        if src_right != src_left:
            tgt_right = string.convertRLName(tgt_left) + suffix
            processed.append((src_right, tgt_right))

    # -- Snapping
    for src_name, dst_name in processed:
        try:
            src = pm.PyNode(src_name)
            dst = pm.PyNode(dst_name)
        except pm.MayaNodeError:
            logger.warning(f"Missing node. Skipping pair: {src_name} -> {dst_name}")
            continue

        try:
            _snap_translation(src, dst)
        except Exception as exc:
            logger.error(f"Failed to snap {src_name} to {dst_name}: {exc}")

    # -- Ensure to set the correct naming rule for mGear build.
    name_pattern = f"{{description}}{{side}}{suffix}"
    joint_name_rule = f"{guide_name}.joint_name_rule"

    if not pm.objExists(joint_name_rule):
        logger.error("Guide and attribute could not be found in the scene.")
        return

    # -- Set the value
    pm.setAttr(joint_name_rule, name_pattern)

    # -- Set the roll attributes
    _set_roll_divisions_zero()

    logger.info("Successfully aligned mGear guide to MetaHuman skeleton.")
