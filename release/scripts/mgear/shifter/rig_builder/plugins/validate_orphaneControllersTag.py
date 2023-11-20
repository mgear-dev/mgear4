import pyblish.api
import pymel.core as pm

# from pyblish_shifter.actions import RepairAction


class delteOrphaneTags(pyblish.api.Action):
    """delete tags"""

    label = "Delete Orphane Controller Tags"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Ico

    def process(self, context, plugin):
        """select"""
        pm.delete(plugin.tags)


class selectOrphaneTags(pyblish.api.Action):
    """delete tags"""

    label = "Select Orphane Controller Tags"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Ico

    def process(self, context, plugin):
        """select"""
        pm.select(plugin.tags)


class validateOrphaneControllerTags(pyblish.api.Validator):
    """Test Validate Rig information"""

    families = ["rig"]
    actions = [selectOrphaneTags, delteOrphaneTags]
    optional = True
    label = "Validator - Orphane controller tag"

    @classmethod
    def getOrphaneTags(self, instance):
        self.tags = []
        for t in pm.ls(et="controller"):
            if not t.controllerObject.connections():
                self.tags.append(t)
        return self.tags

    def process(self, instance):
        """Process all the nodes in the instance"""
        check = True

        if self.getOrphaneTags(instance):
            check = False

        assert (
            check
        ), " {} are orphane without Control Object input. Please delete it".format(
            self.tags
        )
