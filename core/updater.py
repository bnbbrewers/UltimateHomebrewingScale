"""Compatibility facade for the updater package."""

from updater.github_release import (
    GITHUB_API_BASE,
    MANIFEST_ASSET_NAME,
    REPO_NAME,
    REPO_OWNER,
    asset_download_url as _asset_download_url,
    download_manifest,
    github_api_get_json as _github_api_get_json,
    latest_release_url,
    release_info as _release_info,
    releases_url,
    resolve_release,
)
from updater.workflow import update
from updater.http_client import (
    REQUEST_TIMEOUT_S,
    default_requests_module as _default_requests_module,
    get as _request_get,
    response_header as _response_header,
    response_text as _response_text,
)
