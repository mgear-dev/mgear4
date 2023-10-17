class Base(object):
    def __init__(self, *args, **kwargs):
        super(Base, self).__init__()

    def name(self):
        raise NotImplementedError("'name' is not implemented yet")

    def __repr__(self):
        return f"{self.__class__.__name__}<'{self.name()}'>"

    def __str__(self):
        return self.__repr__()


class Node(Base):
    pass


class Attr(Base):
    pass


class Geom(Base):
    pass
