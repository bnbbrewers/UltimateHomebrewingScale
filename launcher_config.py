"""
Launcher Configuration for Ultimate Homebrewing Scale
Configure menu items: label, icon path, and order
"""

# Menu Items Configuration
LAUNCHER_ITEMS = [
    {
        'label': 'Home',
        'icon': '/flash/assets/icons/Home.png',
        'module': 'scale',
        'order': 0,
    },
    {
        'label': 'Scale',
        'icon': '/flash/assets/icons/Scale.png',
        'module': 'scale',
        'order': 1,
    },
    {
        'label': 'Malt',
        'icon': '/flash/assets/icons/Malt.png',
        'module': 'grain_assistant',
        'order': 2,
    },
    {
        'label': 'Hop',
        'icon': '/flash/assets/icons/Hop.png',
        'module': 'hop_assistant',
        'order': 3,
    },
    {
        'label': 'Keg',
        'icon': '/flash/assets/icons/Keg.png',
        'module': 'keg_filler',
        'order': 4,
    },
    {
        'label': 'Settings',
        'icon': '/flash/assets/icons/Parameters.png',
        'module': 'settings',
        'order': 5,
    },
]

# Launcher Visual Settings
LAUNCHER_CONFIG = {
    # Icon settings
    'icon_size': 58,                # Icon size in pixels (58x58 - all icons same size)
    'icon_radius': 90,              # Distance from center to place icons (adjusted for larger icons)
    'touch_radius': 64,             # Touch detection radius (slightly larger)
    
    # Arc positioning (for icons on left side)
    'arc_start_angle': 105,          # Start angle in degrees
    'arc_total_angle': 135,         # Total arc span in degrees (135 = more spacing)
    
    # Colors (RGB565 or hex)
    'bg_color': 0x000000,           # Background (black)
    'icon_normal': 0xFFFFFF,        # Icon tint when not selected (white)
    'icon_selected': 0x00A8E8,      # Icon tint when selected (blue)
    'label_color': 0xFFFFFF,        # Center label color (white)
    'selection_color': 0x00A8E8,    # Selection highlight color (blue)
    
    # Label settings
    'label_font_size': 96,          # Font size for label (3x larger)
    'label_y_offset': 0,            # Y offset from center (0 = centered)
    'label_x_position': 60,         # X position from left edge (60px from left)
    
    # Animation
    'enable_animation': True,       # Smooth rotation animation
    'animation_speed': 200,         # Animation duration in ms
    
    # Behavior
    'encoder_sensitivity': 1,       # Encoder steps per menu item (1 or 2)
    'button_hold_time': 500,        # Long press duration in ms
    'auto_return': False,           # Auto return to launcher after app exit
}

# Screen settings (M5Dial specific)
SCREEN_CONFIG = {
    'width': 240,
    'height': 240,
    'center_x': 120,
    'center_y': 120,
}
