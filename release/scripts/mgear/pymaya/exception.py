class MayaAttributeError(Exception):
    pass


class MayaNodeError(RuntimeError, TypeError):
    """A node does not exist or can not be found.

    Subclasses RuntimeError and TypeError so callers catching the PyMEL-style
    ``pm.MayaNodeError``, a plain ``RuntimeError`` or the ``TypeError`` that
    PyMEL's MayaNodeError derives from all work.
    """

    pass


class MayaGeometryError(Exception):
    pass
