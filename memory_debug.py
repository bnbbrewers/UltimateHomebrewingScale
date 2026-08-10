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


def lvgl_memory_stats():
    """Best-effort LVGL allocator stats when the firmware exposes them."""
    try:
        import lvgl as lv
        monitor = getattr(lv, "mem_monitor", None)
        if monitor is None:
            return None
        result = monitor()
        if result is None:
            return None

        def value(name):
            if isinstance(result, dict):
                return result.get(name)
            return getattr(result, name, None)

        free_size = value("free_size")
        biggest = value("free_biggest_size")
        fragmentation = value("frag_pct")
        if free_size is None or biggest is None or fragmentation is None:
            return None
        return int(free_size), int(biggest), int(fragmentation)
    except Exception:
        return None


def snapshot(tag, enabled=False, collect=False, verbose=False):
    """
    Print a memory snapshot if enabled.

    Args:
        tag: Short label for the snapshot.
        enabled: Usually config.DEBUG.
        collect: Collect the Python heap before measuring when true.
        verbose: Best-effort MicroPython allocator dump, disabled by default.
    """
    if not enabled:
        return

    py_free, c_free, c_largest = stats(collect=collect)
    lvgl_stats = lvgl_memory_stats()

    if verbose:
        try:
            import micropython
            micropython.mem_info(1)
        except Exception:
            pass

    if c_free is None:
        print("[MEM] {} py_free={}".format(tag, py_free))
        return
    message = "[MEM] {} py_free={} c_free={} c_largest={}".format(
        tag, py_free, c_free, c_largest
    )
    if lvgl_stats is not None:
        message += " lv_free={} lv_largest={} lv_frag={}%".format(
            lvgl_stats[0], lvgl_stats[1], lvgl_stats[2]
        )
    print(message)
