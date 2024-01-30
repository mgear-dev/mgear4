from maya.api import OpenMaya
from maya import cmds
from . import cmd
from . import attr
from . import base
from . import datatypes
from . import exception
from . import geometry
from functools import partial


def _getPivots(node, **kwargs):
    kwargs.pop("pivots", kwargs.pop("piv", None))
    kwargs["pivots"] = True
    kwargs["q"] = True
    res = cmd.xform(node, **kwargs)
    return (datatypes.Vector(res[:3]), datatypes.Vector(res[3:]))


def _setTransformation(node, matrix):
    if isinstance(matrix, OpenMaya.MMatrix):
        matrix = OpenMaya.MTransformationMatrix(matrix)

    OpenMaya.MFnTransform(node.dagPath()).setTransformation(matrix)


def _getTransformation(node):
    return datatypes.TransformationMatrix(OpenMaya.MFnTransform(node.dagPath()).transformationMatrix())


def _getShape(node, **kwargs):
    shapes = node.getShapes(**kwargs)
    if shapes:
        return shapes[0]

    return None


def _getShapes(node, **kwargs):
    kwargs.pop("shapes", kwargs.pop("s", None))
    kwargs["shapes"] = True
    return cmd.listRelatives(node, **kwargs)


def _getParent(node):
    res = cmd.listRelatives(node, p=True)
    if res:
        return res[0]

    return None


def _addChild(node, child):
    return cmd.parent(child, node)


def _setMatrix(node, val, **kwargs):
    kwargs.pop("m", kwargs.pop("matrix", None))
    kwargs["m"] = cmd._dt_to_value(val)
    cmd.xform(node, **kwargs)


def _getMatrix(node, **kwargs):
    kwargs.pop("m", kwargs.pop("matrix", None))
    kwargs.pop("q", kwargs.pop("query", None))
    kwargs.update({"q": True, "m": True})
    return datatypes.Matrix(cmd.xform(node, **kwargs))


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

    def __hash__(self):
        return hash(self.name())

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
            self.getPivots = partial(_getPivots, self)
            self.setTransformation = partial(_setTransformation, self)
            self.getTransformation = partial(_getTransformation, self)
            self.getShape = partial(_getShape, self)
            self.getShapes = partial(_getShapes, self)
            self.getParent = partial(_getParent, self)
            self.addChild = partial(_addChild, self)
            self.setMatrix = partial(_setMatrix, self)
            self.getMatrix = partial(_getMatrix, self)
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
            elif cmds.ls("{}.{}[:]".format(nfnc(), name)):
                return geometry.BindGeometry("{}.{}[:]".format(nfnc(), name))

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
        fdag = super(_Node, self).__getattribute__("_Node__fn_dag")
        if fdag is not None:
            return fdag.partialPathName()
        fdg = super(_Node, self).__getattribute__("_Node__fn_dg")
        return fdg.name()

    def namespace(self, **kwargs):
        n = self.name()
        if ":" not in n:
            return ""
        return ":".join(n.split("|")[-1].split(":")[:-1]) + ":"

    def attr(self, name, checkShape=True):
        attr_cache = super(_Node, self).__getattribute__("_Node__attrs")
        if name in attr_cache:
            return attr_cache[name]

        p = None
        fn_dg = super(_Node, self).__getattribute__("_Node__fn_dg")
        try:
            p = fn_dg.findPlug(name, False)
        except Exception:
            if checkShape:
                get_shape = super(_Node, self).__getattribute__("getShape")
                shape = get_shape()
                if shape:
                    try:
                        p = shape.dgFn().findPlug(name, False)
                    except:
                        pass

            if p is None:
                raise exception.MayaAttributeError("No '{}' attr found".format(name))

        at = attr.Attribute(p)
        attr_cache[name] = at
        return at

    def addAttr(self, name, **kwargs):
        kwargs.pop("ln", None)
        kwargs.pop("longName", None)
        kwargs["longName"] = name
        return cmds.addAttr(self.name(), **kwargs)

    def getAttr(self, name, **kwargs):
        return cmd.getAttr("{}.{}".format(self.name(), name), **kwargs)

    def setAttr(self, name, *args, **kwargs):
        return cmd.setAttr("{}.{}".format(self.name(), name), *args, **kwargs)

    def hasAttr(self, name, checkShape=True):
        return cmds.objExists("{}.{}".format(self.name(), name))

    def listConnections(self, **kwargs):
        return cmd.listConnections(self, **kwargs)

    def listRelatives(self, **kwargs):
        return cmd.listRelatives(self, **kwargs)

    def type(self):
        return self.__fn_dg.typeName

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


class SoftMod(_Node):
    def __init__(self, nodename_or_mobject):
        super(SoftMod, self).__init__(nodename_or_mobject)

    def getGeometry(self):
        # pymel returns str list
        return cmds.softMod(self.name(), g=True, q=True)


nt.registerClass("softMod", cls=SoftMod)


def BindNode(name):
    if not cmds.objExists(name):
        raise exception.MayaNodeError("No such node '{}'".format(name))

    return nt.getTypeClass(cmds.nodeType(name))(name)
