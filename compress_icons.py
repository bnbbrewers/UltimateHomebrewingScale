"""
Icon Compression Script for M5Stack Dial
Compresses PNG icons to reduce memory usage
"""
import os
from PIL import Image

# Configuration
ICON_DIR = "assets/icons"
TARGET_SIZE = 58  # Icon size 58x58 to match launcher config
OPTIMIZE = True
QUALITY = 85

def compress_icon(input_path, output_path, size):
    """Compress and resize a PNG icon"""
    try:
        # Open image
        img = Image.open(input_path)
        
        # Convert to RGBA if not already
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Resize with high-quality resampling
        img_resized = img.resize((size, size), Image.Resampling.LANCZOS)
        
        # Save with optimization
        img_resized.save(
            output_path,
            'PNG',
            optimize=OPTIMIZE,
            compress_level=9  # Maximum PNG compression
        )
        
        # Get file sizes
        input_size = os.path.getsize(input_path)
        output_size = os.path.getsize(output_path)
        reduction = ((input_size - output_size) / input_size) * 100
        
        print(f"✓ {os.path.basename(input_path)}: {input_size}B → {output_size}B ({reduction:.1f}% reduction)")
        
    except Exception as e:
        print(f"✗ Error processing {input_path}: {e}")

def main():
    """Compress all icons in the directory"""
    print(f"Compressing icons in {ICON_DIR}/")
    print(f"Target size: {TARGET_SIZE}x{TARGET_SIZE}px")
    print("=" * 60)
    
    # Create backup directory
    backup_dir = os.path.join(ICON_DIR, "original")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Process all PNG files
    icon_files = [f for f in os.listdir(ICON_DIR) if f.endswith('.png')]
    
    if not icon_files:
        print("No PNG files found!")
        return
    
    for filename in icon_files:
        input_path = os.path.join(ICON_DIR, filename)
        backup_path = os.path.join(backup_dir, filename)
        
        # Backup original
        if not os.path.exists(backup_path):
            import shutil
            shutil.copy2(input_path, backup_path)
        
        # Compress
        compress_icon(input_path, input_path, TARGET_SIZE)
    
    print("=" * 60)
    print(f"✓ Compression complete! Originals backed up to {backup_dir}/")
    print(f"\nUpdate launcher_config.py with icon_size = {TARGET_SIZE}")

if __name__ == "__main__":
    main()
