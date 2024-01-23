import re
from . import base


def __find_attr(name):
    from . import node
    from . import attr

    nspts = re.split("[.]", name)
    cur = node.BindNode(nspts[0])
    for n in nspts[1:]:
        res = re.search("([^[]+)\[?([0-9]+)?\]?", n)
        if not res:
            raise Exception("Unexpected name")

        an, ai = res.groups()
        cur = getattr(cur, an)
        if ai is not None:
            i = int(ai)
            cur = cur.__getitem__(i)

    return cur


def PyNode(name_or_node):
    from . import node
    from . import attr
    from . import geometry

    if isinstance(name_or_node, base.Base):
        return name_or_node

    if "." in name_or_node:
        try:
            return __find_attr(name_or_node)
        except:
            bound = geometry.BindGeometry(name_or_node, silent=True)
            if bound:
                return bound
            else:
                raise
    else:
        return node.BindNode(name_or_node)
