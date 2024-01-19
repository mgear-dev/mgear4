import re
from maya.api import OpenMaya
from maya import cmds
from . import base
from . import datatypes
from . import exception


_SELECTION_LIST = OpenMaya.MSelectionList()


def _to_mspace(space_str):
    if space_str == "transform":
        return OpenMaya.MSpace.kTransform
    elif space_str == "preTransform":
        return OpenMaya.MSpace.kPreTransform
    elif space_str == "postTransform":
        return OpenMaya.MSpace.kPostTransform
    elif space_str == "world":
        return OpenMaya.MSpace.kWorld
    elif space_str == "object":
        return OpenMaya.MSpace.kObject

    return OpenMaya.MSpace.kInvalid


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

    def __iter__(self):
        return iter([])

    def __init__(self, nodename_or_dagpath, component):
        super(_Geometry, self).__init__()
        if isinstance(nodename_or_dagpath, OpenMaya.MDagPath):
            if not isinstance(component, OpenMaya.MObject) or not component.hasFn(OpenMaya.MFn.kComponent):
                raise exception.MayaGeometryError("Invalid component given")
            self.__dagpath = nodename_or_dagpath
            self.__component = component
        else:
            self.__dagpath, self.__component = _Geometry.__getComponent(nodename_or_dagpath)
            if self.__dagpath is None or self.__component is None:
                raise exception.MayaGeometryError("No such geometry '{}'".format(nodename_or_dagpath))

    def dagPath(self):
        return self.__dagpath

    def component(self):
        return self.__component


class MeshVertex(_Geometry):
    @classmethod
    def Match(cls, dagpath, component):
        return component.hasFn(OpenMaya.MFn.kMeshVertComponent)

    def __iter__(self):
        it = OpenMaya.MItMeshVertex(self.dagPath(), self.component())
        while (not it.isDone()):
            comp = OpenMaya.MFnSingleIndexedComponent()
            comp_obj = comp.create(OpenMaya.MFn.kMeshVertComponent)
            comp.addElement(it.index())
            it.next()
            yield MeshVertex(self.dagPath(), comp_obj)

    def __init__(self, nodename_or_dagpath, component):
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

        self.__vtxid = ".vtx[" + (str(minid) if minid == maxid else "{}:{}".format(minid, maxid)) + "]"

    def name(self):
        return self.dagPath().partialPathName() + self.__vtxid

    def getPosition(self, space="preTransform"):
        it = OpenMaya.MItMeshVertex(self.dagPath(), self.component())
        return datatypes.Point(it.position(_to_mspace(space)))


class MeshFace(_Geometry):
    @classmethod
    def Match(cls, dagpath, component):
        return component.hasFn(OpenMaya.MFn.kMeshPolygonComponent)

    def __iter__(self):
        it = OpenMaya.MItMeshPolygon(self.dagPath(), self.component())
        while (not it.isDone()):
            comp = OpenMaya.MFnSingleIndexedComponent()
            comp_obj = comp.create(OpenMaya.MFn.kMeshPolygonComponent)
            comp.addElement(it.index())
            it.next()
            yield MeshFace(self.dagPath(), comp_obj)

    def __init__(self, nodename_or_dagpath, component):
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

        self.__faceid = ".f[" + (str(minid) if minid == maxid else "{}:{}".format(minid, maxid)) + "]"

    def name(self):
        return self.dagPath().partialPathName() + self.__faceid


class NurbsCurveCV(_Geometry):
    @classmethod
    def Match(cls, dagpath, component):
        return component.hasFn(OpenMaya.MFn.kCurveCVComponent)

    def __iter__(self):
        it = OpenMaya.MItCurveCV(self.dagPath(), self.component())
        while (not it.isDone()):
            comp = OpenMaya.MFnSingleIndexedComponent()
            comp_obj = comp.create(OpenMaya.MFn.kCurveCVComponent)
            comp.addElement(it.index())
            it.next()
            yield NurbsCurveCV(self.dagPath(), comp_obj)

    def __init__(self, nodename_or_dagpath, component=None):
        super(NurbsCurveCV, self).__init__(nodename_or_dagpath, component=component)
        it = OpenMaya.MItCurveCV(self.dagPath(), self.component())
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

        self.__cvid = ".cv[" + (str(minid) if minid == maxid else "{}:{}".format(minid, maxid)) + "]"

    def name(self):
        return self.dagPath().partialPathName() + self.__cvid

    def getPosition(self, space="preTransform"):
        it = OpenMaya.MItCurveCV(self.dagPath(), self.component())
        return datatypes.Point(it.position(_to_mspace(space)))


def BindGeometry(name, silent=False):
    if "." not in name:
        return None

    if not re.search("\[[0-9:]+\]$", name):
        name += "[:]"

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

    for cls in [MeshVertex, MeshFace, NurbsCurveCV]:
        if cls.Match(dag, comp):
            try:
                return cls(dag, comp)
            except:
                if not silent:
                    raise

    return None
