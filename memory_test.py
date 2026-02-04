"""
Memory Diagnostic for M5Stack Dial
Check available memory before and after loading images
"""
import gc
import M5
from M5 import *
import m5ui

def print_memory():
    """Print memory stats"""
    gc.collect()
    free = gc.mem_free()
    allocated = gc.mem_alloc()
    total = free + allocated
    print(f"Memory: {free:,} bytes free / {total:,} total ({(free/total)*100:.1f}% free)")

# Initialize
M5.begin()
m5ui.init()
gc.collect()

print("=" * 50)
print("M5Stack Dial Memory Test")
print("=" * 50)

print("\n1. After M5 init:")
print_memory()

print("\n2. Creating page:")
page = m5ui.M5Page(bg_c=0x000000)
print_memory()

print("\n3. Creating first image:")
try:
    img1 = m5ui.M5Image('/flash/assets/icons/Home.png', x=50, y=50, parent=page)
    img1.set_size(32, 32)
    print("✓ Image 1 loaded")
    print_memory()
except Exception as e:
    print(f"✗ Error: {e}")

print("\n4. Creating second image:")
try:
    img2 = m5ui.M5Image('/flash/assets/icons/Scale.png', x=100, y=50, parent=page)
    img2.set_size(32, 32)
    print("✓ Image 2 loaded")
    print_memory()
except Exception as e:
    print(f"✗ Error: {e}")

print("\n5. Creating third image:")
try:
    img3 = m5ui.M5Image('/flash/assets/icons/Malt.png', x=150, y=50, parent=page)
    img3.set_size(32, 32)
    print("✓ Image 3 loaded")
    print_memory()
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 50)
print("Test complete!")
print("=" * 50)
