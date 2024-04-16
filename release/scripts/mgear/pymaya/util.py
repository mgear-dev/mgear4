from math import degrees
from maya import cmds
from maya.api import OpenMaya
from . import base
import math


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


def to_mspace(space_str):
    if space_str == "transform":
        return OpenMaya.MSpace.kTransform
    elif space_str == "preTransform":
        return OpenMaya.MSpace.kPreTransform
    elif space_str == "postTransform":
        return OpenMaya.MSpace.kPostTransform
    elif space_str == "world":
        return OpenMaya.MSpace.kWorld
    elif space_str == "object":
        return OpenMaya.MSpace.kObject

    return OpenMaya.MSpace.kInvalid
