# .mpy Runtime Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build and publish the UHS runtime as MicroPython .mpy files while keeping main.py and configuration exceptions, migrating legacy .py installations through the updater, and preserving safe differential updates.

**Architecture:** Add tools/build_runtime.py as the deterministic transformation and diff-planning library used by the GitHub Actions workflow. The workflow builds mpy-cross from UIFlow MicroPython tag 2.4.2, creates the complete staged filesystem, and archives artifacts from that staging. The updater removes the same-path .py after successfully installing an .mpy; explicit manifest deletes handle files that no longer exist in the source tree.

**Tech Stack:** MicroPython mpy-cross from m5stack/uiflow-micropython tag 2.4.2, Python 3 host tooling, GitHub Actions, LittleFS staging, TAR/ZIP archives, unittest host tests.

## Global Constraints

- main.py remains a deployed source bootstrap and is never compiled or deleted.
- config.py.example remains a deployed source example and is never compiled or deleted.
- config.py is never included in release artifacts and is never deleted by the updater.
- Every other selected project .py file is deployed as the same-path .mpy file.
- The updater deletes a same-path .py only after installing its .mpy; a missing .py is harmless.
- A source file removed from the project may contribute both .py and .mpy to explicit manifest deletes.
- The first .mpy release must include all current compiled modules in its diff so legacy .py devices can migrate.
- Build tooling under tools/ is not deployed to the device.
- mpy-cross must come from UIFlow MicroPython tag 2.4.2; no floating/latest compiler is allowed.
- No release or updater behavior may delete arbitrary .py files by filesystem scan.
- All shell commands in this workspace use the rtk prefix.

---

### Task 1: Add failing host tests for runtime transformation and diff planning

**Files:**
- Create: tools/test_build_runtime.py
- Test: tools/test_build_runtime.py

**Interfaces:**
- Consumes: public and testable functions that will be added to tools/build_runtime.py in Task 2.
- Produces: executable regression coverage for path selection, artifact mapping, staging, and legacy migration behavior.

- [ ] **Step 1: Create the test module with temporary fixtures and a fake compiler**

Add a unittest.TestCase that creates a temporary source tree containing:

~~~
main.py
config.py
config.py.example
apps/scale_app.py
apps/__init__.py
assets/icons/Scale.png
docs/README.md
tools/build_runtime.py
~~~

Use a fake compiler callable with the signature
compile_file(source_path: Path, output_path: Path) -> None that writes
b"MPY:" + source_path.read_bytes() to the output. This keeps transformation
tests independent from the host compiler binary.

- [ ] **Step 2: Write failing tests for selection and artifact mapping**

Cover these exact expectations:

~~~
assert should_compile("apps/scale_app.py") is True
assert should_compile("main.py") is False
assert should_compile("config.py.example") is False
assert should_compile("config.py") is False
assert artifact_path("apps/scale_app.py") == "apps/scale_app.mpy"
assert artifact_path("main.py") == "main.py"
assert artifact_path("assets/icons/Scale.png") == "assets/icons/Scale.png"
assert include_runtime_path("docs/README.md") is False
assert include_runtime_path("tools/build_runtime.py") is False
~~~

- [ ] **Step 3: Write failing tests for staging output**

Call build_staging(source_root, staging_root, version, compile_file=fake_compile)
and assert:

~~~
assert (staging_root / "main.py").is_file()
assert (staging_root / "config.py.example").is_file()
assert not (staging_root / "config.py").exists()
assert (staging_root / "apps/scale_app.mpy").read_bytes().startswith(b"MPY:")
assert (staging_root / "apps/__init__.mpy").is_file()
assert (staging_root / "assets/icons/Scale.png").is_file()
assert not (staging_root / "docs/README.md").exists()
assert not (staging_root / "tools/build_runtime.py").exists()
assert (staging_root / "uhs-version.txt").read_text() == "v-test\n"
~~~

- [ ] **Step 4: Write failing tests for diff planning**

