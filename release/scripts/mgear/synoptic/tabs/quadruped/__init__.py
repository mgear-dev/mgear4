from mgear.synoptic.tabs import MainSynopticTab

from . import widget


##################################################
# SYNOPTIC TAB WIDGET
##################################################


class SynopticTab(MainSynopticTab, widget.Ui_biped_body):

    description = "biped body"
    name = "biped_body"

    # ============================================
    # INIT
    def __init__(self, parent=None):
        super(SynopticTab, self).__init__(self, parent)
        self.cbManager.selectionChangedCB(self.name, self.selectChanged)
