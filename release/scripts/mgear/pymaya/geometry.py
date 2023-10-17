from maya.api import OpenMaya
from maya import cmds
from . import base
from . import exception


class _Geometry(base.Geom):
    _selection_list = OpenMaya.MSelectionList()

    @classmethod
    def Match(cls, nodename):
        return False

    @staticmethod
    def __getComponent(nodename):
        _Geometry._selection_list.clear()
        try:
            _Geometry._selection_list.add(nodename)
        except RuntimeError:
            return (None, None)

        dag, comp = _Geometry._selection_list.getComponent(0)
        if comp.isNull():
            return (None, None)

        return (dag, comp)

    def __init__(self, nodename_or_dagpath, component=None):
        super(_Geometry, self).__init__()
        if isinstance(nodename_or_dagpath, OpenMaya.MDagPath):
            if not isinstance(component, OpenMaya.MObject) or not component.hasFn(OpenMaya.MFn.kComponent):
                raise exception.MayaGeometryError("Invalid component given")
            self.__dagpath = dagpath
            self.__component = component
        else:
            self.__dagpath, self.__component = _Geometry.__getComponent(nodename_or_dagpath)
            if self.__dagpath is None or self.__component is None:
                raise exception.MayaGeometryError(f"No such geometry '{nodename_or_dagpath}'")


class MeshVertex(_Geometry):
    @classmethod
    def Match(cls, nodename):
        _Geometry._selection_list.clear()
        try:
            _Geometry._selection_list.add(nodename)
            return _Geometry._selection_list.getDependNode(0).hasFn(OpenMaya.MFn.kMesh)
        except RuntimeError:
            return False


def BindGeometry(name, silent=False):
    if "." not in name:
        return None

    for cls in [MeshVertex]:
        if cls.Match(name):
            try:
                return cls(name)
            except:
                if not silent:
                    raise

    return None