Use a fake repository adapter that returns these changed paths:

~~~
M    apps/scale_app.py
A    apps/new_app.py
D    apps/old_app.py
M    main.py
M    assets/icons/Scale.png
~~~

Assert that a post-migration plan archives apps/scale_app.mpy,
apps/new_app.mpy, main.py, and the changed image, while explicit deletes
contain apps/old_app.py and apps/old_app.mpy. Assert that a first-migration
plan includes every .mpy file present in the staging and legacy .py files
from the base tree, but does not delete main.py or either configuration file.

- [ ] **Step 5: Run the focused tests and verify they fail for missing interfaces**

Run:

~~~
rtk python -m unittest tools.test_build_runtime -v
~~~

Expected: FAIL because tools/build_runtime.py and its specified interfaces do
not exist yet.

### Task 2: Implement the deterministic runtime staging and diff planner

**Files:**
- Create: tools/build_runtime.py
- Modify: .gitignore only if needed to keep generated staging files ignored
- Test: tools/test_build_runtime.py

**Interfaces:**
- Consumes: a source root, staging root, version string, compiler executable or injected compiler, and Git repository path/ref data.
- Produces: include_runtime_path(path) -> bool, should_compile(path) -> bool, artifact_path(path) -> str, build_staging(...) -> BuildReport, and plan_diff(...) -> DiffPlan.

- [ ] **Step 1: Implement path normalization and selection rules**

Use POSIX-style relative paths internally. Implement:

~~~
COMPILE_EXCEPTIONS = {"main.py", "config.py.example"}
PROTECTED_CONFIG = {"config.py", "config.py.example"}

def include_runtime_path(path: str) -> bool: ...
def should_compile(path: str) -> bool: ...
def artifact_path(path: str) -> str: ...
~~~

include_runtime_path must reject empty paths, docs/, firmware/, .github/, tools/,
Markdown files, LICENSE, .gitignore, excluded examples, and config.py. It must
allow config.py.example. should_compile must return true only for included .py
files outside COMPILE_EXCEPTIONS.

- [ ] **Step 2: Implement compiler invocation with injectable test support**

Implement a production compiler wrapper that runs:

~~~
<mpy-cross> <source.py> -o <output.mpy>
~~~

with subprocess.run(..., check=True, cwd=source_root). Keep the fake compiler
callable path used by the tests so path rules can be tested without compiling
MicroPython during every host test. Create parent directories before writing
outputs and fail immediately if the compiler returns non-zero or does not
produce a non-empty .mpy.

- [ ] **Step 3: Implement build_staging**

Enumerate tracked files with git -C <source_root> ls-files -z, normalize each
path, and apply include_runtime_path. For selected files, copy exceptions and
non-Python files byte-for-byte; compile all other .py files to the mapped .mpy
path. Write exactly one newline-terminated version file.

Return a report containing at least:

~~~
BuildReport(
    files=tuple[str, ...],
    compiled=tuple[str, ...],
    direct=tuple[str, ...],
)
~~~

Before returning, scan the staging tree and raise RuntimeError if any .py file
other than main.py or config.py.example exists, or if either required exception
is missing.

- [ ] **Step 4: Implement Git diff parsing and runtime format detection**

Implement a repository adapter using git diff --name-status -z <base_ref> <head_ref>
and git ls-tree -r --name-only <base_ref>. Parse additions, modifications,
deletions, and renames without assuming a tab-delimited single path. A base
release is considered legacy when <base_ref>:tools/build_runtime.py does not
exist; this makes the first release containing the tool the automatic .mpy
migration release without adding a runtime marker file.

- [ ] **Step 5: Implement plan_diff**

Return:

~~~
DiffPlan(
    archive_paths=tuple[str, ...],
    delete_paths=tuple[str, ...],
    first_mpy_migration=bool,
)
~~~

