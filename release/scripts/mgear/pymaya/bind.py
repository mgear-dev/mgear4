def PyNode(name):
    from . import node
    from . import attr
    from . import geometry

    if "." in name:
        bound = geometry.BindGeometry(name)
        if bound:
            return bound

        return attr.Attribute(name)

    else:
        return node.BindNode(name)
