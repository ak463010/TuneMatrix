import os
import unittest
from unittest.mock import patch

import main


class MainEntryPointTests(unittest.TestCase):
    def test_prepare_argv_removes_smoke_test_flag(self):
        argv, smoke_test = main._prepare_argv(["main.py", "--smoke-test", "--other"])

        self.assertEqual(argv, ["main.py", "--other"])
        self.assertTrue(smoke_test)

    def test_prepare_argv_uses_smoke_test_environment_flag(self):
        with patch.dict(os.environ, {"TUNEMATRIX_SMOKE_TEST": "true"}):
            argv, smoke_test = main._prepare_argv(["main.py"])

        self.assertEqual(argv, ["main.py"])
        self.assertTrue(smoke_test)


if __name__ == "__main__":
    unittest.main()
