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

    def plug(self):
        return self.__plug

    def name(self):
        return self.__plug.name()