For post-migration changes, map selected .py sources to .mpy, keep
main.py/config.py.example direct, preserve non-Python paths, and include
uhs-version.txt. For a deleted source, add both its .py and .mpy paths to
delete_paths. For a rename, archive the new artifact and delete both variants
of the old path. Never add protected configuration paths to deletes.

For the first migration, add every .mpy in the current staging to
archive_paths, add every legacy compiled .py from the base tree to
delete_paths, keep main.py and config.py.example, and still include changed
direct files plus uhs-version.txt. Deduplicate and sort both tuples.

- [ ] **Step 6: Run the focused tests and verify they pass**

Run:

~~~
rtk python -m unittest tools.test_build_runtime -v
~~~

Expected: PASS for all staging, mapping, and migration cases.

- [ ] **Step 7: Commit the build tool and tests**

~~~
rtk git add tools/build_runtime.py tools/test_build_runtime.py
rtk git commit -m "build: add deterministic mpy runtime staging"
~~~

### Task 3: Wire the GitHub Actions firmware and diff build to .mpy

**Files:**
- Modify: .github/workflows/repack-firmware.yml:91-318
- Modify: tools/build_runtime.py only if integration exposes a tested interface gap
- Test: tools/test_build_runtime.py

**Interfaces:**
- Consumes: build_staging(...) and plan_diff(...) from Task 2, the tag/ref metadata already prepared by the workflow, and UIFlow MicroPython tag 2.4.2.
- Produces: compiled dist/fs-user, a compiled ZIP, a compiled firmware filesystem, a translated TAR diff, and manifests that identify runtime_format: "mpy".

- [ ] **Step 1: Add a pinned UIFlow compiler preparation step**

After installing the existing ESP-IDF tools, add a step that clones:

~~~
https://github.com/m5stack/uiflow-micropython.git
~~~

at tag 2.4.2, initializes the MicroPython submodule needed by the M5Stack
Makefile, runs make -C <clone>/m5stack mpy-cross, and verifies the resulting
mpy-cross executable is present and executable. Do not use pip install mpy-cross
without the pinned source revision.

- [ ] **Step 2: Replace the current raw source copy with the staging tool**

Replace the git ls-files | tar ... block in Build runtime file artifact with a
call equivalent to:

~~~
python3 tools/build_runtime.py \
  --source-root "$GITHUB_WORKSPACE" \
  --staging-root "$GITHUB_WORKSPACE/dist/fs-user" \
  --version "$TAG_NAME" \
  --mpy-cross "$GITHUB_WORKSPACE/dist/uiflow-micropython/micropython/mpy-cross/mpy-cross"
~~~

Keep the existing postconditions for excluded directories, but change them to
assert that main.py and config.py.example exist, that config.py does not, and
that no unexpected .py exists under dist/fs-user. Keep the ZIP creation from
dist/fs-user.

- [ ] **Step 3: Replace source-path diff assembly with plan_diff**

In the metadata Python block, import tools.build_runtime, call
plan_diff(source_root=Path(os.environ["GITHUB_WORKSPACE"]), base_ref=base_version,
head_ref=os.environ["TAG_NAME"], staging_root=Path("../fs-user")), and add
every archive_path that exists in the staging to the TAR. Add every delete_path
to the manifest delete list, preserving the existing explicit install.py cleanup
for compatibility.

Remove the old direct Path("../fs-user") / path logic that would otherwise
place .py sources in the archive. Keep uhs-version.txt in every diff.

- [ ] **Step 4: Add runtime format metadata to manifests**

Add these fields to the current build/update metadata:

~~~
{
  "runtime_format": "mpy",
  "first_mpy_migration": true
}
~~~

Set first_mpy_migration from the returned DiffPlan. Update the excluded list to
include tools/ and describe that Python sources are compiled except for main.py
and config.py.example.

- [ ] **Step 5: Validate the generated artifact lists in CI**

Add shell assertions after staging and before publication:

