"""Lips Rigger 3.0 tab of the Facial Rigger window."""

from mgear.vendor.Qt import QtWidgets

from mgear.core.facial import lips_schema

from . import lips
from .rigger_tab import RiggerTab


class LipsRiggerTab(RiggerTab):
    """Settings form and actions of Lips Rigger 3.0.

    Check Detection selects the upper lip found from the loop, to set
    Invert Upper/Lower before building.

    Args:
        parent (QtWidgets.QWidget, optional): Parent widget.
    """

    def __init__(self, parent=None):
        super(LipsRiggerTab, self).__init__(lips_schema, lips, "Lips", parent)

    def create_extra_buttons(self):
        """Create the Check Detection button."""
        button = QtWidgets.QPushButton("Check Detection")
        button.setToolTip(
            "Select the upper lip found from the loop. Turn on Invert "
            "Upper/Lower when the lower lip is selected."
        )
        button.clicked.connect(self.check_detection)
        return [button]

    def check_detection(self):
        """Select the detected upper lip and corners on the mesh."""
        return lips.check_detection(**self.form.get_settings())
