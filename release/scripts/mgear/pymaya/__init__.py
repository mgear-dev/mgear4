from .cmd import versions


class _Core(object):
    __Instance = None
    def __new__(self):
        if _Core.__Instance is None:
            _Core.__Instance = super(_Core, self).__new__(self)
            _Core.__Instance.__initialize()

        return _Core.__Instance

    def __init__(self):
        super(_Core, self).__init__()

    def __getattribute__(self, name):
        try:
            return super(_Core, self).__getattribute__(name)
        except AttributeError:
            return getattr(super(_Core, self).__getattribute__("cmd"), name)

    def __initialize(self):
        from . import cmd
        from . import exception
        from . import util
        from .bind import PyNode
        from .node import nt
        from .geometry import MeshVertex, MeshFace
        from . import datatypes

        self.cmd = cmd.cmd
        self.mel = cmd.mel
        self.Callback = cmd.Callback
        self.displayError = cmd.displayError
        self.displayInfo = cmd.displayInfo
        self.displayWarning = cmd.displayWarning
        self.exportSelected = cmd.exportSelected
        self.mel = cmd.mel
        self.hasAttr = cmd.hasAttr
        self.selected = cmd.selected
        self.versions = cmd.versions
        self.importFile = cmd.importFile
        self.sceneName = cmd.sceneName
        self.runtime = cmd.runtime
        self.confirmBox = cmd.confirmBox
        self.general = exception
        self.MayaAttributeError = exception.MayaAttributeError
        self.MayaNodeError = exception.MayaNodeError
        self.util = util
        self.UndoChunk = util.UndoChunk
        self.NameParser = util.NameParser
        self.PyNode = PyNode
        self.nodetypes = nt
        self.nt = nt
        self.MeshVertex = MeshVertex
        self.MeshFace = MeshFace
        self.datatypes = datatypes
        self.dt = datatypes


core = _Core()
