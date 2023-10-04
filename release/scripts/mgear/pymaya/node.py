from maya.api import OpenMaya
from maya import cmds
from . import attr
from . import base
from . import exception


class PyNode(base.Node):
    __selection_list = OpenMaya.MSelectionList()

    @staticmethod
    def __getObjectFromName(nodename):
        PyNode.__selection_list.clear()
        try:
            PyNode.__selection_list.add(nodename)
        except RuntimeError as e:
            return None

        return PyNode.__selection_list.getDependNode(0)

    def __init__(self, nodename_or_mobject):
        super(PyNode, self).__init__()
        self.__attrs = {}

        if isinstance(nodename_or_mobject, OpenMaya.MObject):
            self.__obj = nodename_or_mobject
        else:
            self.__obj = PyNode.__getObjectFromName(nodename_or_mobject)
            if self.__obj is None:
                raise exception.MayaNodeError(f"No such node '{nodename_or_mobject}'")

        if not self.__obj.hasFn(OpenMaya.MFn.kDependencyNode):
            raise exception.MayaNodeError(f"Not a dependency node '{nodename_or_mobject}'")

        self.__fn_dg = OpenMaya.MFnDependencyNode(self.__obj)

        if self.__obj.hasFn(OpenMaya.MFn.kDagNode):
            self.__fn_dag = OpenMaya.MFnDagNode(OpenMaya.MDagPath.getAPathTo(self.__obj))
        else:
            self.__fn_dag = None

    def __getattribute__(self, name):
        try:
            return super(PyNode, self).__getattribute__(name)
        except AttributeError:
            nfnc = super(PyNode, self).__getattribute__("name")
            if cmds.ls(f"{nfnc()}.{name}"):
                return super(PyNode, self).__getattribute__("attr")(name)

            raise

    def __eq__(self, other):
        return self.__obj == other.__obj

    def __ne__(self, other):
        return self.__obj != other.__obj

    def dg(self):
        return self.__fn_dg

    def dag(self):
        return self.__fn_dag

    def isDag(self):
        return self.__fn_dag is not None

    def name(self):
        return self.__fn_dg.name() if self.__fn_dag is None else self.__fn_dag.partialPathName()

    def attr(self, name):
        if name in self.__attrs:
            return self.__attrs[name]

        nfnc = super(PyNode, self).__getattribute__("name")
        if cmds.ls(f"{nfnc()}.{name}"):
            at = attr.PyAttr(f"{nfnc()}.{name}")
            self.__attrs[name] = at
            return at

        raise exception.MayaAttributeError(f"No '{name}' attr found")
