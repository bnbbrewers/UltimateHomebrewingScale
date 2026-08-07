from . import http_client


REPO_OWNER = "bnbbrewers"
REPO_NAME = "UltimateHomebrewingScale"
GITHUB_API_BASE = "https://api.github.com"
MANIFEST_ASSET_NAME = "uhs-update-manifest.json"
GITHUB_JSON_TMP_PATH = "updater_github.tmp"
MANIFEST_JSON_TMP_PATH = "updater_manifest.tmp"


def _t(i18n, key, fallback):
    if i18n:
        return i18n.t(key)
    return fallback


def latest_release_url():
    return "%s/repos/%s/%s/releases/latest" % (GITHUB_API_BASE, REPO_OWNER, REPO_NAME)


def releases_url(page=None, per_page=None):
    url = "%s/repos/%s/%s/releases" % (GITHUB_API_BASE, REPO_OWNER, REPO_NAME)
    if page is None:
        return url
    return "%s?per_page=%d&page=%d" % (url, int(per_page or 10), int(page))


def release_by_tag_url(tag):
    return "%s/repos/%s/%s/releases/tags/%s" % (
        GITHUB_API_BASE,
        REPO_OWNER,
        REPO_NAME,
        str(tag or "").strip(),
    )


def asset_download_url(release, asset_name=MANIFEST_ASSET_NAME):
    assets = release.get("assets", []) if isinstance(release, dict) else []
    for asset in assets:
        if asset.get("name") == asset_name:
            return asset.get("browser_download_url") or ""
    return ""


def release_info(release, manifest_url):
    return {
        "tag": release.get("tag_name", ""),
        "name": release.get("name", "") or release.get("tag_name", ""),
        "manifest_url": manifest_url,
        "prerelease": bool(release.get("prerelease", False)),
    }


def select_next_release(releases, local_version, manifest_loader):
    """Select the immediate delta after local_version.

    Releases must be ordered newest first. Only manifests along the chain
    from the latest release back to the local version are loaded.
    """
    local = str(local_version or "").strip()
    if not local:
        raise RuntimeError("Local application version is unknown")
    if not releases:
        raise RuntimeError("No matching releases")

    latest = releases[0]
    latest_tag = str(latest.get("tag", "") or "")
    if local == latest_tag:
        return None

    by_tag = {}
    for release in releases:
        tag = str(release.get("tag", "") or "")
        if tag:
            by_tag[tag] = release

    current = latest_tag
    visited = set()
    while current != local:
        if current in visited:
            raise RuntimeError("Update chain contains a cycle at %s" % current)
        visited.add(current)

        release = by_tag.get(current)
        if release is None:
            raise RuntimeError(
                "No update path from %s to %s" % (local, latest_tag)
            )
        manifest = manifest_loader(release.get("manifest_url", ""))
        if not isinstance(manifest, dict):
            raise RuntimeError("Invalid update manifest for %s" % current)
        version = str(manifest.get("version", "") or "")
        if version and version != current:
            raise RuntimeError("Manifest version mismatch for %s" % current)
        base = str(manifest.get("base_version", "") or "")
        if not base:
            raise RuntimeError("Missing base version for %s" % current)
        if base == local:
            return {
                "release": release,
                "manifest": manifest,
                "latest_version": latest_tag,
                "more_updates": current != latest_tag,
            }
        current = base

    raise RuntimeError("No update step found from %s" % local)


def print_exception(e):
    try:
        import sys

        if hasattr(sys, "print_exception"):
            sys.print_exception(e)
            return
    except Exception:
        pass
    try:
        import traceback

        traceback.print_exception(type(e), e, getattr(e, "__traceback__", None))
    except Exception:
        try:
            print(repr(e))
        except Exception:
            pass


def log_github_api_failure(url, attempt, retries, use_headers, err=None, response=None):
    try:
        status = None
        if response is not None:
            status = getattr(response, "status_code", None)
            if status is None:
                status = getattr(response, "status", None)
        print(
            "[updater] GitHub API request failed: attempt={}/{} headers={} status={} url={}".format(
                attempt + 1,
                retries,
                "yes" if use_headers else "no",
                status,
                url,
            )
        )
        if response is not None:
            body = http_client.response_text(response)
            if body:
                if len(body) > 300:
                    body = body[:300] + "..."
                print("[updater] GitHub API response body: {}".format(body))
    except Exception:
        pass
    if err is not None:
        print_exception(err)


