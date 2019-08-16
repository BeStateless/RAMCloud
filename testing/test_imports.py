import __init__

import ramcloud
import unittest

class TestImports(unittest.TestCase):
    def test_get_key(self):
        key = ramcloud.get_key(27)
        self.assertEqual(key, "27")

    def test_get_key_length(self):
        length = ramcloud.get_keyLength(27)
        self.assertEqual(length, 2)

if __name__ == '__main__':
    unittest.main()
