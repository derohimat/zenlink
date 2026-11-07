"""ZenLink macOS Apple Silicon (arm64) End-to-End Test Suite

Requirement-driven, opaque-box test suite across 4 tiers:
- Tier 1: Feature Coverage (tools/get-adb, OCR, startup scripts, Rust platform gating, non-macOS test regression)
- Tier 2: Boundary & Corner Cases (corrupted downloads, hash mismatch, empty/malformed OCR, unicode/spaces paths, guarded imports, Windows file isolation)
- Tier 3: Cross-Feature Combinations (get-adb -> find_adb, OCR -> sidecar endpoint, playfair build & codesign, sidecar python resolution)
- Tier 4: Real-World Workload Scenarios (fresh clone bootstrap simulation, macOS runtime paths & contracts, VideoView API contract)

Authoritative sources:
- ORIGINAL_REQUEST.md
- PROJECT.md (Architecture, Code Layout, Interface Contracts)
- Google Android platform-tools repository manifest (repository2-3.xml line 11488-11495)
"""

from __future__ import annotations

import base64
import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Authoritative Constants from PROJECT.md and Google platform-tools manifest
EXPECTED_DARWIN_ADB_REVISION = "37.0.1"
EXPECTED_DARWIN_ADB_SHA256 = "ee39ad5967e95c2a07f04dbcbde96b1a0c916ba376096db5d2f498b7727a5d1d"
EXPECTED_DARWIN_ADB_URL = f"https://dl.google.com/android/repository/platform-tools_r{EXPECTED_DARWIN_ADB_REVISION}-darwin.zip"

EXPECTED_WIN_ADB_REVISION = "37.0.1"
EXPECTED_WIN_ADB_SHA256 = "45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99"


# ==============================================================================
# Tier 1: Feature Coverage
# ==============================================================================

