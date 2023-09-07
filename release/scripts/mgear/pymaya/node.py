class PyNode(object):
    from maya.api import OpenMaya as _om
    from maya import cmds as _cmds
    _selectionlist = _om.MSelectionList()

    @staticmethod
    def _getObjectFromName(nodename):
        PyNode._selectionlist.clear()
        try:
            PyNode._selectionlist.add(nodename)
        except RuntimeError as e:
            return None

        return PyNode._selectionlist.getDependNode(0)

    def __new__(self, nodename):
        obj = PyNode._getObjectFromName(nodename)
        if obj is None:
            print(f"[pymaya.PyNode] Error : No such node '{nodename}'")
            return None

        if not obj.hasFn(PyNode._om.MFn.kDependencyNode):
            print(f"[pymaya.PyNode] Error : Not a dependency node '{nodename}'")
            return None

        return super(PyNode, self).__new__(self)

    def __init__(self, nodename):
        super(PyNode, self).__init__()
        self.__obj = PyNode._getObjectFromName(nodename)
        self.__fn_dg = PyNode._om.MFnDependencyNode(self.__obj)

        if self.__obj.hasFn(PyNode._om.MFn.kDagNode):
            self.__fn_dag = PyNode._om.MFnDagNode(PyNode._om.MDagPath.getAPathTo(self.__obj))
        else:
            self.__fn_dag = None

    def dg(self):
        return self.__fn_dg

    def dag(self):
        return self.__fn_dag

    def isDag(self):
        return self.__fn_dag is not None

    def name(self):
        return self.__fn_dg.name() if self.__fn_dag is None else self.__fn_dag.partialPathName()
