from mgear.synoptic.tabs import MainSynopticTab

from . import widget


##################################################
# SYNOPTIC TAB WIDGET
##################################################


class SynopticTab(MainSynopticTab, widget.Ui_visibility):

    description = "visibility"
    name = "visibility"

    # ============================================
    # INIT
    def __init__(self, parent=None):
        super(SynopticTab, self).__init__(self, parent)
