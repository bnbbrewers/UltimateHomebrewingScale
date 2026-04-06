"""
Memory debug helpers for MicroPython on ESP32/UIFlow2.

When DEBUG is enabled, these helpers print both:
- Python heap free bytes (gc.mem_free)
- ESP-IDF C heap stats when available (total free + largest free block)
"""

import gc


def _py_heap_free():
    try:
        return gc.mem_free()
    except Exception:
        return -1


def _c_heap_stats():
    """
    Returns (total_free, largest_free) for ESP-IDF HEAP_DATA when available.
    Falls back to (None, None) if unsupported on the running firmware.
    """
    try:
        import esp32
        cap = getattr(esp32, "HEAP_DATA", None)
        if cap is None:
            return None, None

        regions = esp32.idf_heap_info(cap)
        if not regions:
            return None, None

        total_free = 0
        largest_free = 0
        for region in regions:
            if not isinstance(region, tuple) or len(region) < 2:
                continue
            free_bytes = int(region[1])
            total_free += free_bytes
            if len(region) >= 3:
                largest = int(region[2])
                if largest > largest_free:
                    largest_free = largest

        return total_free, largest_free
    except Exception:
        return None, None


def stats(collect=False):
    """
    Return memory stats as a tuple:
    (py_free, c_free, c_largest)
    """
    if collect:
        gc.collect()
    py_free = _py_heap_free()
    c_free, c_largest = _c_heap_stats()
    return py_free, c_free, c_largest


def snapshot(tag, enabled=False, collect=False):
    """
    Print a memory snapshot if enabled.

    Args:
        tag: Short label for the snapshot.
        enabled: Usually config.DEBUG.
        collect: Run gc.collect() before taking the snapshot.
    """
    if not enabled:
        return

    py_free, c_free, c_largest = stats(collect=collect)

    if c_free is None:
        print("[MEM] {} py_free={}".format(tag, py_free))
        return
    print(
        "[MEM] {} py_free={} c_free={} c_largest={}".format(
            tag, py_free, c_free, c_largest
        )
    )