~~~
test -f dist/fs-user/main.py
test -f dist/fs-user/config.py.example
test ! -e dist/fs-user/config.py
if find dist/fs-user -type f -name '*.py' ! -path 'dist/fs-user/main.py' ! -path 'dist/fs-user/config.py.example' | grep -q .; then
  echo "Unexpected Python source in runtime staging" >&2
  exit 1
fi
find dist/fs-user -type f -name '*.mpy' -print
~~~

Ensure the ZIP, LittleFS image, uploaded artifact, and GitHub Release all use
the same compiled dist/fs-user outputs.

- [ ] **Step 6: Run host tests and validate the workflow text**

Run:

~~~
rtk python -m unittest tools.test_build_runtime -v
rtk rg -n "mpy-cross|build_runtime|runtime_format|first_mpy_migration|Unexpected Python" .github/workflows/repack-firmware.yml
~~~

Expected: all tests pass and the workflow contains the pinned compiler, staging
call, metadata, and validation assertions.

- [ ] **Step 7: Commit the workflow changes**

~~~
rtk git add .github/workflows/repack-firmware.yml
rtk git commit -m "ci: publish compiled mpy runtime artifacts"
~~~

### Task 4: Add updater cleanup for installed .mpy files

**Files:**
- Modify: updater/tar_extract.py:154-197
- Modify: updater/workflow.py:73-86,285-295,152-167
- Test: tools/test_updater_mpy_cleanup.py

**Interfaces:**
- Consumes: extracted archive paths and the existing safe path/delete validation.
- Produces: same-path .py cleanup after .mpy installation and protected configuration behavior.

- [ ] **Step 1: Write failing updater cleanup tests**

Create tools/test_updater_mpy_cleanup.py using a temporary working directory and
a minimal TAR writer. Cover:

~~~
def test_extracting_mpy_removes_existing_source_py(): ...
def test_extracting_mpy_succeeds_when_source_py_is_absent(): ...
def test_config_files_are_not_removed_by_mpy_cleanup(): ...
def test_explicit_delete_accepts_both_variants_for_removed_module(): ...
def test_explicit_delete_rejects_config_example(): ...
~~~

The first test must create apps/demo.py, extract apps/demo.mpy, and assert that
only apps/demo.mpy remains. The second must omit the source and assert extraction
succeeds. The configuration test must verify that a compiled config.mpy cannot
remove either config.py or config.py.example.

- [ ] **Step 2: Run the focused updater tests and verify failure**

Run:

~~~
rtk python -m unittest tools.test_updater_mpy_cleanup -v
~~~

Expected: FAIL because the extractor has no .py cleanup hook and delete
validation does not yet protect config.py.example.

- [ ] **Step 3: Implement same-path source cleanup in tar_extract.py**

Add a helper with this contract:

~~~
def _remove_source_for_mpy(dest_root, path):
    """Remove the same-path .py source for an installed .mpy, if allowed."""
~~~

Call it only after _replace(tmp, dest) succeeds for a regular file whose
validated archive path ends in .mpy. Convert foo.mpy to foo.py in the same
directory, skip config.py and config.py.example, and ignore the filesystem error
for an absent source file. Do not scan directories or delete other Python files.

- [ ] **Step 4: Protect configuration paths in explicit manifest deletes**

