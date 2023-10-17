from maya.api import OpenMaya
from maya import cmds
from . import attr
from . import base
from . import exception


class _Node(base.Node):
    __selection_list = OpenMaya.MSelectionList()

    @staticmethod
    def __getObjectFromName(nodename):
        _Node.__selection_list.clear()
        try:
            _Node.__selection_list.add(nodename)
        except RuntimeError as e:
            return None

        return _Node.__selection_list.getDependNode(0)

    def __init__(self, nodename_or_mobject):
        super(_Node, self).__init__()
        self.__attrs = {}

        if isinstance(nodename_or_mobject, OpenMaya.MObject):
            self.__obj = nodename_or_mobject
        else:
            self.__obj = _Node.__getObjectFromName(nodename_or_mobject)
            if self.__obj is None:
                raise exception.MayaNodeError(f"No such node '{nodename_or_mobject}'")

        if not self.__obj.hasFn(OpenMaya.MFn.kDependencyNode):
            raise exception.MayaNodeError(f"Not a dependency node '{nodename_or_mobject}'")

        self.__fn_dg = OpenMaya.MFnDependencyNode(self.__obj)

        if self.__obj.hasFn(OpenMaya.MFn.kDagNode):
            dagpath = OpenMaya.MDagPath.getAPathTo(self.__obj)
            self.__dagpath = dagpath
            self.__fn_dag = OpenMaya.MFnDagNode(dagpath)
        else:
            self.__dagpath = None
            self.__fn_dag = None

    def __getattribute__(self, name):
        try:
            return super(_Node, self).__getattribute__(name)
        except AttributeError:
            nfnc = super(_Node, self).__getattribute__("name")
            if cmds.ls(f"{nfnc()}.{name}"):
                return super(_Node, self).__getattribute__("attr")(name)

            raise

    def __eq__(self, other):
        return self.__obj == other.__obj

    def __ne__(self, other):
        return self.__obj != other.__obj

    def object(self):
        return self.__obj

    def dgFn(self):
        return self.__fn_dg

    def dagFn(self):
        return self.__fn_dag

    def dagPath(self):
        return self.__dagpath

    def isDag(self):
        return self.__fn_dag is not None

    def name(self):
        return self.__fn_dg.name() if self.__fn_dag is None else self.__fn_dag.partialPathName()

    def attr(self, name):
        if name in self.__attrs:
            return self.__attrs[name]

        nfnc = super(_Node, self).__getattribute__("name")
        if cmds.ls(f"{nfnc()}.{name}"):
            at = attr.Attribute(f"{nfnc()}.{name}")
            self.__attrs[name] = at
            return at

        raise exception.MayaAttributeError(f"No '{name}' attr found")


class _NodeTypes(object):
    __Instance = None

    def __new__(self):
        if _NodeTypes.__Instance is None:
            _NodeTypes.__Instance = super(_NodeTypes, self).__new__(self)
            _NodeTypes.__Instance.__types = {}

        return _NodeTypes.__Instance

    def registerClass(self, typename, cls=None):
        if cls is not None:
            self.__types[typename] = cls
        else:
            class _New(_Node):
                def __repr__(self):
                    return f"{typename[0].upper()}{typename[1:]}('{self.name()}')"

            self.__types[typename] = _New

    def getTypeClass(self, typename):
        if typename in self.__types:
            return self.__types[typename]

        if typename in cmds.allNodeTypes():
            self.registerClass(typename, cls=None)
            return self.__types[typename]

        return None

    def __getattribute__(self, name):
        try:
            return super(_NodeTypes, self).__getattribute__(name)
        except AttributeError:
            tcls = super(_NodeTypes, self).__getattribute__("getTypeClass")(f"{name[0].lower()}{name[1:]}")
            if tcls:
                return tcls

            raise

    def __init__(self):
        super(_NodeTypes, self).__init__()


nt = _NodeTypes()


def BindNode(name):
    if not cmds.objExists(name):
        raise exception.MayaNodeError(f"No such node '{name}'")

    return nt.getTypeClass(cmds.nodeType(name))(name)
