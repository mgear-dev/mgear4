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
        import pymaya.attr
        cls.pm = pymaya
        cls.pattr = pymaya.attr
        cls.os = os

    def setUp(self):
        self.cmds.file(new=True, f=True)

    def test_return_pyobject(self):
        n = self.pm.createNode("transform", n="test1")
        self.assertIsNotNone(n)
        self.assertTrue(isinstance(n, self.pm.nt.Transform))
        self.assertTrue(isinstance(self.pm.listAttr("test1")[0], self.pattr.Attribute))

    def test_pyobject_arg(self):
        n = self.pm.createNode("transform", n="test1")
        self.assertEqual(n.name(), "test1")
        self.pm.rename(n, "test2")
        self.assertEqual(n.name(), "test2")
        n2 = self.pm.createNode("transform", n="test1")
        self.pm.parent(n, n2)
        self.assertEqual(n.dagPath().fullPathName(), "|test1|test2")
        self.assertEqual(self.pm.getAttr(n.tx), 0)
        self.pm.setAttr(n.tx, 10)
        self.assertEqual(self.pm.getAttr(n.tx), 10)

        self.pm.addAttr(n, ln="testtest", dt="string")
        self.pm.setAttr(n.testtest, "aaa", type="string")
        self.assertEqual(self.pm.getAttr(n.testtest), "aaa")

    def test_original_commands(self):
        self.pm.displayInfo("TEST DISPLAY")
        self.pm.displayWarning("TEST WARNING")
        self.pm.displayError("TEST ERROR")

        self.pm.createNode("transform", n="test")
        self.pm.select("test")
        testma = self.os.path.join(self.os.path.dirname(__file__), "exportest.ma")
        self.pm.exportSelected(testma, f=True, type="mayaAscii")
        self.assertTrue(self.os.path.isfile(testma))
        self.os.remove(testma)
        self.assertFalse(self.os.path.isfile(testma))

        self.pm.mel.eval("createNode -n \"test2\" \"transform\"")
        self.assertIsNotNone(self.pm.PyNode("test2"))

        sphere = self.pm.polySphere()[0]
        self.assertTrue(self.pm.hasAttr(sphere, "v"))
        self.assertTrue(self.pm.hasAttr(sphere, "inMesh", checkShape=True))
        self.assertFalse(self.pm.hasAttr(sphere, "inMesh", checkShape=False))

        self.pm.select(sphere)
        self.assertEqual(self.pm.selected(), [sphere])
        self.pm.select(cl=True)
        self.assertEqual(self.pm.selected(), [])

        self.cmds.file(new=True, f=True)
        self.pm.createNode("transform", n="test")
        self.pm.select("test")
        testma = self.os.path.join(self.os.path.dirname(__file__), "exportest.ma")
        self.pm.exportSelected(testma, f=True, type="mayaAscii")
        imported = self.pm.importFile(testma, ns="testfile", rnn=True)
        self.assertEqual([x.name() for x in imported], ["testfile:test"])
        self.os.remove(testma)