Update updater/workflow.py delete path validation to reject both config.py and
config.py.example, while retaining the existing rejection of storage/*.json,
traversal, absolute paths, and drive-qualified paths. Keep explicit deletion
tolerant of an already absent file.

- [ ] **Step 5: Validate optional runtime metadata without breaking old manifests**

In _manifest_archive, accept an absent runtime_format for legacy manifests, but
reject a present value other than "mpy". Preserve strategy == "tar-diff" and all
existing archive URL, size, and SHA-256 checks. Carry first_mpy_migration through
the parsed archive record only as metadata; do not use it to broaden filesystem
deletes.

- [ ] **Step 6: Run updater tests and the full host suite**

Run:

~~~
rtk python -m unittest tools.test_updater_mpy_cleanup -v
rtk python -m unittest discover -v
~~~

Expected: both commands pass. If repository-wide discovery does not find the
tool tests because the project has no tracked tests package, run both tool
modules explicitly and record that result in the handoff.

- [ ] **Step 7: Commit updater behavior**

~~~
rtk git add updater/tar_extract.py updater/workflow.py tools/test_updater_mpy_cleanup.py
rtk git commit -m "fix: remove legacy python after mpy updates"
~~~

### Task 5: Update documentation and add release-safety checks

**Files:**
- Modify: README.md:137-142,218-225,263-270
- Modify: INSTALLATION.MD:26-47
- Modify: firmware/CustomFirmware.MD
- Test: no new test file; validate documentation references with search

**Interfaces:**
- Consumes: final artifact and updater behavior from Tasks 3 and 4.
- Produces: user-facing instructions that match the compiled runtime and migration behavior.

- [ ] **Step 1: Update the README runtime architecture**

Document that runtime modules are deployed as .mpy, main.py remains the
entrypoint, config.py.example is retained, config.py is local, and tools/ is
CI-only. Replace the current hop-specific precompile wording with the
project-wide rule while keeping the memory rationale.

- [ ] **Step 2: Update installation and updater instructions**

Explain that the first .mpy release migrates existing .py installations, that
later diffs carry changed .mpy files, and that the updater removes only a
same-path .py after installing its .mpy. State that absent .py files are normal
and configuration files are preserved.

- [ ] **Step 3: Update firmware build documentation**

Document the pinned UIFlow 2.4.2 mpy-cross provenance, the retained main.py
bootstrap, and the fact that the repack workflow uses one compiled staging tree
for both the full firmware and update archives.

- [ ] **Step 4: Validate documentation and repository state**

Run:

~~~
rtk rg -n "\\.mpy|main\\.py|config\\.py\\.example|config\\.py|mpy-cross|migration" README.md INSTALLATION.MD firmware/CustomFirmware.MD
rtk git diff --check
rtk git status --short
~~~

Expected: documentation contains the new behavior, no whitespace errors are
reported, and only intended files are modified.

- [ ] **Step 5: Commit documentation**

~~~
rtk git add README.md INSTALLATION.MD firmware/CustomFirmware.MD
rtk git commit -m "docs: describe mpy runtime deployment"
~~~

### Task 6: Verify the complete implementation before handoff

**Files:**
- Verify: .github/workflows/repack-firmware.yml
- Verify: tools/build_runtime.py
- Verify: updater/tar_extract.py
- Verify: updater/workflow.py

**Interfaces:**
- Consumes: all changes from Tasks 1–5.
- Produces: evidence that host transformations, updater safety, and workflow wiring are internally consistent.

- [ ] **Step 1: Run all host tests**

~~~
rtk python -m unittest tools.test_build_runtime tools.test_updater_mpy_cleanup -v
~~~

Expected: PASS.

- [ ] **Step 2: Run static source checks**

~~~
rtk python -m py_compile tools/build_runtime.py tools/test_build_runtime.py tools/test_updater_mpy_cleanup.py updater/tar_extract.py updater/workflow.py
rtk git diff --check
~~~

Expected: no syntax errors and no whitespace errors.

- [ ] **Step 3: Perform a local staging smoke test with the fake compiler**

Run a short Python command that creates a temporary copy of the tracked runtime
fixture, invokes build_staging with the fake compiler, and prints the sorted
staging file list. Confirm manually that the list contains main.py,
config.py.example, .mpy modules and non-Python assets, but no other .py.

- [ ] **Step 4: Inspect the final diff and status**

~~~
rtk git diff HEAD~5..HEAD --stat
rtk git status --short --branch
~~~

Expected: all implementation, test, workflow and documentation files are
accounted for, and no generated .mpy or staging directory is tracked.

- [ ] **Step 5: Report completion with verification evidence**

State the exact test commands and results, identify any check that could not be
run locally (for example the full GitHub Action requiring hosted Linux and
ESP-IDF), and link the changed files.
