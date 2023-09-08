from maya.api import OpenMaya


class PyAttr(object):
    __selectionlist = OpenMaya.MSelectionList()

    @staticmethod
    def __getPlug(attrname):
        PyAttr.__selectionlist.clear()
        try:
            PyAttr.__selectionlist.add(attrname)
        except RuntimeError as e:
            return None

        return PyAttr.__selectionlist.getDependNode(0)

    def __init__(self, attrname):
        super(PyAttr, self).__init__()
        self.__plug = PyAttr.__getPlug(attrname)
        if self.__plug is None:
            raise RuntimeError(f"No such attribute '{attrname}'")
