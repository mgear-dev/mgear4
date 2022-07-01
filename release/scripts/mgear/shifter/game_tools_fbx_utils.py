import pymel.core as pm
import sys

from mgear.core import pyFBX as pfbx


def export_skeletal_mesh(jnt_root, mesh_root, path, **kwargs):

    # export settings config
    pfbx.FBXResetExport()

    # select elements
    pm.select([jnt_root, mesh_root])

    # export
    pfbx.FBXExport(f=path, s=True)

    # post process with FBX SDK if available
    return


def export_clip():
    return


if __name__ == "__main__":

    if sys.version_info[0] == 2:
        reload(pfbx)
    else:
        import importlib

        importlib.reload(pfbx)

    export_skeletal_mesh(
        "Root", "geo_root", r"C:\Users/Miquel/Desktop/testing_auto2.fbx"
    )
