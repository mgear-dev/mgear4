def PyNode(name):
    from . import node
    from . import attr
    from . import geometry

    if "." in name:
        try:
            return attr.Attribute(name)
        except:
            bound = geometry.BindGeometry(name, silent=True)
            if bound:
                return bound
            else:
                raise
    else:
        return node.BindNode(name)