def is_rate_limited(response):
    status = getattr(response, "status_code", None)
    if status is None:
        status = getattr(response, "status", None)
    if status not in (403, 429):
        return False
    headers = getattr(response, "headers", None)
    if headers:
        try:
            if str(headers.get("x-ratelimit-remaining", "")) == "0":
                return True
        except Exception:
            pass
    return "rate limit" in http_client.response_text(response).lower()


def github_api_get_json(url, requests_module, retries=4, i18n=None):
    headers = {
        "User-Agent": "UHS-M5Dial-Updater",
        "Accept": "application/vnd.github+json",
        "Connection": "close",
    }
    last_err = None
    for attempt in range(retries):
        r = None
        try:
            http_client.gc_hard(cycles=2, pause_ms=20)
            r = http_client.get(requests_module, url, headers=headers, stream=True)
            status = getattr(r, "status_code", None)
            if status is None:
                status = getattr(r, "status", None)
            if is_rate_limited(r):
                err = RuntimeError(_t(i18n, "updater.github_rate_limited", "GitHub API limit reached, retry later"))
                log_github_api_failure(url, attempt, retries, True, err=err, response=r)
                raise err
            if status != 200:
                err = RuntimeError("HTTP %s: %s" % (status, url))
                log_github_api_failure(url, attempt, retries, True, err=err, response=r)
                raise err
            data = http_client.read_response_json(r, GITHUB_JSON_TMP_PATH)
            r = None
            return data
        except TypeError as e:
            last_err = e
            log_github_api_failure(url, attempt, retries, True, err=e)
            break
        except OSError as e:
            last_err = e
            log_github_api_failure(url, attempt, retries, True, err=e)
            http_client.gc_hard(cycles=3, pause_ms=80)
        finally:
            try:
                if r is not None:
                    r.close()
            except Exception:
                pass
        try:
            import time

            time.sleep_ms(200 + (attempt * 250))
        except Exception:
            import time

            time.sleep(0.2 + (attempt * 0.25))
    raise RuntimeError("GitHub API request failed: %s err=%r" % (url, last_err))


def resolve_release(channel="stable", requests_module=None, i18n=None):
    requests_module = requests_module or http_client.default_requests_module()
    if requests_module is None:
        raise RuntimeError("Missing requests2 module")

    normalized = str(channel or "stable").strip().lower()
    if normalized != "prerelease":
        release = github_api_get_json(latest_release_url(), requests_module, i18n=i18n)
        manifest_url = asset_download_url(release)
        if manifest_url:
            info = release_info(release, manifest_url)
            del release
            http_client.gc_hard(cycles=1, pause_ms=10)
            return info
        raise RuntimeError("No matching release manifest")

    releases = github_api_get_json(releases_url(), requests_module, i18n=i18n)
    for release in releases:
        if release.get("draft"):
            continue
        if not release.get("prerelease"):
            continue
        manifest_url = asset_download_url(release)
        if manifest_url:
            info = release_info(release, manifest_url)
            del release
            del releases
            http_client.gc_hard(cycles=1, pause_ms=10)
            return info
    raise RuntimeError("No matching release manifest")


def release_candidates(channel="stable", requests_module=None, local_version="", i18n=None):
    """Return compact eligible release records, newest first.

    Pages are deliberately small because GitHub release objects contain large
    asset metadata. We stop once the local tag is encountered.
    """
    requests_module = requests_module or http_client.default_requests_module()
    if requests_module is None:
        raise RuntimeError("Missing requests2 module")

    normalized = str(channel or "stable").strip().lower()
    if normalized != "prerelease":
        normalized = "stable"
    local = str(local_version or "").strip()
    page = 1
    page_size = 10
    candidates = []
    while page <= 20:
        releases = github_api_get_json(
            releases_url(page=page, per_page=page_size),
            requests_module,
            i18n=i18n,
        )
        if not isinstance(releases, list):
            raise RuntimeError("Invalid GitHub releases response")
        page_count = len(releases)
        found_local = False
        for release in releases:
            if release.get("draft"):
                continue
            if normalized == "prerelease":
                if not release.get("prerelease"):
                    continue
            elif release.get("prerelease"):
                continue
            manifest_url = asset_download_url(release)
            if not manifest_url:
                continue
            info = release_info(release, manifest_url)
            candidates.append(info)
            if info.get("tag") == local:
                found_local = True
        del releases
        http_client.gc_hard(cycles=1, pause_ms=10)
        if found_local or page_count < page_size:
            break
        page += 1
    return candidates


