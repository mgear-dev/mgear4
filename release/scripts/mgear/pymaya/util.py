from math import degrees
from maya import cmds


class UndoChunk(object):
    def __init__(self):
        super(UndoChunk, self).__init__()

    def __enter__(self):
        cmds.undoInfo(ock=True)

    def __exit__(self, exc_type, exc_value, traceback):
        cmds.undoInfo(cck=True)
