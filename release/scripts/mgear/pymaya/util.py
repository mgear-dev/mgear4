from math import degrees
from maya import cmds
from . import base


class UndoChunk(object):
    def __init__(self):
        super(UndoChunk, self).__init__()

    def __enter__(self):
        cmds.undoInfo(ock=True)

    def __exit__(self, exc_type, exc_value, traceback):
        cmds.undoInfo(cck=True)


class NameParser(object):
    def __init__(self, name_or_node):
        super(NameParser, self).__init__()
        self.__name_or_node = name_or_node

    def stripNamespace(self):
        n = self.__name_or_node
        if isinstance(n, base.Base):
            n = n.name()

        return "|".join([x.split(":")[-1] for x in n.split("|")])
