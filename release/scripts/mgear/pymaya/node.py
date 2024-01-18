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
                raise exception.MayaNodeError("No such node '{}'".format(nodename_or_mobject))

        if not self.__obj.hasFn(OpenMaya.MFn.kDependencyNode):
            raise exception.MayaNodeError("Not a dependency node '{}'".format(nodename_or_mobject))

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
            if cmds.ls("{}.{}".format(nfnc(), name)):
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
        if cmds.ls("{}.{}".format(nfnc(), name)):
            at = attr.Attribute("{}.{}".format(nfnc(), name))
            self.__attrs[name] = at
            return at

        raise exception.MayaAttributeError("No '{}' attr found".format(name))

    def addAttr(self, name, **kwargs):
        kwargs.pop("ln")
        kwargs.pop("longName")
        kwargs["longName"] = name
        return cmds.addAttr(self.name(), **kwargs)

    def getAttr(self, name, **kwargs):
        return cmds.getAttr("{}.{}".format(self.name(), name), **kwargs)

    def hasAttr(self, name, checkShape=True):
        return cmds.objExists("{}.{}".format(self.name(), name))

    def listConnections(self, **kwargs):
        return cmds.listConnections("{}.{}".format(self.name(), name), **kwargs)

    def namespace(self):
        nss = self.name().split("|")[-1].split(":")[:-1]
        if not nss:
            return ""

        return ":".join(nss) + ":"

    def node(self):
        return self

    def rename(self, name):
        return cmds.rename(self.name(), name)

    def startswith(self, word):
        return self.name().startswith(word)

    def endswith(self, word):
        return self.name().endswith(word)

    def replace(self, old, new):
        return self.name().replace(old, new)

    def split(self, word):
        return self.name().split(word)


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
                    return "{}{}('{}')".format(typename[0].upper(), typename[1:], self.name())

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
            tcls = super(_NodeTypes, self).__getattribute__("getTypeClass")("{}{}".format(name[0].lower(), name[1:]))
            if tcls:
                return tcls

            raise

    def __init__(self):
        super(_NodeTypes, self).__init__()


nt = _NodeTypes()


def BindNode(name):
    if not cmds.objExists(name):
        raise exception.MayaNodeError("No such node '{}'".format(name))

    return nt.getTypeClass(cmds.nodeType(name))(name)