def resolve_update_step(channel, local_version, requests_module=None, i18n=None):
    """Resolve the one delta that can be applied to local_version."""
    requests_module = requests_module or http_client.default_requests_module()
    if requests_module is None:
        raise RuntimeError("Missing requests2 module")
    normalized = str(channel or "stable").strip().lower()
    if normalized != "prerelease":
        latest_payload = github_api_get_json(
            latest_release_url(), requests_module, i18n=i18n
        )
        latest_manifest_url = asset_download_url(latest_payload)
        if not latest_manifest_url:
            raise RuntimeError("No matching release manifest")
        current = release_info(latest_payload, latest_manifest_url)
        del latest_payload
    else:
        current = None
        page = 1
        while page <= 20 and current is None:
            payload = github_api_get_json(
                releases_url(page=page, per_page=1),
                requests_module,
                i18n=i18n,
            )
            if not isinstance(payload, list):
                raise RuntimeError("Invalid GitHub releases response")
            for release in payload:
                if release.get("draft") or not release.get("prerelease"):
                    continue
                manifest_url = asset_download_url(release)
                if manifest_url:
                    current = release_info(release, manifest_url)
                    break
            page += 1
            del payload
            http_client.gc_hard(cycles=1, pause_ms=10)
        if current is None:
            raise RuntimeError("No matching prerelease manifest")

    local = str(local_version or "").strip()
    latest_version = current.get("tag", "")
    if local == latest_version:
        return None

    visited = set()
    while True:
        tag = current.get("tag", "")
        if tag in visited:
            raise RuntimeError("Update chain contains a cycle at %s" % tag)
        visited.add(tag)

        manifest = download_manifest(
            current["manifest_url"],
            requests_module=requests_module,
            i18n=i18n,
        )
        if not isinstance(manifest, dict):
            raise RuntimeError("Invalid update manifest for %s" % tag)
        manifest_version = str(manifest.get("version", "") or "")
        if manifest_version and manifest_version != tag:
            raise RuntimeError("Manifest version mismatch for %s" % tag)
        base = str(manifest.get("base_version", "") or "")
        if not base:
            raise RuntimeError("Missing base version for %s" % tag)
        if base == local:
            return {
                "release": current,
                "manifest": manifest,
                "latest_version": latest_version,
                "more_updates": tag != latest_version,
            }

        previous_payload = github_api_get_json(
            release_by_tag_url(base), requests_module, i18n=i18n
        )
        previous_manifest_url = asset_download_url(previous_payload)
        if not previous_manifest_url:
            raise RuntimeError("No matching release manifest for %s" % base)
        current = release_info(previous_payload, previous_manifest_url)
        del previous_payload
        del manifest
        http_client.gc_hard(cycles=1, pause_ms=10)


def download_manifest(url, requests_module=None, i18n=None):
    requests_module = requests_module or http_client.default_requests_module()
    if requests_module is None:
        raise RuntimeError("Missing requests2 module")
    headers = {
        "User-Agent": "UHS-M5Dial-Updater",
        "Accept": "application/json",
        "Connection": "close",
    }
    current_url = url
    for _ in range(5):
        r = None
        try:
            r = http_client.get(requests_module, current_url, headers=headers, stream=True)
            status = getattr(r, "status_code", None)
            if status is None:
                status = getattr(r, "status", None)
            if status == 200:
                data = http_client.read_response_json(r, MANIFEST_JSON_TMP_PATH)
                r = None
                http_client.gc_hard(cycles=1, pause_ms=10)
                return data
            if status in (301, 302, 303, 307, 308):
                location = http_client.response_header(r, "Location")
                if not location:
                    raise RuntimeError("Manifest redirect missing Location")
                current_url = location
                continue
            raise RuntimeError("HTTP %s: %s" % (status, current_url))
        finally:
            try:
                if r is not None:
                    r.close()
            except Exception:
                pass
    raise RuntimeError("Manifest redirect limit exceeded")
