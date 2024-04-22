from math import degrees
from maya import cmds
from maya.api import OpenMaya
from maya import OpenMaya as om
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


def to_mspace(space, as_api2=True):
    if isinstance(space, int):
        return space

    if as_api2:
        if space == "transform":
            return OpenMaya.MSpace.kTransform
        elif space == "preTransform":
            return OpenMaya.MSpace.kPreTransform
        elif space == "postTransform":
            return OpenMaya.MSpace.kPostTransform
        elif space == "world":
            return OpenMaya.MSpace.kWorld
        elif space == "object":
            return OpenMaya.MSpace.kObject

        return OpenMaya.MSpace.kInvalid
    else:
        if space == "transform":
            return om.MSpace.kTransform
        elif space == "preTransform":
            return om.MSpace.kPreTransform
        elif space == "postTransform":
            return om.MSpace.kPostTransform
        elif space == "world":
            return om.MSpace.kWorld
        elif space == "object":
            return om.MSpace.kObject

        return om.MSpace.kInvalid


def cross(a, b):
    return a ^ b
