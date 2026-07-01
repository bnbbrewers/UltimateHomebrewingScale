"""Updater package.

Keep this package light: boot-time code imports only ``updater.update_app`` first,
then the workflow imports network/release/TAR pieces lazily after Wi-Fi is up.
"""