class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1: Primary behavior and happy path verification for macOS features."""

    def test_t1_01_get_adb_darwin_cli_contract(self):
        """tools/get-adb must exist, be executable, and default to official Darwin pins."""
        script = ROOT / "tools" / "get-adb"
        self.assertTrue(script.is_file(), f"tools/get-adb script does not exist at {script}")
        mode = script.stat().st_mode
        self.assertTrue(bool(mode & stat.S_IXUSR), "tools/get-adb must be executable (+x)")

        content = script.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("#!/usr/bin/env bash") or content.startswith("#!/bin/bash") or content.startswith("#!/bin/sh"),
                        "tools/get-adb must have a valid POSIX shebang")
        self.assertIn(EXPECTED_DARWIN_ADB_REVISION, content,
                      f"tools/get-adb must default to revision {EXPECTED_DARWIN_ADB_REVISION}")
        self.assertIn(EXPECTED_DARWIN_ADB_SHA256, content,
                      f"tools/get-adb must default to SHA-256 {EXPECTED_DARWIN_ADB_SHA256}")
        self.assertTrue(re.search(r"platform-tools_r(\$\{REVISION\}|\$REVISION|" + re.escape(EXPECTED_DARWIN_ADB_REVISION) + r")-darwin\.zip", content),
                        "tools/get-adb must download the darwin archive")
        self.assertIn("third_party/platform-tools", content,
                      "tools/get-adb default destination must be third_party/platform-tools")

    def test_t1_02_get_adb_execution_and_sha256(self):
        """tools/get-adb must download Darwin adb, verify SHA-256, extract adb/NOTICE.txt, and validate codesign."""
        script = ROOT / "tools" / "get-adb"
        if not script.is_file():
            self.skipTest("tools/get-adb not yet created")

        with tempfile.TemporaryDirectory(prefix="zenlink_adb_test_") as tmpdir:
            dest = Path(tmpdir) / "platform-tools"
            res = subprocess.run(
                ["bash", str(script), str(dest), EXPECTED_DARWIN_ADB_REVISION, EXPECTED_DARWIN_ADB_SHA256],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(res.returncode, 0, f"tools/get-adb failed: {res.stderr}\nstdout: {res.stdout}")

            adb_bin = dest / "adb"
            self.assertTrue(adb_bin.is_file(), f"adb executable missing in {dest}")
            self.assertTrue(os.access(adb_bin, os.X_OK), "Extracted adb must be executable")

            notice = dest / "NOTICE.txt"
            self.assertTrue(notice.is_file(), f"NOTICE.txt missing in {dest}")
            self.assertGreater(notice.stat().st_size, 0, "NOTICE.txt must not be empty")

            # Check Mach-O binary format on macOS
            if platform.system() == "Darwin":
                cs = subprocess.run(["codesign", "-v", str(adb_bin)], capture_output=True, text=True)
                self.assertEqual(cs.returncode, 0, f"codesign verification failed on {adb_bin}: {cs.stderr}")

                ver = subprocess.run([str(adb_bin), "version"], capture_output=True, text=True)
                self.assertEqual(ver.returncode, 0, f"adb version failed: {ver.stderr}")
                self.assertIn("Android Debug Bridge version", ver.stdout)

    def test_t1_03_ocr_helper_and_safe_fallback(self):
        """tools/ocr.swift must exist and zenlink/ocr.py must run on macOS without Win32/creationflags errors."""
        swift_tool = ROOT / "tools" / "ocr.swift"
        self.assertTrue(swift_tool.is_file(), f"tools/ocr.swift does not exist at {swift_tool}")

        # Check zenlink/ocr.py implementation
        ocr_py = ROOT / "zenlink" / "ocr.py"
        self.assertTrue(ocr_py.is_file(), "zenlink/ocr.py must exist")
        content = ocr_py.read_text(encoding="utf-8")

        # Must not unconditionally pass Windows creationflags
        self.assertNotIn("creationflags=_NO_WINDOW,\n        )", content,
                         "creationflags must not be passed unconditionally on macOS in subprocess.run")

        # Test importing and calling recognize_png on empty/minimal image
        sys.path.insert(0, str(ROOT))
        try:
            from zenlink import ocr
            # 1x1 transparent PNG bytes
            tiny_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
                b"\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            try:
                lines = ocr.recognize_png(tiny_png)
                self.assertIsInstance(lines, list, "recognize_png must return a list of strings")
            except Exception as e:
                self.assertNotIsInstance(e, ValueError, "Must not raise ValueError: creationflags on macOS")
                self.assertNotIsInstance(e, FileNotFoundError, "Must not attempt to execute powershell.exe on macOS")
        finally:
            if str(ROOT) in sys.path:
                sys.path.remove(str(ROOT))

    def test_t1_04_startup_scripts_syntax_and_environment(self):
        """Start ZenLink.sh and run.sh must be executable, syntactically valid bash, and target macOS."""
        start_sh = ROOT / "Start ZenLink.sh"
        run_sh = ROOT / "run.sh"

        self.assertTrue(start_sh.is_file(), f"Start ZenLink.sh missing at {start_sh}")
        self.assertTrue(run_sh.is_file(), f"run.sh missing at {run_sh}")

        self.assertTrue(bool(start_sh.stat().st_mode & stat.S_IXUSR), "Start ZenLink.sh must be executable (+x)")
        self.assertTrue(bool(run_sh.stat().st_mode & stat.S_IXUSR), "run.sh must be executable (+x)")

        # Verify bash syntax with `bash -n`
        res_start = subprocess.run(["bash", "-n", str(start_sh)], capture_output=True, text=True)
        self.assertEqual(res_start.returncode, 0, f"Syntax error in Start ZenLink.sh: {res_start.stderr}")

        res_run = subprocess.run(["bash", "-n", str(run_sh)], capture_output=True, text=True)
        self.assertEqual(res_run.returncode, 0, f"Syntax error in run.sh: {res_run.stderr}")

        # Verify Start ZenLink.sh contents
        start_txt = start_sh.read_text(encoding="utf-8")
        self.assertNotIn("winget", start_txt, "macOS start script must not use Windows winget")
        self.assertNotIn("powershell.exe", start_txt, "macOS start script must not use powershell.exe")
        self.assertIn("tools/get-adb", start_txt, "Start ZenLink.sh must invoke POSIX tools/get-adb")
        self.assertIn(".venv", start_txt, "Start ZenLink.sh must reference .venv")

    def test_t1_05_rust_cargo_darwin_target_gating(self):
        """Cargo.toml in zenlink-video and zenlink-app must gate windows under target.'cfg(windows)'."""
        video_cargo = ROOT / "rust" / "crates" / "zenlink-video" / "Cargo.toml"
        app_cargo = ROOT / "rust" / "crates" / "zenlink-app" / "Cargo.toml"

        self.assertTrue(video_cargo.is_file(), "zenlink-video Cargo.toml missing")
        self.assertTrue(app_cargo.is_file(), "zenlink-app Cargo.toml missing")

        v_toml = video_cargo.read_text(encoding="utf-8")
        self.assertIn("[target.'cfg(windows)'.dependencies", v_toml,
                      "zenlink-video must gate windows dependencies under cfg(windows)")
        self.assertNotIn("\n[dependencies.windows]\n", v_toml,
                         "zenlink-video must not have unconditional windows dependency")

        a_toml = app_cargo.read_text(encoding="utf-8")
        self.assertIn("[target.'cfg(windows)'.dependencies", a_toml,
                      "zenlink-app must gate windows dependencies under cfg(windows)")

        # Check zenlink-video/src/lib.rs gating
        v_lib = (ROOT / "rust" / "crates" / "zenlink-video" / "src" / "lib.rs").read_text(encoding="utf-8")
        self.assertIn("#[cfg(windows)]", v_lib,
                      "zenlink-video/src/lib.rs must use #[cfg(windows)] to gate Win32 modules")
        self.assertIn("macos", v_lib,
                      "zenlink-video/src/lib.rs must reference macos module for Apple Silicon")

        # Check existence of zenlink-video/src/macos.rs
        macos_rs = ROOT / "rust" / "crates" / "zenlink-video" / "src" / "macos.rs"
        self.assertTrue(macos_rs.is_file(), f"zenlink-video/src/macos.rs platform layer missing at {macos_rs}")

    def test_t1_06_non_macos_test_regression(self):
        """Existing non-macOS test contracts (pins, prereqs, scrcpy) must not regress."""
        # 1. Scrcpy pin test
        scrcpy_rs = (ROOT / "rust" / "crates" / "zenlink-android" / "src" / "scrcpy.rs").read_text(encoding="utf-8")
        self.assertIn('pub const SCRCPY_VERSION: &str = "5.0.1";', scrcpy_rs)

        # 2. Windows source package pin invariant
        bat = (ROOT / "Start ZenLink.bat").read_text(encoding="utf-8")
        self.assertIn(f'set "ZL_ADB_REV={EXPECTED_WIN_ADB_REVISION}"', bat)
        self.assertIn(f'set "ZL_ADB_SHA256={EXPECTED_WIN_ADB_SHA256}"', bat)

        ps1 = (ROOT / "tools" / "get-adb.ps1").read_text(encoding="utf-8")
        self.assertIn(f'[string]$Revision = "{EXPECTED_WIN_ADB_REVISION}"', ps1)
        self.assertIn(f'[string]$Sha256 = "{EXPECTED_WIN_ADB_SHA256}"', ps1)

        # 3. Packaging installer checks
        iss = (ROOT / "packaging" / "ZenLink.iss").read_text(encoding="utf-8")
        self.assertNotIn("EdgeUpdate", iss)


# ==============================================================================
# Tier 2: Boundary & Corner Cases
# ==============================================================================

class TestTier2BoundaryAndCornerCases(unittest.TestCase):
    """Tier 2: Boundary conditions, invalid inputs, error handling, and isolation."""

    def test_t2_01_get_adb_hash_mismatch_aborts(self):
        """tools/get-adb must abort immediately on SHA-256 mismatch, exit non-zero, and leave no adb binary."""
        script = ROOT / "tools" / "get-adb"
        if not script.is_file():
            self.skipTest("tools/get-adb not yet created")

        fake_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        with tempfile.TemporaryDirectory(prefix="zenlink_adb_mismatch_") as tmpdir:
            dest = Path(tmpdir) / "platform-tools"
            res = subprocess.run(
                ["bash", str(script), str(dest), EXPECTED_DARWIN_ADB_REVISION, fake_hash],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertNotEqual(res.returncode, 0, "tools/get-adb must exit with non-zero code on hash mismatch")
            self.assertFalse((dest / "adb").exists(), "adb executable must NOT be installed on hash mismatch")
            # Verify no zip files left behind in destination or parent
            zips = list(Path(tmpdir).glob("**/*.zip"))
            self.assertEqual(len(zips), 0, f"Temporary zip files were not cleaned up: {zips}")

    def test_t2_02_get_adb_invalid_url_or_revision(self):
        """tools/get-adb must exit non-zero cleanly when given an invalid revision or unreachable URL."""
        script = ROOT / "tools" / "get-adb"
        if not script.is_file():
            self.skipTest("tools/get-adb not yet created")

        with tempfile.TemporaryDirectory(prefix="zenlink_adb_bad_rev_") as tmpdir:
            dest = Path(tmpdir) / "platform-tools"
            res = subprocess.run(
                ["bash", str(script), str(dest), "999.999.999", "1111111111111111111111111111111111111111111111111111111111111111"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(res.returncode, 0, "tools/get-adb must exit non-zero on non-existent revision")
            self.assertFalse((dest / "adb").exists(), "adb must not be installed on 404 URL")

    def test_t2_03_ocr_empty_and_malformed_inputs(self):
        """zenlink/ocr.py must handle empty image, corrupt data, and invalid paths gracefully without crashes."""
        sys.path.insert(0, str(ROOT))
        try:
            from zenlink import ocr

            # 1. Zero bytes
            try:
                res = ocr.recognize_png(b"")
                self.assertIsInstance(res, list, "Zero-byte image should return list (empty)")
                self.assertEqual(res, [], "Zero-byte image should return []")
            except Exception as e:
                # If it raises, must not be unhandled Win32 crash
                self.assertNotIn("creationflags", str(e))
                self.assertNotIn("powershell.exe", str(e))

            # 2. Corrupted random garbage
            garbage = b"NOT_A_PNG_HEADER_RANDOM_DATA_1234567890" * 10
            try:
                res = ocr.recognize_png(garbage)
                self.assertIsInstance(res, list)
            except Exception as e:
                self.assertNotIn("creationflags", str(e))
                self.assertNotIn("powershell.exe", str(e))

            # 3. OcrSession merge edge cases
            self.assertEqual(ocr.merge([], []), ([], 0))
            self.assertEqual(ocr.merge(["line1"], []), (["line1"], 0))
            self.assertEqual(ocr.merge([], ["line1"]), (["line1"], 1))
            self.assertEqual(ocr.merge(["A", "B"], ["B", "C"]), (["A", "B", "C"], 1))
        finally:
            if str(ROOT) in sys.path:
                sys.path.remove(str(ROOT))

    def test_t2_04_get_adb_unicode_and_spaces_in_paths(self):
        """tools/get-adb must support destination directories with spaces, unicode, and emojis."""
        script = ROOT / "tools" / "get-adb"
        if not script.is_file():
            self.skipTest("tools/get-adb not yet created")

        with tempfile.TemporaryDirectory(prefix="zenlink_adb_unicode_") as tmpdir:
            unicode_dest = Path(tmpdir) / "sp ace" / "测试 🚀" / "platform-tools"
            res = subprocess.run(
                ["bash", str(script), str(unicode_dest), EXPECTED_DARWIN_ADB_REVISION, EXPECTED_DARWIN_ADB_SHA256],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(res.returncode, 0, f"Failed with unicode/spaces path: {res.stderr}\nstdout: {res.stdout}")
            self.assertTrue((unicode_dest / "adb").is_file(), f"adb executable missing in unicode path: {unicode_dest}")

    def test_t2_05_python_windows_imports_guarded(self):
        """Python modules importing Win32 APIs (winreg, ctypes.windll) must guard them on macOS."""
        # 1. zenlink.window
        win_py = (ROOT / "zenlink" / "window.py").read_text(encoding="utf-8")
        self.assertTrue(
            "ctypes.windll" not in win_py or "win32" in win_py or "try:" in win_py,
            "zenlink/window.py must guard ctypes.windll"
        )

        # 2. zenlink.apple.devices
        dev_py = (ROOT / "zenlink" / "apple" / "devices.py").read_text(encoding="utf-8")
        self.assertTrue(
            "import winreg" not in dev_py or "win32" in dev_py or "try:" in dev_py,
            "zenlink/apple/devices.py must guard import winreg"
        )

        # 3. zenlink.drivers.status
        stat_py = (ROOT / "zenlink" / "drivers" / "status.py").read_text(encoding="utf-8")
        self.assertTrue(
            "import winreg" not in stat_py or "win32" in stat_py or "try:" in stat_py,
            "zenlink/drivers/status.py must guard import winreg"
        )

        # 4. zenlink.__main__
        main_py = (ROOT / "zenlink" / "__main__.py").read_text(encoding="utf-8")
        self.assertTrue(
            "ctypes.windll" not in main_py or "win32" in main_py or "try:" in main_py,
            "zenlink/__main__.py must guard ctypes.windll"
        )

    def test_t2_06_windows_source_files_preserved(self):
        """Existing Windows developer files must not be deleted or modified to preserve Windows support."""
        for filename in ["tools/get-adb.ps1", "tools/ocr.ps1", "Start ZenLink.bat", "run.bat", "Uninstall-ZenLink.bat"]:
            p = ROOT / filename
            self.assertTrue(p.is_file(), f"Windows file {filename} must remain present")


# ==============================================================================
# Tier 3: Cross-Feature Combinations
# ==============================================================================

class TestTier3CrossFeatureCombinations(unittest.TestCase):
    """Tier 3: Inter-component contracts and cross-module interactions."""

    def test_t3_01_adb_download_to_find_adb_resolution(self):
        """tools/get-adb output path matches zenlink-app/src/android.rs find_adb() resolution."""
        # Check find_adb in zenlink-app
        android_rs = (ROOT / "rust" / "crates" / "zenlink-app" / "src" / "android.rs").read_text(encoding="utf-8")
        self.assertIn('let exe = if cfg!(windows) { "adb.exe" } else { "adb" };', android_rs,
                      "find_adb must search for 'adb' without .exe on macOS")
        self.assertIn('.join("third_party").join("platform-tools").join(exe)', android_rs,
                      "find_adb must search third_party/platform-tools")

        # Check that get-adb script default places adb at third_party/platform-tools/adb
        script = ROOT / "tools" / "get-adb"
        if script.is_file():
            content = script.read_text(encoding="utf-8")
            self.assertIn("third_party/platform-tools", content)

    def test_t3_02_ocr_sidecar_endpoint_flow(self):
        """zenlink.ocr.OcrSession must accept data URL captures without Windows 500 error."""
        sys.path.insert(0, str(ROOT))
        try:
            from zenlink import ocr

            session = ocr.OcrSession()
            # Valid 1x1 transparent PNG data URL
            tiny_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
                b"\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            data_url = "data:image/png;base64," + base64.b64encode(tiny_png).decode("ascii")

            res = session.add_capture(data_url)
            self.assertIsInstance(res, dict)
            self.assertTrue(res.get("ok"), "add_capture should return ok: True")
            self.assertIn("text", res)
            self.assertIn("read", res)

            cleared = session.clear()
            self.assertEqual(cleared, {"ok": True})
            self.assertEqual(session.lines, [])
        except (ValueError, FileNotFoundError) as e:
            self.fail(f"OCR session raised Windows runtime error on macOS: {e}")
        finally:
            if str(ROOT) in sys.path:
                sys.path.remove(str(ROOT))

    def test_t3_03_playfair_build_and_codesign(self):
        """native/playfair/build.sh must build libplayfair.dylib and sign it with codesign on macOS."""
        build_sh = ROOT / "native" / "playfair" / "build.sh"
        self.assertTrue(build_sh.is_file(), f"native/playfair/build.sh missing at {build_sh}")
        self.assertTrue(bool(build_sh.stat().st_mode & stat.S_IXUSR), "build.sh must be executable (+x)")

        # Verify build script executes and produces dylib
        res = subprocess.run(["bash", str(build_sh)], cwd=str(ROOT / "native" / "playfair"),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, f"native/playfair/build.sh failed: {res.stderr}\nstdout: {res.stdout}")

        dylib = ROOT / "zenlink" / "airplay" / "libplayfair.dylib"
        if not dylib.is_file():
            dylib = ROOT / "native" / "playfair" / "libplayfair.dylib"
        self.assertTrue(dylib.is_file(), f"Compiled libplayfair.dylib missing at {dylib}")

        # Check codesign verification
        cs = subprocess.run(["codesign", "-v", str(dylib)], capture_output=True, text=True)
        self.assertEqual(cs.returncode, 0, f"libplayfair.dylib has invalid signature: {cs.stderr}")

    def test_t3_04_sidecar_python_binary_resolution(self):
        """zenlink-core/src/sidecar.rs must locate .venv/bin/python on macOS alongside .venv/Scripts/python.exe."""
        sidecar_rs = (ROOT / "rust" / "crates" / "zenlink-core" / "src" / "sidecar.rs").read_text(encoding="utf-8")
        self.assertTrue(
            ".join(\"bin\").join(\"python\")" in sidecar_rs or "bin/python" in sidecar_rs,
            "sidecar.rs must check .venv/bin/python for macOS/POSIX virtual environments"
        )
        self.assertIn('up.join(".venv").join("Scripts").join("python.exe")', sidecar_rs,
                      "sidecar.rs must retain Windows Scripts/python.exe check")


# ==============================================================================
# Tier 4: Real-World Workload Scenarios
# ==============================================================================

class TestTier4RealWorldScenarios(unittest.TestCase):
    """Tier 4: End-to-end user workflows and full system integration scenarios."""

    def test_t4_01_developer_fresh_clone_bootstrap_simulation(self):
        """Simulate fresh clone developer workflow on macOS arm64: verify scripts, tool downloads, and ready state."""
        # 1. Scripts check
        for script in ["Start ZenLink.sh", "run.sh", "tools/get-adb", "rust/tools/build-window.sh"]:
            sp = ROOT / script
            self.assertTrue(sp.is_file(), f"Developer workflow requires {script}")
            self.assertTrue(bool(sp.stat().st_mode & stat.S_IXUSR), f"{script} must be executable (+x)")

        # 2. Host architecture check
        self.assertEqual(platform.system(), "Darwin", "Developer environment is macOS")
        self.assertEqual(platform.machine(), "arm64", "Target architecture is Apple Silicon (arm64)")

        # 3. Simulate adb download into a staging location
        script_adb = ROOT / "tools" / "get-adb"
        with tempfile.TemporaryDirectory(prefix="zenlink_clone_test_") as tmpdir:
            dest = Path(tmpdir) / "staging-platform-tools"
            res = subprocess.run(
                ["bash", str(script_adb), str(dest), EXPECTED_DARWIN_ADB_REVISION, EXPECTED_DARWIN_ADB_SHA256],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(res.returncode, 0, f"Developer get-adb failed: {res.stderr}")
            self.assertTrue((dest / "adb").is_file(), "adb must be ready for developer use")

    def test_t4_02_macos_runtime_contracts_and_paths(self):
        """Validate macOS filesystem conventions: ~/Library/Application Support and ~/Library/Logs."""
        # 1. zenlink/paths.py contract
        paths_py = (ROOT / "zenlink" / "paths.py").read_text(encoding="utf-8")
        self.assertIn("Library", paths_py, "zenlink/paths.py must support macOS ~/Library paths")
        self.assertIn("Application Support", paths_py,
                      "zenlink/paths.py must resolve ~/Library/Application Support on macOS")

        # 2. zenlink-core/src/lib.rs contract
        core_lib = (ROOT / "rust" / "crates" / "zenlink-core" / "src" / "lib.rs").read_text(encoding="utf-8")
        self.assertTrue(
            "Library" in core_lib or "dirs::" in core_lib or "cfg(target_os = \"macos\")" in core_lib,
            "zenlink-core local_data_dir() must resolve macOS Application Support directory"
        )

        # 3. zenlink-app/src/prefs.rs contract
        prefs_rs = (ROOT / "rust" / "crates" / "zenlink-app" / "src" / "prefs.rs").read_text(encoding="utf-8")
        self.assertTrue(
            "Library" in prefs_rs or "cfg(target_os = \"macos\")" in prefs_rs or "HOME" in prefs_rs,
            "zenlink-app prefs path() must resolve preferences directory on macOS"
        )

    def test_t4_03_video_view_macos_api_contract(self):
        """zenlink-video/src/macos.rs must satisfy complete VideoView trait/API contract from PROJECT.md."""
        macos_rs_path = ROOT / "rust" / "crates" / "zenlink-video" / "src" / "macos.rs"
        self.assertTrue(macos_rs_path.is_file(), f"macos.rs missing at {macos_rs_path}")
        code = macos_rs_path.read_text(encoding="utf-8")

        required_methods = [
            "pub fn new(",
            "pub fn set_bounds(",
            "pub fn set_holes(",
            "pub fn set_rotation(",
            "pub fn set_fit(",
            "pub fn set_crop(",
            "pub fn set_background(",
            "pub fn on_pointer(",
            "pub fn stats(",
            "pub fn start(",
            "pub fn start_source(",
            "pub fn stop(",
            "pub fn snapshot(",
            "pub fn decoder_available(",
            "pub fn media_foundation_present(",
        ]

        for method in required_methods:
            self.assertIn(method, code, f"zenlink-video/src/macos.rs is missing required API method: {method}")


# ==============================================================================
# Test Runner CLI
# ==============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="ZenLink macOS E2E Test Suite Runner")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run only tests from specified tier")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose test execution output")
    args, unknown = parser.parse_known_args()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    tier_map = {
        1: [TestTier1FeatureCoverage],
        2: [TestTier2BoundaryAndCornerCases],
        3: [TestTier3CrossFeatureCombinations],
        4: [TestTier4RealWorldScenarios],
    }

    if args.tier:
        classes = tier_map[args.tier]
        for cls in classes:
            suite.addTests(loader.loadTestsFromTestCase(cls))
    else:
        for classes in tier_map.values():
            for cls in classes:
                suite.addTests(loader.loadTestsFromTestCase(cls))

    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
