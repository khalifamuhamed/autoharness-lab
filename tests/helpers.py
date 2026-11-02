import tempfile
import unittest
from pathlib import Path

from autoharness_lab import sample
from autoharness_lab.store import Store


class SampleStoreCase(unittest.TestCase):
    """Each test gets a fresh, throw-away SAMPLE store (never the runtime/ one)."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.project = sample.build(self.tmp / "project")
        self.store = Store(self.project)
