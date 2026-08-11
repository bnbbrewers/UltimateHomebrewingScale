import unittest

from updater import boot


class BlobNvs:
    def __init__(self, value=b"0"):
        self.value = bytes(value)
        self.committed = False

    def get_blob(self, key, buffer):
        size = min(len(self.value), len(buffer))
        buffer[:size] = self.value[:size]
        return size

    def set_blob(self, key, value):
        self.value = str(value).encode("utf-8")

    def commit(self):
        self.committed = True


class BootUpdateFlagTests(unittest.TestCase):
    def test_blob_nvs_flag_is_detected_before_full_runtime_load(self):
        self.assertTrue(boot.is_update_requested(BlobNvs(b"1")))
        self.assertFalse(boot.is_update_requested(BlobNvs(b"0")))

    def test_blob_nvs_flag_can_be_cleared_after_update(self):
        nvs = BlobNvs(b"1")

        boot.set_update_requested(False, nvs=nvs)

        self.assertEqual(nvs.value, b"0")
        self.assertTrue(nvs.committed)


if __name__ == "__main__":
    unittest.main()
