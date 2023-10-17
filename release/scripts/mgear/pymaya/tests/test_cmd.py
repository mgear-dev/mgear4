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
        self.assertEqual(n.dag().fullPathName(), "|test1|test2")
        self.assertEqual(self.pm.getAttr(n.tx), 0)
        self.pm.setAttr(n.tx, 10)
        self.assertEqual(self.pm.getAttr(n.tx), 10)

        self.pm.addAttr(n, ln="testtest", dt="string")
        self.pm.setAttr(n.testtest, "aaa", type="string")
        self.assertEqual(self.pm.getAttr(n.testtest), "aaa")
