import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO = SKILL_ROOT.parents[1]
SCRIPT = REPO / "scripts" / "eta-skill-sync.sh"
SKILL = SKILL_ROOT / "SKILL.md"
STABLE = ("ITERATION", "BUILD", "MIGRATION", "CLOUD")
DYNAMIC = ("INDEX", "RULES", "LESSONS", "STATE")
SENTINEL = "PRIVATE-FIXTURE-CONTENT-DO-NOT-PRINT"


class EtaSkillSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.knowledge = self.root / "knowledge"
        self.references = self.root / "skills" / "eta-project-maintainer" / "references"
        self.knowledge.mkdir()
        self.references.mkdir(parents=True)
        scripts = self.root / "scripts"
        scripts.mkdir()
        self.script = scripts / SCRIPT.name
        shutil.copyfile(SCRIPT, self.script)
        for name in STABLE + DYNAMIC:
            (self.knowledge / f"{name}.md").write_text(f"{name}: {SENTINEL}\n", encoding="utf-8")
            (self.references / f"{name}.md").write_text(f"old {name}\n", encoding="utf-8")
        (self.references / "EXAMPLES.md").write_text("hand-written examples\n", encoding="utf-8")
        (self.references / "USER.md").write_text("user file\n", encoding="utf-8")

    def run_sync(self, *args):
        return subprocess.run(["sh", str(self.script), *args], text=True, capture_output=True)

    def file_state(self):
        return {
            path.name: (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            for path in self.references.iterdir() if path.is_file()
        }

    def test_check_reports_hashes_without_writes_or_content(self):
        before = self.file_state()
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.file_state(), before)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        for name in STABLE + DYNAMIC:
            digest = hashlib.sha256((self.knowledge / f"{name}.md").read_bytes()).hexdigest()
            self.assertIn(f"source=knowledge/{name}.md source_sha256={digest}", result.stdout)
            self.assertIn(f"target=references/{name}.md", result.stdout)
        self.assertEqual(result.stdout.count("status=differs"), 8)

    def test_sync_creates_stable_snapshots_and_dynamic_routes_only(self):
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        for name in STABLE:
            self.assertEqual((self.references / f"{name}.md").read_bytes(),
                             (self.knowledge / f"{name}.md").read_bytes())
        for name in DYNAMIC:
            route = (self.references / f"{name}.md").read_text(encoding="utf-8")
            self.assertIn(f"F:/eta/02-工程知识库/knowledge/{name}.md", route)
            self.assertIn(f"/mnt/f/eta/02-工程知识库/knowledge/{name}.md", route)
            self.assertIn(f"/workspace/projects/eta-local/knowledge/{name}.md", route)
            self.assertIn(f"/data/local/tmp/eta/projects/eta-local/knowledge/{name}.md", route)
            self.assertIn("旧手机路径仅在实际存在时使用", route)
            self.assertNotIn(SENTINEL, route)
            self.assertLess(len(route.encode()), 1000)
        self.assertEqual((self.references / "EXAMPLES.md").read_text(), "hand-written examples\n")
        self.assertEqual((self.references / "USER.md").read_text(), "user file\n")
        checked = self.run_sync("--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(checked.stdout.count("status=current"), 8)

    def test_repeated_update_does_not_replace_current_files(self):
        self.assertEqual(self.run_sync().returncode, 0)
        before = self.file_state()
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.file_state(), before)

    def test_source_changes_affect_snapshots_but_not_routes(self):
        self.assertEqual(self.run_sync().returncode, 0)
        old_route = (self.references / "STATE.md").read_bytes()
        (self.knowledge / "STATE.md").write_text("new private state\n", encoding="utf-8")
        check = self.run_sync("--check")
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("route STATE", check.stdout)
        self.assertNotIn("new private state", check.stdout)
        (self.knowledge / "CLOUD.md").write_text("new stable cloud handbook\n", encoding="utf-8")
        self.assertEqual(self.run_sync("--check").returncode, 1)
        self.assertEqual(self.run_sync().returncode, 0)
        self.assertEqual((self.references / "CLOUD.md").read_text(), "new stable cloud handbook\n")
        self.assertEqual((self.references / "STATE.md").read_bytes(), old_route)
        self.assertEqual(self.run_sync("--check").returncode, 0)

    def test_missing_source_fails_before_any_writes(self):
        (self.knowledge / "CLOUD.md").unlink()
        before = self.file_state()
        for args in ((), ("--check",)):
            result = self.run_sync(*args)
            self.assertEqual(result.returncode, 2)
            self.assertIn("knowledge/CLOUD.md", result.stderr)
            self.assertEqual(self.file_state(), before)

    def test_empty_source_fails_before_any_writes(self):
        (self.knowledge / "STATE.md").write_bytes(b"")
        before = self.file_state()
        result = self.run_sync()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.file_state(), before)

    def test_target_symlink_is_rejected_before_writes(self):
        external = self.root / "outside"
        external.write_text("do not touch\n")
        link = self.references / "STATE.md"
        link.unlink()
        link.symlink_to(external)
        before = self.file_state()
        result = self.run_sync()
        self.assertEqual(result.returncode, 2)
        self.assertIn("references/STATE.md", result.stderr)
        self.assertEqual(self.file_state(), before)
        self.assertEqual(external.read_text(), "do not touch\n")
        self.assertTrue(link.is_symlink())

    def test_unknown_target_directory_and_missing_references_are_rejected(self):
        target = self.references / "CLOUD.md"
        target.unlink()
        target.mkdir()
        before = self.file_state()
        result = self.run_sync()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.file_state(), before)
        target.rmdir()
        shutil.rmtree(self.references)
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.references.exists())

    def test_update_preserves_target_mode_and_creates_missing_target(self):
        target = self.references / "BUILD.md"
        target.chmod(0o640)
        (self.references / "CLOUD.md").unlink()
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertEqual((self.references / "CLOUD.md").stat().st_mode & 0o777, 0o644)

    def test_metadata_front_loads_local_and_conditional_cloud(self):
        lines = SKILL.read_text(encoding="utf-8").splitlines()
        description = next(line.removeprefix("description: ") for line in lines
                           if line.startswith("description: "))
        self.assertIn("Eta", description[:180])
        self.assertIn("本地验证优先", description[:180])
        self.assertIn("云检查或构建按当次任务需要", description[:180])
        self.assertNotIn("GitHub 构建", description[:180])

    def test_invalid_arguments_do_not_modify_files(self):
        before = self.file_state()
        for args in (("--invalid",), ("--check", "extra"), ("--help", "extra")):
            result = self.run_sync(*args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(self.file_state(), before)
        self.assertEqual(self.run_sync("--help").returncode, 0)


if __name__ == "__main__":
    unittest.main()
