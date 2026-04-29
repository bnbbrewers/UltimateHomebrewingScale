"""
English translations for Ultimate Homebrewing Scale
"""

TRANSLATIONS = {
    'common': {
        'ok': 'OK',
    },

    'scale': {
        'title': 'Scale',
        'tare_ready': 'Press to tare',
        'taring': 'Taring...',
        'tare_done': 'Tare done!',
        'tare_error': 'Tare error',
    },

    'scale_calibration': {
        'intro_message_line1': 'Connect your scale',
        'intro_message_line2': 'OK to continue',
        'title': 'Scale Calibration',
        'step': 'Step {0}/{1} - {2}g',
        'adjust_target_hint_line1': 'Turn',
        'adjust_target_hint_line2': 'to adjust target weight',
        'start_button': 'Start',
        'target': '{0} g',
        'measuring_label': 'Measuring',
        'measuring_progress': '{0}/{1}s',
        'average': 'Avg: {0}',
        'complete': 'Calibration complete',
        'data_saved': 'Data saved',
        'complete_saved_line1': 'Calibration complete!',
        'complete_saved_line2': 'Data saved',
        'restart_after_success': 'Calibration complete, OK to restart',
        'restart_after_save_error': 'Calibration file save error',
        'done': 'Done',
        'error': 'Error',
        'scale_not_found': 'Scale not found',
        'save_error': 'Save error: {0}',
    },

    'recipe': {
        'select_recipe': 'Select a recipe',
        'no_recipe': 'No recipe found',
        'loading_recipes': 'Loading recipes...',
    },

    'grain': {
        'title': 'Grain',
        'select_malt': 'Select a malt',
        'no_malts': 'No malts found',
        'loading_grains': 'Loading grains...',
        'all_malts_done': 'All malts weighed!',
    },

    'hop': {
        'title': 'Hop',
        'prepare_recipients': 'Prepare {0} container(s) for hop additions',
        'no_hops': 'No hops found',
        'loading_hops': 'Loading hops...',
        'step_line': '{0} ({1}g)',
        'select_hop': 'Select a hop',
        'hop_weighed': '{0} weighed',
        'all_hops_weighed': 'All hops weighed!',
    },

    'keg': {
        'title': 'Keg Filler',
    },

    'settings': {
        'title': 'Settings',
        'language': 'Language',
        'calibration': 'Calibration',
        'about': 'About',
        'portal_connect_sta': 'Scan the QR code to open setup',
        'portal_connect_ap': 'Join the Dial Wi-Fi, then scan the QR code',
        'portal_error': 'Portal error, check network',
    },

    'launcher': {
        'scale': 'Scale',
        'malt': 'Malt',
        'hop': 'Hop',
        'keg': 'Keg',
        'settings': 'Settings',
    },

    'portal': {
        'title': 'Ultimate Homebrewing Scale setup',
        'ap': 'AP',
        'saved': 'Saved',
        'invalid_fields': 'Invalid fields',
        'save_reboot': 'Save and reboot',
        'saved_rebooting': 'Saved. Rebooting...',
        'saved_manual_reboot': 'Saved. Please reboot manually.',
        'forbidden': 'Forbidden',
        'not_found': 'Not found',
        'internal_error': 'Internal error',
        'fields': {
            'LANGUAGE': 'Language',
            'GRAIN_WEIGHT_TOLERANCE': 'Grain tolerance (g)',
            'DEBUG': 'Debug mode',
            'WIFI_SSID': 'Wi-Fi SSID',
            'WIFI_PASSWORD': 'Wi-Fi password',
            'BREWFATHER_USER_ID': 'Brewfather user id',
            'BREWFATHER_API_KEY': 'Brewfather API key',
            'BREWING_SOFTWARE': 'Brewing software',
        },
        'choices': {
            'language_en': 'English',
            'language_fr': 'French',
        },
        'validation': {
            'invalid_boolean': 'invalid boolean',
            'invalid_integer': 'invalid integer',
            'below_minimum': 'below minimum',
            'above_maximum': 'above maximum',
            'invalid_value': 'invalid value',
            'too_long': 'too long',
            'unsupported_type': 'unsupported type',
            'nvs_write_failed': 'NVS write failed: {0}',
        },
    },
}
