from maya.api import OpenMaya
from maya import cmds
from . import base
from . import exception


_SELECTION_LIST = OpenMaya.MSelectionList()


class _Geometry(base.Geom):


    @classmethod
    def Match(cls, dagpath, component):
        return False

    @staticmethod
    def __getComponent(nodename):
        _SELECTION_LIST.clear()
        try:
            _SELECTION_LIST.add(nodename)
        except RuntimeError:
            return (None, None)

        dag, comp = _SELECTION_LIST.getComponent(0)
        if comp.isNull():
            return (None, None)

        return (dag, comp)

    def __init__(self, nodename_or_dagpath, component=None):
        super(_Geometry, self).__init__()
        if isinstance(nodename_or_dagpath, OpenMaya.MDagPath):
            if not isinstance(component, OpenMaya.MObject) or not component.hasFn(OpenMaya.MFn.kComponent):
                raise exception.MayaGeometryError("Invalid component given")
            self.__dagpath = nodename_or_dagpath
            self.__component = component
        else:
            self.__dagpath, self.__component = _Geometry.__getComponent(nodename_or_dagpath)
            if self.__dagpath is None or self.__component is None:
                raise exception.MayaGeometryError(f"No such geometry '{nodename_or_dagpath}'")

    def dagPath(self):
        return self.__dagpath

    def component(self):
        return self.__component


class MeshVertex(_Geometry):
    @classmethod
    def Match(cls, dagpath, component):
        return component.hasFn(OpenMaya.MFn.kMeshVertComponent)

    def __init__(self, nodename_or_dagpath, component=None):
        super(MeshVertex, self).__init__(nodename_or_dagpath, component=component)
        it = OpenMaya.MItMeshVertex(self.dagPath(), self.component())
        minid = None
        maxid = None
        while (not it.isDone()):
            idx = it.index()
            if minid is None:
                minid = idx
                maxid = idx
            else:
                minid = min(minid, idx)
                maxid = max(minid, idx)

            it.next()

        self.__vtxid = ".vtx[" + (str(minid) if minid == maxid else f"{minid}:{maxid}") + "]"

    def name(self):
        return self.dagPath().partialPathName() + self.__vtxid


class MeshFace(_Geometry):
    @classmethod
    def Match(cls, dagpath, component):
        return component.hasFn(OpenMaya.MFn.kMeshPolygonComponent)

    def __init__(self, nodename_or_dagpath, component=None):
        super(MeshFace, self).__init__(nodename_or_dagpath, component=component)
        it = OpenMaya.MItMeshPolygon(self.dagPath(), self.component())
        minid = None
        maxid = None
        while (not it.isDone()):
            idx = it.index()
            if minid is None:
                minid = idx
                maxid = idx
            else:
                minid = min(minid, idx)
                maxid = max(minid, idx)

            it.next()

        self.__faceid = ".vtx[" + (str(minid) if minid == maxid else f"{minid}:{maxid}") + "]"

    def name(self):
        return self.dagPath().partialPathName() + self.__faceid


def BindGeometry(name, silent=False):
    if "." not in name:
        return None

    _SELECTION_LIST.clear()
    try:
        _SELECTION_LIST.add(name)
    except RuntimeError:
        if not silent:
            raise
        return None

    dg = _SELECTION_LIST.getDependNode(0)
    if not dg.hasFn(OpenMaya.MFn.kGeometric):
        if not silent:
            raise exception.MayaGeometryError("Invalid geometry given")
        return None

    try:
        dag, comp = _SELECTION_LIST.getComponent(0)
    except:
        if not silent:
            raise
        return None

    if comp.isNull():
        if not silent:
            raise exception.MayaGeometryError("Invalid geometry given")
        return None

    for cls in [MeshVertex, MeshFace]:
        if cls.Match(dag, comp):
            try:
                return cls(dag, comp)
            except:
                if not silent:
                    raise

    return None
