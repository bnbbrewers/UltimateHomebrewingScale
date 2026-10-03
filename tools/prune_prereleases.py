"""Keep at most one pre-release on GitHub: the newest, and only while it is
newer than the latest release.

A device on the prerelease channel installs the newest published release,
stable or not, and one on the stable channel the latest release: an older
pre-release is never installed again and only clutters the release list.

Run by the release workflow once a new pre-release carries all its assets,
and by the promote workflow once a pre-release became a release. Only the
GitHub releases are deleted, with their assets; the tags stay, so a version
can still be rebuilt with the release workflow's dispatch. Drafts and tags
that are not vX.Y.Z are never touched.

Usage: python3 tools/prune_prereleases.py [--dry-run]   (needs gh and GH_TOKEN)
"""

import json
import subprocess
import sys


def _version(tag):
    """(X, Y, Z) for a vX.Y.Z tag, None otherwise."""
    text = str(tag or "")
    if not text.startswith("v"):
        return None
    try:
        parts = tuple(int(p) for p in text[1:].split("."))
    except ValueError:
        return None
    return parts if len(parts) == 3 else None


def prereleases_to_delete(releases):
    """Tags of the pre-releases to delete, newest first.

    ``releases`` are the objects of ``gh release list --json
    tagName,isPrerelease,isDraft``.
    """
    stable = []
    pre = []
    for release in releases:
        if release.get("isDraft"):
            continue
        version = _version(release.get("tagName"))
        if version is None:
            continue
        if release.get("isPrerelease"):
            pre.append((version, release["tagName"]))
        else:
            stable.append(version)
    pre.sort(reverse=True)
    latest_stable = max(stable) if stable else None
    if pre and (latest_stable is None or pre[0][0] > latest_stable):
        pre = pre[1:]
    return [tag for _version_, tag in pre]


def _gh(*args):
    return subprocess.run(("gh",) + args, check=True, capture_output=True, text=True).stdout


def main(argv):
    dry_run = "--dry-run" in argv
    releases = json.loads(_gh("release", "list", "--limit", "200",
                              "--json", "tagName,isPrerelease,isDraft"))
    doomed = prereleases_to_delete(releases)
    if not doomed:
        print("No pre-release to prune.")
        return 0
    for tag in doomed:
        if dry_run:
            print("Would delete pre-release %s" % tag)
            continue
        try:
            _gh("release", "delete", tag, "--yes")
            print("Deleted pre-release %s (tag kept)" % tag)
        except subprocess.CalledProcessError as error:
            # Another run may have deleted it first. The new release is out
            # whatever happens here, so warn rather than fail the run.
            print("::warning::could not delete %s: %s" % (tag, (error.stderr or "").strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
