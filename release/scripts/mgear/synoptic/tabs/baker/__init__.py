from mgear.synoptic.tabs import MainSynopticTab

from . import widget


##################################################
# SYNOPTIC TAB WIDGET
##################################################


class SynopticTab(MainSynopticTab, widget.Ui_baker):

    description = "baker"
    name = "baker"

    # ============================================
    # INIT
    def __init__(self, parent=None):
        super(SynopticTab, self).__init__(self, parent)
