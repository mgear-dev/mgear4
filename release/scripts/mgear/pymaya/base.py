class Base(object):
    def __init__(self, *args, **kwargs):
        super(Base, self).__init__()

    def name(self):
        raise NotImplementedError("'name' is not implemented yet")

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def __repr__(self):
        return "{}<'{}'>".format(self.__class__.__name__, self.name())

    def __str__(self):
        return self.name()


class Node(Base):
    pass


class Attr(Base):
    pass


class Geom(Base):
    pass
