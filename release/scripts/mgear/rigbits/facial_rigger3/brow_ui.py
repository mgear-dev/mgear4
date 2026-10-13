"""Brow Rigger 3.0 tab of the Facial Rigger window."""

from mgear.vendor.Qt import QtWidgets

from mgear.core.facial import brow_schema

from . import brow
from .rigger_tab import RiggerTab


class BrowRiggerTab(RiggerTab):
    """Settings form and actions of Brow Rigger 3.0.

    Check Detection selects the first brow end found from the path: the
    inner end of a left or right brow, the right end of a center brow.

    Args:
        parent (QtWidgets.QWidget, optional): Parent widget.
    """

    def __init__(self, parent=None):
        super(BrowRiggerTab, self).__init__(brow_schema, brow, "Brow", parent)

    def create_extra_buttons(self):
        """Create the Check Detection button."""
        button = QtWidgets.QPushButton("Check Detection")
        button.setToolTip(
            "Select the inner end of the brow found from the path (the right "
            "end of a center brow), and report the side."
        )
        button.clicked.connect(self.check_detection)
        return [button]

    def check_detection(self):
        """Select the first brow end found from the path."""
        return brow.check_detection(**self.form.get_settings())
