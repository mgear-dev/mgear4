from maya import cmds
from maya.api import OpenMaya
from . import base
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
        self.__node_name_func = None

        if isinstance(attrname_or_mplug, OpenMaya.MPlug):
            self.__plug = attrname_or_mplug
        else:
            self.__plug = Attribute.__getPlug(attrname_or_mplug)
            if self.__plug is None:
                raise RuntimeError(f"No such attribute '{attrname_or_mplug}'")

    def __getitem__(self, index):
        if not self.__plug.isArray:
            raise TypeError(f"{self.name()} is not an array plug")

        if index >= self.__plug.numElements():
            print(self.__plug.numElements())
            raise IndexError("index out of range")

        return Attribute(f"{self.name()}[{index}]")

    def __getattribute__(self, name):
        try:
            return super(Attribute, self).__getattribute__(name)
        except AttributeError:
            nfnc = super(Attribute, self).__getattribute__("name")
            if cmds.ls(f"{nfnc()}.{name}"):
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
        nfunc = super(Attribute, self).__getattribute__("_Attribute__node_name_func")
        if nfunc is None:
            if obj.hasFn(OpenMaya.MFn.kDagNode):
                nfunc = OpenMaya.MFnDagNode(OpenMaya.MDagPath.getAPathTo(obj)).partialPathName
            else:
                nfunc = OpenMaya.MFnDependencyNode(obj).name

            self.__node_name_func = nfunc

        return f"{nfunc()}.{self.__plug.partialName(False, False, False, False, False, True)}"

    def delete(self):
        cmds.deleteAttr(self.name())

    def connect(self, other, **kwargs):
        return cmds.connectAttr(self.name(), other.name() if isinstance(other, Attribute) else other)

    def disconnect(self, other):
        return cmds.disconnectAttr(self.name(), other.name() if isinstance(other, Attribute) else other)

    def attr(self, name):
        attr_cache = super(Attribute, self).__getattribute__("_Attribute__attrs")
        if name in self.__attrs:
            return self.__attrs[name]

        nfnc = super(Attribute, self).__getattribute__("name")
        if cmds.ls(f"{nfnc()}.{name}"):
            at = Attribute(f"{nfnc()}.{name}")
            self.__attrs[name] = at
            return at

        raise exception.MayaAttributeError(f"No '{name}' attr found")
