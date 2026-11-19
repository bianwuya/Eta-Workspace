"""Offline QA provenance/download regression; no GitHub, keys, build or install."""
import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1] / 'scripts'

def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

c, q = load('cloud_delivery'), load('qa_delivery')
HEAD, SOURCE, BASE = '1' * 40, '2' * 40, '3' * 40


class QaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.args = argparse.Namespace(pr=24, head=HEAD, version='3.4.0', label='GUI-P0',
            receipt_dir=self.root / 'receipts', merge_approved=False, qa_run=200,
            downloads=self.root / 'Downloads', interval=60,
            apksigner_jar=self.root/'signer.jar', aapt=self.root/'aapt2')
        self.args.receipt_dir.mkdir()
        self.sign = dict(id=200, run_attempt=1, path='.github/workflows/device-test-apk.yml',
                         head_branch='local', event='workflow_run', status='completed', conclusion='success')
        self.pr = {'head': {'sha': HEAD, 'ref': 'feat/p0', 'repo': {'full_name': c.REPO}},
                   'base': {'ref': 'local', 'sha':BASE, 'repo': {'full_name': c.REPO}}, 'state': 'open', 'merged': False}
        self.receipt = dict(schema_version=1, channel='pr-qa', repository=c.REPO,
            pr_number=24, feature_head_sha=HEAD, base_sha=BASE, source_sha=SOURCE,
            check_run_id=100, check_run_attempt=1, sign_run_id=200, sign_run_attempt=1,
            apks=[dict(variant=v, file_name=n, bytes=3, sha256=hashlib.sha256(b'apk').hexdigest(),
                       certificate_sha256=c.CERT) for n, v in c.artifact_names('3.4.0', SOURCE, qa=True).items()])

    def bundle(self, names=None):
        p = self.root / 'proof.zip'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('qa-receipt.json', json.dumps(self.receipt))
            z.writestr('REVIEW-CONTEXT.md', 'Task: PR24, excludes P1')
            for name in names or []:
                z.writestr(name, 'unexpected')
        return p

    def test_receipt_requires_exact_source_pr_head_run_attempt_and_variant(self):
        self.assertEqual(2, len(q.validate_receipt(self.receipt, self.args, self.sign, c)))
        for key, value in [('feature_head_sha', '4'*40), ('pr_number', 2),
                           ('sign_run_id', 300), ('sign_run_attempt', 2), ('source_sha', 'short')]:
            with self.subTest(key=key), self.assertRaises(c.DeliveryError):
                q.validate_receipt(dict(self.receipt, **{key:value}), self.args, self.sign, c)
        bad = json.loads(json.dumps(self.receipt))
        bad['apks'][1]['variant'] = bad['apks'][0]['variant']
        with self.assertRaises(c.DeliveryError): q.validate_receipt(bad, self.args, self.sign, c)

    def test_bounded_proof_rejects_extra_duplicate_and_traversal_paths(self):
        self.assertEqual(self.receipt, q.read_proof(self.bundle(), c)[0])
        for extra in ['../escape', 'nested/qa-receipt.json', 'other.txt']:
            with self.assertRaises(c.DeliveryError): q.read_proof(self.bundle([extra]), c)
        with zipfile.ZipFile(self.root / 'large.zip', 'w') as z:
            z.writestr('qa-receipt.json', json.dumps(self.receipt))
            z.writestr('REVIEW-CONTEXT.md', 'x' * (q.TEXT_LIMIT + 1))
        with self.assertRaises(c.DeliveryError): q.read_proof(self.root / 'large.zip', c)

    def fake_api(self, path):
        if path == 'pulls/24': return self.pr
        if path == 'actions/runs/200': return self.sign
        if path == 'actions/runs/100':
            return dict(id=100, path='.github/workflows/pr-check.yml', head_sha=HEAD,
                        head_branch='feat/p0', event='pull_request', run_attempt=1,
                        status='completed', conclusion='success')
        if path == f'git/commits/{SOURCE}': return {'parents':[{'sha': BASE}, {'sha': HEAD}]}
        if path.endswith('/jobs?per_page=100'):
            name = q.SIGN_JOB if '/200/' in path else c.PR_JOB
            return {'jobs': [{'name': name, 'conclusion':'success'}]}
        raise AssertionError(path)

    def test_runs_reject_wrong_source_parent_and_untrusted_sign_branch(self):
        with patch.object(c, 'api', side_effect=self.fake_api):
            q.validate_runs(self.receipt, self.args, self.sign, c)
        for key, value in [('head_branch','feat/other'), ('event','pull_request'), ('path','other.yml')]:
            with self.assertRaises(c.DeliveryError):
                q.validate_runs(self.receipt, self.args, dict(self.sign, **{key:value}), c)
        def bad_parent(path):
            return {'parents':[{'sha': HEAD}]} if path.startswith('git/commits/') else self.fake_api(path)
        with patch.object(c, 'api', side_effect=bad_parent), self.assertRaises(c.DeliveryError):
            q.validate_runs(self.receipt, self.args, self.sign, c)
        self.pr['base']['sha']='4'*40
        def changed_base(path):
            if path.startswith('compare/'):
                return {'status':'diverged','merge_base_commit':{'sha':'5'*40}}
            return self.fake_api(path)
        with patch.object(c, 'api', side_effect=changed_base), self.assertRaises(c.DeliveryError):
            q.validate_runs(self.receipt, self.args, self.sign, c)

    def test_concurrent_local_advance_keeps_exact_checked_qa_snapshot_usable(self):
        self.pr['base']['sha']='4'*40
        def changed_base(path):
            if path.startswith('compare/'):
                return {'status':'ahead','merge_base_commit':{'sha':BASE}}
            return self.fake_api(path)
        with patch.object(c,'api',side_effect=changed_base):
            q.validate_runs(self.receipt,self.args,self.sign,c)

    def test_qa_args_cannot_merge_and_uses_separate_latest_pointer(self):
        common=['--pr','24','--head',HEAD,'--version','3.4.0','--label','p0',
                '--receipt-dir',str(self.args.receipt_dir),'--qa-run','200']
        with patch('sys.stderr'), self.assertRaises(SystemExit): c.parse_args(common+['--merge-approved'])
        self.args.qa_receipt = self.receipt
        dest=self.args.downloads/'qa'
        dest.mkdir(parents=True)
        (self.args.downloads/'最新测试包.txt').write_text('stable')
        rows=[{'path':str(dest/r['file_name']), 'sha256':r['sha256']} for r in self.receipt['apks']]
        c.publish_delivery(self.args,SOURCE,self.sign,rows,dest)
        self.assertEqual('stable',(self.args.downloads/'最新测试包.txt').read_text())
        self.assertTrue((self.args.downloads/'最新QA-PR24.txt').exists())
        data=json.loads((dest/'交付回执.json').read_text())
        self.assertFalse(data['merged']); self.assertFalse(data['installed'])
        self.assertEqual(self.receipt,data['qa_provenance'])

    def test_qa_version_still_verifies_existing_certificate_and_actual_source(self):
        apk=self.root/'sample.apk'
        with zipfile.ZipFile(apk,'w') as z: z.writestr('AndroidManifest.xml','fixture')
        for variant in ['debug','release']:
            version='3.4.0'+('-debug' if variant=='debug' else '')+'+qa-2222222'
            output=['-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----',
                    'SHA256 Fingerprint='+c.CERT,
                    f"package: name='{c.PACKAGE}' versionName='{version}'"]
            with patch.object(c.subprocess,'check_output',side_effect=output):
                self.assertEqual(version,c.verify_apk(apk,variant,SOURCE,self.args)['version_name'])

    def test_complete_qa_download_does_not_merge_dispatch_or_touch_stable_pointer(self):
        proof=self.bundle().read_bytes()
        artifacts=[dict(name=r['file_name'],size_in_bytes=3,expired=False) for r in self.receipt['apks']]
        artifacts.append(dict(name='qa-proof-100',size_in_bytes=len(proof),expired=False))
        def api(path):
            if path=='actions/runs/200/artifacts?per_page=100': return {'artifacts':artifacts}
            return self.fake_api(path)
        def download(a,path): path.write_bytes(proof)
        def obtain(a,dest,variant,source,args):
            return {'path':str(dest/a['name']),'sha256':hashlib.sha256(b'apk').hexdigest(),'bytes':3,
                    'certificate_sha256':c.CERT}
        with patch.object(c,'api',side_effect=api), patch.object(c,'download',side_effect=download), \
             patch.object(c,'obtain_apk',side_effect=obtain), patch.object(c,'gh') as mutation:
            dest=q.deliver(self.args,float('inf'),c)
            mutation.assert_not_called()
        self.assertEqual('pr-qa',json.loads((dest/'交付回执.json').read_text())['channel'])
        self.assertTrue((dest/'REVIEW-CONTEXT.md').exists())
        self.assertFalse((self.args.downloads/'最新测试包.txt').exists())


if __name__=='__main__': unittest.main()
