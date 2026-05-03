# -*- coding: utf-8 -*-
"""
Traductions francaises pour Ultimate Homebrewing Scale
"""

TRANSLATIONS = {
    'common': {
        'ok': 'OK',
    },

    'scale': {
        'title': 'Balance',
        'tare_ready': 'Appuyer pour tarer',
        'taring': 'Tarage...',
        'tare_done': 'Tarage effectue !',
        'tare_error': 'Erreur de tarage',
    },

    'scale_calibration': {
        'intro_message_line1': 'Branchez votre balance',
        'intro_message_line2': 'OK pour continuer',
        'title': 'Calibration balance',
        'step': 'Etape {0}/{1} - {2}g',
        'adjust_target_hint_line1': 'Tourner',
        'adjust_target_hint_line2': 'pour ajuster le poids cible',
        'start_button': 'Start',
        'target': '{0} g',
        'measuring_label': 'Mesure',
        'measuring_progress': '{0}/{1}s',
        'average': 'Moy: {0}',
        'complete': 'Calibration terminee',
        'data_saved': 'Donnees sauvees',
        'complete_saved_line1': 'Calibration terminee!',
        'complete_saved_line2': 'Donnees sauvees',
        'restart_after_success': 'Calibration terminée, OK pour redémarrer',
        'restart_after_save_error': 'Erreur de sauvegarde du fichier de calibration',
        'done': 'Termine',
        'error': 'Erreur',
        'scale_not_found': 'Balance introuvable',
        'save_error': 'Erreur sauvegarde: {0}',
    },

    'recipe': {
        'select_recipe': 'Selectionner une recette',
        'no_recipe': 'Pas de recette trouvée',
        'loading_recipes': 'Chargement des recettes...',
    },

    'grain': {
        'title': 'Malt',
        'select_malt': 'Selectionner un malt',
        'no_malts': 'Aucun malt trouve',
        'loading_grains': 'Chargement des grains...',
        'all_malts_done': 'Tous les malts peses !',
    },

    'hop': {
        'title': 'Houblon',
        'prepare_recipients': 'Preparez {0} recipient(s) pour les ajouts de houblon',
        'no_hops': 'Aucun houblon',
        'loading_hops': 'Chargement des houblons...',
        'step_line': '{0} ({1}g)',
        'select_hop': 'Selectionner un houblon',
        'hop_weighed': '{0} : termine',
        'all_hops_weighed': 'Tous les houblons peses !',
    },

    'keg': {
        'title': 'Remplisseur de Futs',
    },

    'settings': {
        'title': 'Parametres',
        'language': 'Langue',
        'calibration': 'Calibration',
        'about': 'A propos',
        'portal_connect_sta': 'Scanner le QR pour ouvrir la config',
        'portal_connect_ap': 'Connectez le tel au Wi-Fi du Dial puis scannez',
        'portal_error': 'Erreur portail, verifier le reseau',
    },

    'updater': {
        'title': 'Mise a jour',
        'ready': 'Preparation...',
        'error': 'Erreur',
        'done_restart': 'installation terminee, OK pour redemarrer',
    },

    'launcher': {
        'scale': 'Balance',
        'malt': 'Malt',
        'hop': 'Houblon',
        'keg': 'Fut',
        'settings': 'Config',
    },

    'portal': {
        'title': 'Configuration Ultimate Homebrewing Scale',
        'ap': 'Point d acces',
        'saved': 'Enregistre',
        'invalid_fields': 'Champs invalides',
        'save_reboot': 'Enregistrer et redemarrer',
        'saved_rebooting': 'Enregistre. Redemarrage...',
        'saved_manual_reboot': 'Enregistre. Redemarrez manuellement.',
        'update_app': 'UPDATE APP',
        'update_rebooting': 'Mise a jour demandee. Redemarrage...',
        'update_request_failed': 'Demande de mise a jour echouee : {0}',
        'forbidden': 'Interdit',
        'not_found': 'Introuvable',
        'internal_error': 'Erreur interne',
        'fields': {
            'LANGUAGE': 'Langue',
            'GRAIN_WEIGHT_TOLERANCE': 'Tolerance malt (g)',
            'DEBUG': 'Mode debug',
            'WIFI_SSID': 'SSID Wi-Fi',
            'WIFI_PASSWORD': 'Mot de passe Wi-Fi',
            'BREWFATHER_USER_ID': 'Identifiant Brewfather',
            'BREWFATHER_API_KEY': 'Cle API Brewfather',
            'BREWING_SOFTWARE': 'Logiciel de brassage',
            'UPDATE_BRANCH': 'Branche de mise a jour',
        },
        'choices': {
            'language_en': 'Anglais',
            'language_fr': 'Francais',
        },
        'validation': {
            'invalid_boolean': 'booleen invalide',
            'invalid_integer': 'entier invalide',
            'below_minimum': 'inferieur au minimum',
            'above_maximum': 'superieur au maximum',
            'invalid_value': 'valeur invalide',
            'too_long': 'trop long',
            'unsupported_type': 'type non pris en charge',
            'nvs_write_failed': 'ecriture NVS echouee : {0}',
        },
    },
}
