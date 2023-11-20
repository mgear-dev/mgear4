import pyblish.api
import pymel.core as pm
import pyblish_shifter.actions as act


class RebuildDagPose(pyblish.api.Action):
    """Rebuild the dagPose for the rig"""

    label = "Rebuild dagPose"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Icon

    def process(self, context, plugin):
        """select"""
        errored_instances = act._get_errored_instances_from_context(context)[0]
        rigNode = pm.PyNode(errored_instances)
        pm.delete(plugin.dp)
        pm.select(plugin.controllersGrp, r=True)
        node = pm.dagPose(save=True, selection=True)
        pm.connectAttr(node.message, rigNode.rigPoses[0])


class SelectNotInDagCtl(pyblish.api.Action):
    """Select the controls not in the dagPose"""

    label = "Select not in DagPose Ctl"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Ico

    def process(self, context, plugin):
        """select"""
        pm.select(plugin.nInDagCtl, r=True)


class validateControlsOnDagPose(pyblish.api.Validator):
    """Check if the controls in the dagPose"""

    families = ["rig"]
    actions = [SelectNotInDagCtl, RebuildDagPose]
    optional = True
    label = "Validator - Controllers in dagPose"

    @classmethod
    def getControllersGrp(self, instance):
        """return the controllers grp"""
        node = pm.PyNode(instance)
        sets = node.listConnections(type="objectSet")

        self.controllersGrp = False
        for oSet in sets:
            if "controllers_grp" in oSet.name().lower():
                self.controllersGrp = oSet

        return self.controllersGrp

    @classmethod
    def getDagPose(self, instance):
        """return first dagPose connected to the rig"""
        node = pm.PyNode(instance)
        self.dp = node.listConnections(type="dagPose")[0]

        return self.dp

    @classmethod
    def getCtlNotInDagPose(self, instance):
        """Return the wrong names on the controllers grp set"""
        # check = True
        oSet = self.getControllersGrp(instance)
        dp = self.getDagPose(instance)
        self.nInDagCtl = []
        pdCnx = dp.listConnections()
        for ctl in oSet.members(flatten=True):
            if ctl not in pdCnx:
                self.log.warning("{} not in dagPose".format(ctl.name()))
                self.nInDagCtl.append(ctl)

        return self.nInDagCtl

    def process(self, instance):
        """Process all the nodes in the instance"""

        check = True
        ndpCtl = self.getCtlNotInDagPose(instance)
        if ndpCtl:
            check = False

        assert check, "The Controls: {} should are not in reset position".format(ndpCtl)
