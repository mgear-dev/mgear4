import unittest


class TestCmd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        import os
        from maya import standalone
        standalone.initialize()

        from maya import cmds
        cls.cmds = cmds

        mpath = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if mpath not in sys.path:
            sys.path.append(mpath)

        import pymaya
        cls.pm = pymaya

    def setUp(self):
        self.cmds.file(new=True, f=True)

    def test_undochunk(self):
        sc = self.pm.undoInfo(q=1)
        self.pm.createNode("transform")
        self.pm.createNode("transform")
        self.pm.createNode("transform")
        self.pm.createNode("transform")
        self.pm.createNode("transform")
        self.assertEqual(self.pm.undoInfo(q=1) - sc, 5)

        sc = self.pm.undoInfo(q=1)
        with self.pm.UndoChunk():
            self.pm.createNode("transform")
            self.pm.createNode("transform")
            self.pm.createNode("transform")
            self.pm.createNode("transform")
            self.pm.createNode("transform")
        self.assertEqual(self.pm.undoInfo(q=1) - sc, 1)
