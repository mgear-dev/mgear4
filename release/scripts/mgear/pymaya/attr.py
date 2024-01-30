import re
from maya import cmds
from maya.api import OpenMaya
from . import base
from . import cmd
from . import exception


class Attribute(base.Attr):
    __selectionlist = OpenMaya.MSelectionList()

    @staticmethod
    def __getPlug(attrname):
        Attribute.__selectionlist.clear()
        try:
            Attribute.__selectionlist.add(attrname)
        except RuntimeError as e:
            return None

        return Attribute.__selectionlist.getPlug(0)

    def __init__(self, attrname_or_mplug):
        super(Attribute, self).__init__()
        self.__attrs = {}

        if isinstance(attrname_or_mplug, OpenMaya.MPlug):
            self.__plug = attrname_or_mplug
        else:
            self.__plug = Attribute.__getPlug(attrname_or_mplug)
            if self.__plug is None:
                raise RuntimeError("No such attribute '{}'".format(attrname_or_mplug))

    def __hash__(self):
        return hash(self.name())

    def __getitem__(self, index):
        if not self.__plug.isArray:
            raise TypeError("{} is not an array plug".format(self.name()))

        return Attribute(self.__plug.elementByLogicalIndex(index))

    def __getattribute__(self, name):
        try:
            return super(Attribute, self).__getattribute__(name)
        except AttributeError:
            nfnc = super(Attribute, self).__getattribute__("name")
            if cmds.ls("{}.{}".format(nfnc(), name)):
                return super(Attribute, self).__getattribute__("attr")(name)

            raise

    def __floordiv__(self, other):
        return self.disconnect(other)

    def __rshift__(self, other):
        return self.connect(other, f=True)

    def plug(self):
        return self.__plug

    def name(self):
        obj = self.__plug.node()
        nfunc = None

        if obj.hasFn(OpenMaya.MFn.kDagNode):
            nfunc = OpenMaya.MFnDagNode(OpenMaya.MDagPath.getAPathTo(obj)).partialPathName
        else:
            nfunc = OpenMaya.MFnDependencyNode(obj).name

        return "{}.{}".format(nfunc(), self.__plug.partialName(False, False, False, False, False, True))

    def node(self):
        from . import node
        obj = self.__plug.node()

        if obj.hasFn(OpenMaya.MFn.kDagNode):
            nfunc = OpenMaya.MFnDagNode(OpenMaya.MDagPath.getAPathTo(obj)).partialPathName
        else:
            nfunc = OpenMaya.MFnDependencyNode(obj).name

        return node.BindNode(nfunc())

    def delete(self):
        cmds.deleteAttr(self.name())

    def connect(self, other, **kwargs):
        return cmds.connectAttr(self.name(), other.name() if isinstance(other, Attribute) else other)

    def disconnect(self, other):
        return cmds.disconnectAttr(self.name(), other.name() if isinstance(other, Attribute) else other)

    def listConnections(self, **kwargs):
        return cmd.listConnections(self, **kwargs)

    def attr(self, name):
        attr_cache = super(Attribute, self).__getattribute__("_Attribute__attrs")
        if name in attr_cache:
            return attr_cache[name]

        this_plug = super(Attribute, self).__getattribute__("_Attribute__plug")
        ln = this_plug.partialName(False, False, False, False, False, True).split(".")[-1]
        sn = this_plug.partialName(False, False, False, False, False, False).split(".")[-1]
        res = re.match("{}\[([0-9])+\]".format(ln), name)
        if res:
            return super(Attribute, self).__getattribute__("__getitem__")(int(res.group(1)))
        res = re.match("{}\[([0-9])+\]".format(sn), name)
        if res:
            return super(Attribute, self).__getattribute__("__getitem__")(int(res.group(1)))

        if this_plug.isCompound:
            for ci in range(this_plug.numChildren()):
                cp = this_plug.child(ci)
                at = None
                if name == cp.partialName(False, False, False, False, False, True).split(".")[-1]:
                    at = Attribute(cp)
                elif name == cp.partialName(False, False, False, False, False, False).split(".")[-1]:
                    at = Attribute(cp)
                else:
                    continue

                attr_cache[name] = at
                return at

        raise exception.MayaAttributeError("No '{}' attr found".format(name))

    def lock(self):
        cmd.setAttr(self, l=True)

    def unlock(self):
        cmd.setAttr(self, l=False)

    def children(self):
        if not self.plug().isCompound:
            raise RuntimeError(f"{self.name()} has no children")

        return [Attribute(self.plug().child(x)) for x in range(self.plug().numChildren())]

    def get(self, *args, **kwargs):
        return cmd.getAttr(self, *args, **kwargs)

    def set(self, *args, **kwargs):
        cmd.setAttr(self, *args, **kwargs)
