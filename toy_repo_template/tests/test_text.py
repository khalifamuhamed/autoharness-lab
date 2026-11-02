import unittest

from slugkit import slugify


class SlugifyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_collapses_separators(self):
        self.assertEqual(slugify("a  --  b"), "a-b")

    def test_unicode(self):
        self.assertEqual(slugify("Crème Brûlée"), "creme-brulee")


if __name__ == "__main__":
    unittest.main()
