from mgear.synoptic.tabs import MainSynopticTab

from . import widget


##################################################
# SYNOPTIC TAB WIDGET
##################################################


class SynopticTab(MainSynopticTab, widget.Ui_baker):

    description = "Control_List"
    name = "Control_List"

    # ============================================
    # INIT
    def __init__(self, parent=None):
        super(SynopticTab, self).__init__(self, parent)
