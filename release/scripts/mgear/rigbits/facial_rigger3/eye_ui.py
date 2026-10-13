"""Eye Rigger 3.0 tab of the Facial Rigger window."""

from mgear.core.facial import eyelid_schema

from . import eye
from .rigger_tab import RiggerTab


class EyeRiggerTab(RiggerTab):
    """Settings form and actions of Eye Rigger 3.0.

    Args:
        parent (QtWidgets.QWidget, optional): Parent widget.
    """

    def __init__(self, parent=None):
        super(EyeRiggerTab, self).__init__(eyelid_schema, eye, "Eye", parent)
