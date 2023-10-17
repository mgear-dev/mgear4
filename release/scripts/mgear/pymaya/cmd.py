from . import base
from . import exception
from maya import cmds
import functools
import inspect


__ALL__ = []
__DO_NOT_CAST_FUNCS = ("getAttr", )
__SCOPE_ATTR_FUNCS = ("listAttr", )


SCOPE_ATTR = 0
SCOPE_NODE = 1
Callback = functools.partial
__ALL__.append("Callback")


def _obj_to_name(arg):
    if isinstance(arg, (list, set, tuple)):
        return arg.__class__([_obj_to_name(x) for x in arg])
    elif isinstance(arg, base.Base):
        return arg.name()
    else:
        return arg


def _name_to_obj(arg, scope=SCOPE_NODE, known_node=None):
    # lazy importing
    from . import node
    from . import attr

    if isinstance(arg, (list, set, tuple)):
        return arg.__class__([_name_to_obj(x, scope=scope, known_node=known_node) for x in arg])

    elif isinstance(arg, str):
        if (scope == SCOPE_ATTR and known_node is not None):
            try:
                return attr.PyAttr(f"{known_node}.{arg}")
            except:
                return arg
        elif "." in arg:
            try:
                return attr.PyAttr(arg)
            except:
                return arg
        else:
            try:
                return node.PyNode(arg)
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


local_dict = locals()

for n, func in inspect.getmembers(cmds, callable):
    local_dict[n] = _pymaya_cmd_wrap(func,
                                     wrap_object=(n not in __DO_NOT_CAST_FUNCS),
                                     scope=SCOPE_ATTR if n in __SCOPE_ATTR_FUNCS else SCOPE_NODE)
    __ALL__.append(n)
