from . import base
from . import exception
from . import datatypes
from maya import cmds
from maya import mel
from maya.api import OpenMaya
import functools
import inspect


__all__ = []
__DO_NOT_CAST_FUNCS = set()
__SCOPE_ATTR_FUNCS = {"listAttr"}


SCOPE_ATTR = 0
SCOPE_NODE = 1
Callback = functools.partial
displayError = OpenMaya.MGlobal.displayError
displayInfo = OpenMaya.MGlobal.displayInfo
displayWarning = OpenMaya.MGlobal.displayWarning
# TODO : None to list


def exportSelected(*args, **kwargs):
    cmds.file(*args, es=True, **kwargs)


def hasAttr(obj, attr, checkShape=True):
    obj = _obj_to_name(obj)

    has = cmds.attributeQuery(attr, n=obj, ex=True)
    if not has and checkShape:
        shapes = cmds.listRelatives(obj, s=True) or []
        for s in shapes:
            has = cmds.attributeQuery(attr, n=s, ex=True)
            if has:
                break

    return has


def selected(**kwargs):
    return _name_to_obj(cmds.ls(sl=True, **kwargs))


class versions():
    def current():
        return cmds.about(api=True)


def importFile(filepath, **kwargs):
    return _name_to_obj(cmds.file(filepath, i=True, **kwargs))


class NameParser(object):
    def __init__(self, name_or_node):
        super(NameParser, self).__init__()
        self.__name_or_node = name_or_node

    def stripNamespace(self):
        n = self.__name_or_node
        if isinstance(n, base.Base):
            n = n.name()

        return "|".join([x.split(":")[-1] for x in n.split("|")])


def sceneName():
    return cmds.file(q=True, sn=True)


class MayaGUIs(object):
    def GraphEditor(self):
        cmds.GraphEditor()

runtime = MayaGUIs()


def confirmBox(title, message, yes="Yes", no="No", *moreButtons, **kwargs):
    ret = cmds.confirmDialog(t=title, m=message, b=[yes, no] + list(moreButtons), db=yes, ma="center", cb=no, ds=no)
    if moreButtons:
        return ret
    else:
        return (ret == yes)


__all__.append("Callback")
__all__.append("displayError")
__all__.append("displayInfo")
__all__.append("displayWarning")
__all__.append("exportSelected")
__all__.append("mel")
__all__.append("hasAttr")
__all__.append("selected")
__all__.append("versions")
__all__.append("importFile")
__all__.append("NameParser")
__all__.append("sceneName")
__all__.append("runtime")
__all__.append("confirmBox")


def _obj_to_name(arg):
    if isinstance(arg, (list, set, tuple)):
        return arg.__class__([_obj_to_name(x) for x in arg])
    elif isinstance(arg, base.Base):
        return arg.name()
    else:
        return arg


def _dt_to_value(arg):
    if isinstance(arg, (list, set, tuple)):
        return arg.__class__([_dt_to_value(x) for x in arg])
    elif isinstance(arg, datatypes.Vector):
        return [arg[0], arg[1], arg[2]]
    elif isinstance(arg, datatypes.Point):
        return [arg[0], arg[1], arg[2], arg[3]]
    elif isinstance(arg, datatypes.Matrix):
        return [arg[0], arg[1], arg[2], arg[3],
                arg[4], arg[5], arg[6], arg[7],
                arg[8], arg[9], arg[10], arg[11],
                arg[12], arg[13], arg[14], arg[15]]
    else:
        return arg


def _name_to_obj(arg, scope=SCOPE_NODE, known_node=None):
    # lazy importing
    from . import bind

    if isinstance(arg, (list, set, tuple)):
        return arg.__class__([_name_to_obj(x, scope=scope, known_node=known_node) for x in arg])

    elif isinstance(arg, str):
        if (scope == SCOPE_ATTR and known_node is not None):
            try:
                return bind.PyNode("{}.{}".format(known_node, arg))
            except:
                return arg
        else:
            try:
                return bind.PyNode(arg)
            except:
                return arg
    else:
        return arg


def _pymaya_cmd_wrap(func, wrap_object=True, scope=SCOPE_NODE):
    def wrapper(*args, **kwargs):
        nargs = _obj_to_name(args)
        nkwargs = {}
        for k, v in kwargs.items():
            nkwargs[k] = _obj_to_name(v)

        res = func(*nargs, **nkwargs)

        if wrap_object:
            known_node = None
            if scope == SCOPE_ATTR:
                candi = None

                if nargs:
                    known_node = nargs[0]
                else:
                    sel = cmds.ls(sl=True)
                    if sel:
                        known_node = sel[0]

                if known_node is not None:
                    if not isinstance(_name_to_obj(known_node), base.Base):
                        known_node = None

            return _name_to_obj(res, scope=scope, known_node=known_node)
        else:
            return res

    return wrapper


def getAttr(*args, **kwargs):
    args = _obj_to_name(args)
    kwargs = _obj_to_name(kwargs)

    try:
        res = cmds.getAttr(*args, **kwargs)
    except Exception as e:
        raise exception.MayaAttributeError(*e.args)

    if isinstance(res, list) and len(res) > 0:
        at = cmds.getAttr(args[0], type=True)
        if isinstance(res[0], tuple):
            if at == "pointArray":
                return [datatypes.Vector(x) for x in res]
            elif at == "vectorArray":
                return [datatypes.Point(x) for x in res]

            if at.endswith("3"):
                return datatypes.Vector(res[0])

            return res[0]
        else:
            if at == "vectorArray":
                return [datatypes.Vector(res[i], res[i + 1], res[i + 2]) for i in range(0, len(res), 3)]
            elif at == "matrix":
                return datatypes.Matrix(res)

            return res

    return res


def setAttr(*args, **kwargs):
    args = _dt_to_value(_obj_to_name(args))
    kwargs = _obj_to_name(kwargs)

    try:
        fargs = []
        for arg in args:
            if isinstance(arg, (list, set, tuple)):
                fargs.extend(arg)
            else:
                fargs.append(arg)

        cmds.setAttr(*fargs, **kwargs)
    except Exception as e:
        raise exception.MayaAttributeError(*e.args)


local_dict = locals()

for n, func in inspect.getmembers(cmds, callable):
    if n not in local_dict:
        local_dict[n] = _pymaya_cmd_wrap(func,
                                        wrap_object=(n not in __DO_NOT_CAST_FUNCS),
                                        scope=SCOPE_ATTR if n in __SCOPE_ATTR_FUNCS else SCOPE_NODE)
    __all__.append(n)
