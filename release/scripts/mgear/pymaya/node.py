class PyNode(object):
    from maya.api import OpenMaya as _om
    from maya import cmds as _cmds
    from . import attr as _attr

    _selectionlist = _om.MSelectionList()

    @staticmethod
    def __getObjectFromName(nodename):
        PyNode._selectionlist.clear()
        try:
            PyNode._selectionlist.add(nodename)
        except RuntimeError as e:
            return None

        return PyNode._selectionlist.getDependNode(0)

    def __init__(self, nodename):
        super(PyNode, self).__init__()
        self.__attrs = {}
        self.__obj = PyNode.__getObjectFromName(nodename)

        if self.__obj is None:
            raise RuntimeError(f"No such node '{nodename}'")

        if not self.__obj.hasFn(PyNode._om.MFn.kDependencyNode):
            raise RuntimeError(f"Not a dependency node '{nodename}'")

        self.__fn_dg = PyNode._om.MFnDependencyNode(self.__obj)

        if self.__obj.hasFn(PyNode._om.MFn.kDagNode):
            self.__fn_dag = PyNode._om.MFnDagNode(PyNode._om.MDagPath.getAPathTo(self.__obj))
        else:
            self.__fn_dag = None

    def __getattribute__(self, name):
        try:
            return super(PyNode, self).__getattribute__(name)
        except AttributeError:
            attrs = super(PyNode, self).__getattribute__("_PyNode__attrs")
            if name in attrs:
                return attrs[name]

            nfnc = super(PyNode, self).__getattribute__("name")
            if PyNode._cmds.ls(f"{nfnc()}.{name}"):
                at = PyNode._attr.PyAttr(f"{nfnc()}.{name}")
                attrs[name] = at
                return at

            raise

    def dg(self):
        return self.__fn_dg

    def dag(self):
        return self.__fn_dag

    def isDag(self):
        return self.__fn_dag is not None

    def name(self):
        return self.__fn_dg.name() if self.__fn_dag is None else self.__fn_dag.partialPathName()
