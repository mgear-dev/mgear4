from . import base
from maya import cmds
import inspect


__ALL__ = []


def _obj_to_name(arg):
    if isinstance(arg, (list, set, tuple)):
        return arg.__class__([_obj_to_name(x) for x in arg])
    elif isinstance(arg, base.Base):
        return arg.name()
    else:
        return arg


def _name_to_obj(arg):
    # lazy importing
    from . import node
    from . import attr

    if isinstance(arg, (list, set, tuple)):
        return arg.__class__([_name_to_obj(x) for x in arg])
    elif isinstance(arg, str):
        if "." in arg:
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


def _pymaya_cmd_wrap(func):
    def wrapper(*args, **kwargs):
        nargs = _obj_to_name(args)
        nkwargs = {}
        for k, v in kwargs.items():
            nkwargs[k] = _obj_to_name(v)

        # TODO
        # return _name_to_obj(func(*nargs, **nkwargs))
        return func(*nargs, **nkwargs)

    return wrapper


local_dict = locals()

for n, func in inspect.getmembers(cmds, callable):
    local_dict[n] = _pymaya_cmd_wrap(func)
    __ALL__.append(n)
