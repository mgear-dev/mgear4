# Shifter guides IO utility functions
import os
import json
import sys
import pymel.core as pm
from mgear import shifter
from mgear.core import curve

if sys.version_info[0] == 2:
    string_types = (basestring, )
else:
    string_types = (str,)


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
    startDir = pm.workspace(q=True, rootDirectory=True)
    filePath = pm.fileDialog2(
        startingDirectory=startDir,
        fileMode=mode,
        fileFilter='Shifter Guide Template .sgt (*%s)' % ".sgt")

    if not filePath:
        return
    if not isinstance(filePath, string_types):
        filePath = filePath[0]

    return filePath


def export_guide_template(filePath=None, meta=None, conf=None, *args):
    """Export the guide templata to a file

    Args:
        filePath (str, optional): Path to save the file
        meta (dict, optional): Arbitraty metadata dictionary. This can
            be use to store any custom information in a dictionary format.
    """
    if not conf:
        conf = get_template_from_selection(meta)
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
    """
    if not conf:
        conf = _import_guide_template(filePath)
    if conf:
        rig = shifter.Rig()
        rig.guide.set_from_dict(conf)
        partial_names, partial_idx = rig.guide.draw_guide(partial, initParent)

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


def import_guide_template(filePath=None, conf=None, *args):
    """Import a guide template

    Args:
        filePath (str, optional): Path to the template file to import
    """
    import_partial_guide(filePath, conf=conf)


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
