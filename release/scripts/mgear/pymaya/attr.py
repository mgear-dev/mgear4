from maya import cmds
from maya.api import OpenMaya
from . import base


class PyAttr(base.Attr):
    __selectionlist = OpenMaya.MSelectionList()

    @staticmethod
    def __getPlug(attrname):
        PyAttr.__selectionlist.clear()
        try:
            PyAttr.__selectionlist.add(attrname)
        except RuntimeError as e:
            return None

        return PyAttr.__selectionlist.getPlug(0)

    def __init__(self, attrname_or_mplug):
        super(PyAttr, self).__init__()
        self.__attrs = {}
        self.__node_name_func = None

        if isinstance(attrname_or_mplug, OpenMaya.MPlug):
            self.__plug = attrname_or_mplug
        else:
            self.__plug = PyAttr.__getPlug(attrname_or_mplug)
            if self.__plug is None:
                raise RuntimeError(f"No such attribute '{attrname_or_mplug}'")

    def __getitem__(self, index):
        if not self.__plug.isArray:
            raise TypeError(f"{self.name()} is not an array plug")

        if index >= self.__plug.numElements():
            print(self.__plug.numElements())
            raise IndexError("index out of range")

        return PyAttr(f"{self.name()}[{index}]")

    def __getattribute__(self, name):
        try:
            return super(PyAttr, self).__getattribute__(name)
        except AttributeError:
            attr_cache = super(PyAttr, self).__getattribute__("_PyAttr__attrs")
            if name in attr_cache:
                return attr_cache[name]

            nfnc = super(PyAttr, self).__getattribute__("name")
            if cmds.ls(f"{nfnc()}.{name}"):
                at = PyAttr(f"{nfnc()}.{name}")
                attr_cache[name] = at
                return at

            raise

    def __floordiv__(self, other):
        return self.disconnect(other)

    def __rshift__(self, other):
        return self.connect(other, f=True)

    def plug(self):
        return self.__plug

    def name(self):
        obj = self.__plug.node()
        nfunc = super(PyAttr, self).__getattribute__("_PyAttr__node_name_func")
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
        return cmds.connectAttr(self.name(), other.name() if isinstance(other, PyAttr) else other)

    def disconnect(self, other):
        return cmds.disconnectAttr(self.name(), other.name() if isinstance(other, PyAttr) else other)
