class Base(object):
    def __init__(self, *args, **kwargs):
        super(Base, self).__init__()

    def name(self):
        raise NotImplementedError("'name' is not implemented yet")


class Node(Base):
    pass


class Attr(Base):
    pass
