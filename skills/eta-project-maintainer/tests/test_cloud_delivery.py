"""Offline only: no GitHub requests, APK build, installation or real credentials."""
import argparse
import importlib.util
import json
import subprocess
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('eta_cloud_delivery', Path(__file__).parents[1] / 'scripts/cloud_delivery.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
HEAD = '1' * 40
SOURCE = '2' * 40


def pr(merged=False):
    return {'head': {'sha': HEAD, 'ref': 'feat/example', 'repo': {'full_name': m.REPO}},
            'base': {'ref': 'local', 'repo': {'full_name': m.REPO}},
            'state': 'closed' if merged else 'open', 'merged': merged, 'merge_commit_sha': SOURCE if merged else None}


def run(sha=SOURCE, branch='local', event='push', conclusion='success'):
    return {'id': 100, 'head_sha': sha, 'head_branch': branch, 'event': event,
            'status': 'completed', 'conclusion': conclusion}


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = argparse.Namespace(pr=8, head=HEAD, version='3.4.0', label='功能测试',
            receipt_dir=self.root / 'receipts', merge_approved=False, interval=60, timeout=60,
            downloads=self.root / 'Downloads', apksigner_jar=self.root / 'signer.jar', aapt=self.root / 'aapt2')
        self.args.apksigner_jar.touch()
        self.args.aapt.touch()

    def artifact(self, name, size=123):
        return {'name': name, 'expired': False, 'size_in_bytes': size,
                'archive_download_url': 'https://api.github.com/repos/example/test/actions/artifacts/1/zip'}

    def test_get_eof_recovers_with_bounded_retries(self):
        error = subprocess.CalledProcessError(1, ['gh'], stderr='network EOF')
        with patch.object(m, 'gh', side_effect=[error, '{"ok":true}']) as request, patch.object(m.time, 'sleep'):
            self.assertEqual({'ok': True}, m.api('pulls/8'))
            self.assertEqual(2, request.call_count)
            self.assertTrue(all(c.args[:3] == ('api', '--method', 'GET') for c in request.call_args_list))
        with patch.object(m, 'gh', side_effect=error) as request, patch.object(m.time, 'sleep'):
            with self.assertRaises(m.DeliveryError):
                m.api('pulls/8')
            self.assertEqual(3, request.call_count)

    def test_get_permission_failure_is_not_retried(self):
        error = subprocess.CalledProcessError(1, ['gh'], stderr='HTTP 403 forbidden')
        with patch.object(m, 'gh', side_effect=error) as request:
            with self.assertRaises(m.DeliveryError):
                m.api('pulls/8')
            self.assertEqual(1, request.call_count)

    def test_pr_identity_rejects_changed_head_base_and_repository(self):
        for location, field, value in [('head', 'sha', '3' * 40), ('base', 'ref', 'main')]:
            value_pr = pr()
            value_pr[location][field] = value
            with self.assertRaises(m.DeliveryError):
                m.validate_pr(value_pr, HEAD)
        value_pr = pr()
        value_pr['head']['repo']['full_name'] = 'other/fork'
        with self.assertRaises(m.DeliveryError):
            m.validate_pr(value_pr, HEAD)

    def test_exact_run_only_uses_requested_sha_branch_and_event(self):
        good = run()
        bad = [run('3' * 40), run(branch='main'), run(event='workflow_dispatch')]
        for index, r in enumerate(bad):
            r['id'] += index + 1
        self.assertIs(good, m.pick_run([good] + bad, SOURCE, 'local', 'push'))
        self.assertIsNone(m.pick_run(bad, SOURCE, 'local', 'push'))

    def test_required_jobs_cannot_be_missing_skipped_or_partial(self):
        for data in [{'jobs': []}, {'jobs': [{'name': m.PR_JOB, 'conclusion': 'skipped'}]},
                     {'total_count': 2, 'jobs': [{'name': m.PR_JOB, 'conclusion': 'success'}]}]:
            with patch.object(m, 'api', return_value=data), self.assertRaises(m.DeliveryError):
                m.verify_jobs({'id': 1}, {m.PR_JOB})

    def test_lost_merge_response_is_read_back_not_replayed(self):
        error = subprocess.CalledProcessError(1, ['gh'], stderr='EOF')
        with patch.object(m, 'gh', side_effect=error) as write, patch.object(m, 'api', return_value=pr(True)):
            self.assertEqual(SOURCE, m.merge_once(8, HEAD))
            self.assertEqual(1, write.call_count)
            self.assertIn(f'sha={HEAD}', write.call_args.args)
        with patch.object(m, 'gh', side_effect=error) as write, patch.object(m, 'api', return_value=pr(False)):
            with self.assertRaises(m.DeliveryError):
                m.merge_once(8, HEAD)
            self.assertEqual(1, write.call_count)

    def test_no_merge_without_this_tasks_explicit_flag(self):
        check = run(HEAD, 'feat/example', 'pull_request')
        with patch.object(m, 'api', side_effect=[pr(), {'workflow_runs': [check]}]), \
             patch.object(m, 'verify_jobs'), patch.object(m, 'merge_once') as merge, \
             patch.object(m.time, 'monotonic', side_effect=[1, 11]), patch.object(m.time, 'sleep'):
            with self.assertRaises(m.DeliveryError):
                m.wait_pr(self.args, 10)
            merge.assert_not_called()

    def test_merged_pr_resumes_without_merging_or_rerunning_ci(self):
        with patch.object(m, 'api', return_value=pr(True)) as read, patch.object(m, 'merge_once') as merge:
            self.assertEqual(SOURCE, m.wait_pr(self.args, float('inf')))
            self.assertEqual(1, read.call_count)
            merge.assert_not_called()

    def test_failed_build_stops_without_dispatch(self):
        with patch.object(m, 'api', return_value={'workflow_runs': [run(conclusion='failure')]}), \
             patch.object(m, 'gh') as mutation:
            with self.assertRaises(m.DeliveryError):
                m.wait_build(self.args, SOURCE, float('inf'))
            mutation.assert_not_called()

    def test_missing_expired_or_duplicate_pair_is_not_deliverable(self):
        names = m.artifact_names('3.4.0', SOURCE)
        artifacts = [self.artifact(n) for n in names]
        self.assertEqual(2, len(m.select_artifacts({'artifacts': artifacts}, names)))
        for bad in [artifacts[:1], artifacts + artifacts[:1],
                    [dict(artifacts[0], expired=True), artifacts[1]]]:
            with self.assertRaises(m.DeliveryError):
                m.select_artifacts({'artifacts': bad}, names)

    def test_redirect_drops_authorization_across_hosts(self):
        request = urllib.request.Request('https://api.github.com/file', headers={'Authorization': 'test-placeholder'})
        request.add_unredirected_header('Authorization', 'test-placeholder')
        result = m.SafeRedirect().redirect_request(request, None, 302, '', {}, 'https://example.org/file')
        self.assertFalse(any(k.lower() == 'authorization' for k, _ in result.header_items()))
        with self.assertRaises(m.DeliveryError):
            m.SafeRedirect().redirect_request(request, None, 302, '', {}, 'http://example.org/file')

    def make_apk(self, path):
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('AndroidManifest.xml', b'fixture')

    def verified_output(self, debug=False, version=None):
        version = version or ('3.4.0-debug+2222222' if debug else '3.4.0+2222222')
        return ['-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----',
                'sha256 Fingerprint=' + m.CERT,
                f"package: name='{m.PACKAGE}' versionCode='1' versionName='{version}'"]

    def test_verify_certificate_and_exact_variant_version(self):
        path = self.root / 'fixture.apk'
        self.make_apk(path)
        for debug in (False, True):
            with patch.object(m.subprocess, 'check_output', side_effect=self.verified_output(debug)):
                result = m.verify_apk(path, 'debug' if debug else 'release', SOURCE, self.args)
                self.assertEqual(m.CERT, result['certificate_sha256'])
        with patch.object(m.subprocess, 'check_output', side_effect=self.verified_output(version='3.4.0+3333333')):
            with self.assertRaises(m.DeliveryError):
                m.verify_apk(path, 'release', SOURCE, self.args)
        bad = self.verified_output()
        bad[1] = 'sha256 Fingerprint=' + '0' * 64
        with patch.object(m.subprocess, 'check_output', side_effect=bad), self.assertRaises(m.DeliveryError):
            m.verify_apk(path, 'release', SOURCE, self.args)

    def test_artifact_wrapper_is_not_accepted_as_apk(self):
        path = self.root / 'wrapper.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('release.apk', b'not-a-real-apk')
        with self.assertRaises(m.DeliveryError):
            m.verify_apk(path, 'release', SOURCE, self.args)

    def test_failed_download_preserves_old_file_and_cleans_partial(self):
        artifact = self.artifact('release.apk')
        final = self.root / 'release.apk'
        final.write_bytes(b'old')
        def broken_download(a, target):
            target.write_bytes(b'partial')
            raise OSError('interrupted')
        with patch.object(m, 'download', side_effect=broken_download), self.assertRaises(OSError):
            m.obtain_apk(artifact, self.root, 'release', SOURCE, self.args)
        self.assertEqual(b'old', final.read_bytes())
        self.assertFalse(final.with_suffix('.part').exists())

    def test_verified_existing_apk_is_reused_without_download(self):
        artifact = self.artifact('release.apk', size=3)
        (self.root / 'release.apk').write_bytes(b'old')
        with patch.object(m, 'verify_apk', return_value={'sha256': 'fixture'}), patch.object(m, 'download') as download:
            m.obtain_apk(artifact, self.root, 'release', SOURCE, self.args)
            download.assert_not_called()

    def test_latest_entry_not_updated_before_both_apks(self):
        dest = self.args.downloads / 'task-2222222'
        dest.mkdir(parents=True)
        latest = dest.parent / '最新测试包.txt'
        latest.write_text('old')
        with self.assertRaises(m.DeliveryError):
            m.publish_delivery(self.args, SOURCE, run(), [], dest)
        self.assertEqual('old', latest.read_text())

    def test_invalid_head_or_directory_label_rejected(self):
        common = ['--pr', '8', '--version', '3.4.0', '--receipt-dir', str(self.root)]
        for head, label in [('short', 'task'), (HEAD, '../escape')]:
            with patch('sys.stderr'), self.assertRaises(SystemExit):
                m.parse_args(common + ['--head', head, '--label', label])

    def test_missing_verifier_stops_before_any_remote_read_or_merge(self):
        argv = ['--pr', '8', '--head', HEAD, '--version', '3.4.0', '--label', 'task',
                '--receipt-dir', str(self.args.receipt_dir), '--apksigner-jar', str(self.root / 'missing.jar'),
                '--aapt', str(self.args.aapt), '--merge-approved']
        with patch.object(m, 'api') as read, patch.object(m, 'gh') as write:
            self.assertEqual(1, m.main(argv))
            read.assert_not_called()
            write.assert_not_called()
        self.assertTrue((self.args.receipt_dir / 'delivery-failure.json').exists())

    def test_truncated_artifact_transfer_fails_size_check(self):
        import io
        artifact = self.artifact('release.apk', size=3)
        with patch.object(m, 'gh', return_value='test-placeholder'), patch.object(m.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value = io.BytesIO(b'12')
            with self.assertRaises(m.DeliveryError):
                m.download(artifact, self.root / 'partial.apk')
        artifact['archive_download_url'] = 'https://example.org/foreign'
        with patch.object(m, 'gh') as auth, self.assertRaises(m.DeliveryError):
            m.download(artifact, self.root / 'other.apk')
        auth.assert_not_called()

    def test_full_offline_delivery_and_restart_do_not_duplicate_writes_or_downloads(self):
        names = m.artifact_names('3.4.0', SOURCE)
        sample = self.root / 'sample.apk'
        self.make_apk(sample)
        artifacts = [self.artifact(n, sample.stat().st_size) for n in names]
        def fake_api(path):
            if path == 'pulls/8':
                return pr(True)
            if path.startswith('actions/workflows/android-release.yml/runs?'):
                return {'workflow_runs': [run()]}
            if path == 'actions/runs/100/jobs?per_page=100':
                return {'jobs': [{'name': n, 'conclusion': 'success'} for n in m.BUILD_JOBS]}
            if path == 'actions/runs/100/artifacts?per_page=100':
                return {'artifacts': artifacts}
            raise AssertionError('unexpected network path: ' + path)
        def fake_download(artifact, target):
            target.write_bytes(sample.read_bytes())
        def fake_verify(path, variant, sha, args):
            return {'sha256': 'fixture-digest', 'bytes': path.stat().st_size, 'certificate_sha256': m.CERT}
        argv = ['--pr', '8', '--head', HEAD, '--version', '3.4.0', '--label', 'task',
                '--receipt-dir', str(self.args.receipt_dir), '--downloads', str(self.args.downloads),
                '--apksigner-jar', str(self.args.apksigner_jar), '--aapt', str(self.args.aapt)]
        with patch.object(m, 'api', side_effect=fake_api), patch.object(m, 'gh') as write, \
             patch.object(m, 'download', side_effect=fake_download) as download, patch.object(m, 'verify_apk', side_effect=fake_verify):
            self.assertEqual(0, m.main(argv))
            self.assertEqual(2, download.call_count)
            self.assertEqual(0, m.main(argv))
            self.assertEqual(2, download.call_count)
            write.assert_not_called()
        report = json.loads((self.args.receipt_dir / 'delivery.json').read_text())
        self.assertEqual(SOURCE, report['source'])
        self.assertFalse(report['installed'])
        self.assertFalse(report['user_accepted'])
        self.assertIn('2222222', (self.args.downloads / '最新测试包.txt').read_text())


if __name__ == '__main__':
    unittest.main()
