# except translate
STR_FUNCS = ["capitalize", "casefold", "center", "count", "encode", "endswith", "expandtabs", "find", "format", "format_map", "index", "isalnum", "isalpha", "isascii", "isdecimal", "isdigit", "islower", "isnumeric", "isprintable", "isspace", "istitle", "isupper", "join", "ljust", "lower", "lstrip", "maketrans", "partition", "replace", "rfind", "rindex", "rjust", "rpartition", "rsplit", "rstrip", "split", "splitlines", "startswith", "strip", "swapcase", "title", "upper", "zfill", "__add__", "__contains__", "__format__", "__ge__", "__gt__", "__le__", "__len__", "__lt__", "__mod__", "__mul__", "__ne__", "__rmod__", "__rmul__", "__sizeof__"]


def _wrap_str_funcs(base, funcname):
    def wrapper(*args, **kwargs):
        return getattr(base.name(), funcname)(*args, **kwargs)

    return wrapper


class Base(object):
    def __init__(self, *args, **kwargs):
        super(Base, self).__init__()
        for sf in STR_FUNCS:
            setattr(self, sf, _wrap_str_funcs(self, sf))

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
