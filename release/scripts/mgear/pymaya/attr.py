class PyAttr(object):
    from maya.api import OpenMaya as _om
    from maya import cmds as _cmds

    _selectionlist = _om.MSelectionList()

    @staticmethod
    def __getPlug(attrname):
        PyAttr._selectionlist.clear()
        try:
            PyAttr._selectionlist.add(attrname)
        except RuntimeError as e:
            return None

        return PyAttr._selectionlist.getDependNode(0)

    def __init__(self, attrname):
        super(PyAttr, self).__init__()
        self.__plug = PyAttr.__getPlug(attrname)
        if self.__plug is None:
            raise RuntimeError(f"No such attribute '{attrname}'")
