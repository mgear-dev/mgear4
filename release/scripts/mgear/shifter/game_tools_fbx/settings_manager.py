import json

from mgear.core import widgets
from mgear.shifter.game_tools_fbx import fbx_export_node


EXPORT_NODE_NAME = "mgearFbxExportNode"


class ExporterSettingsManager(widgets.WidgetSettingsManager):
    PARTITIONS = "partitions"
    ANIM_CLIPS = "anim_clips"

    def __init__(self, ui_name, parent=None):
        super(ExporterSettingsManager, self).__init__(ui_name, parent)

    def save_ui_state(self, widget_dict):
        super(ExporterSettingsManager, self).save_ui_state(widget_dict)
        export_node = fbx_export_node.FbxExportNode.get()
        if not export_node:
            return

        partitions = export_node.get_partitions()
        if partitions:
            self.settings.setValue(self.PARTITIONS, str(partitions))
        anim_clips = export_node.parse_export_data().get(self.ANIM_CLIPS, {})
        if anim_clips:
            self.settings.setValue(self.ANIM_CLIPS, str(anim_clips))

    def load_ui_state(self, widget_dict, reset=False):
        super(ExporterSettingsManager, self).load_ui_state(widget_dict, reset)
        export_node = fbx_export_node.FbxExportNode.get()
        if not export_node:
            return

        partitions = self.settings.value(self.PARTITIONS)
        if partitions and not reset:
            partitions = json.dumps(partitions)
            export_node.add_attribute(self.PARTITIONS, partitions)
        partitions_outliner = widget_dict[self.PARTITIONS]
        partitions_outliner.reset_contents()

        anim_clips = self.settings.value(self.ANIM_CLIPS)
        if anim_clips and not reset:
            anim_clips = json.dumps(anim_clips)
            export_node.add_attribute(self.ANIM_CLIPS, anim_clips)
        anim_clips_listwidget = widget_dict[self.ANIM_CLIPS]
        anim_clips_listwidget.refresh()
