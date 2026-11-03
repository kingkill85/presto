import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('scumm_files',
    Path(__file__).resolve().parents[1] / 'device/lib/scumm_files.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ScummFileTests(unittest.TestCase):
    def test_random_access_and_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'fixture.bin'
            path.write_bytes(bytes(range(256)) * 32)
            session = module.ReadSession()
            handle = session(0, str(path), None)
            self.assertGreater(handle, 0)
            self.assertEqual(session(4, handle, None), 8192)
            self.assertEqual(session(5, handle, 255), 0)
            block = bytearray(3)
            self.assertEqual(session(2, handle, block), 3)
            self.assertEqual(block, b'\xff\x00\x01')
            self.assertEqual(session(3, handle, None), 258)
            self.assertEqual(session(5, handle, 8192), 0)
            self.assertEqual(session(2, handle, block), 0)
            file = session.files[handle][0]
            session.close()
            self.assertTrue(file.closed)
            self.assertEqual(session(2, handle, block), -1)
            session.close()

    def test_missing_file_and_independent_handles(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'fixture.bin'
            session = module.ReadSession()
            self.assertEqual(session(0, str(path), None), 0)
            self.assertFalse(session.files)
            path.write_bytes(b'1234')
            a = session(0, str(path), None)
            b = session(0, str(path), None)
            self.assertNotEqual(a, b)
            session(5, a, 3)
            self.assertEqual(session(3, b, None), 0)
            self.assertEqual(session(1, a, None), 0)
            self.assertEqual(session(3, b, None), 0)
            session.close()


if __name__ == '__main__':
    unittest.main()
