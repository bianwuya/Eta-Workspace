"""Read-only QA channel for cloud_delivery.py; shares its download and APK verifier."""
import json
import re
import zipfile
from pathlib import Path

PROOF_LIMIT = 2 * 1024 * 1024
TEXT_LIMIT = 1024 * 1024
SIGN_JOB = 'Verify source and sign QA APKs'


def require(condition, message, core):
    if not condition:
        raise core.DeliveryError(message)


def validate_receipt(receipt, args, sign_run, core):
    require(isinstance(receipt, dict), 'QA receipt must be an object', core)
    require(receipt.get('schema_version') == 1 and receipt.get('channel') == 'pr-qa',
            'Unsupported QA receipt schema/channel', core)
    require(receipt.get('repository') == core.REPO and receipt.get('pr_number') == args.pr
            and receipt.get('feature_head_sha') == args.head,
            'QA receipt does not identify the requested repository/PR/head', core)
    require(receipt.get('sign_run_id') == sign_run['id']
            and receipt.get('sign_run_attempt') == sign_run.get('run_attempt', 1),
            'QA receipt points at another signing run or attempt', core)
    for key in ('source_sha', 'base_sha'):
        require(bool(re.fullmatch(r'[0-9a-f]{40}', str(receipt.get(key, '')))),
                'QA receipt lacks an exact source/base SHA', core)
    require(type(receipt.get('check_run_id')) is int and receipt['check_run_id'] > 0
            and type(receipt.get('check_run_attempt')) is int and receipt['check_run_attempt'] > 0,
            'QA receipt lacks a check run identity', core)
    rows = receipt.get('apks')
    require(isinstance(rows, list) and len(rows) == 2, 'QA receipt needs exactly two APKs', core)
    expected = core.artifact_names(args.version, receipt['source_sha'], qa=True)
    require({r.get('file_name') for r in rows if isinstance(r, dict)} == set(expected),
            'QA receipt APK names do not match exact source and standard variants', core)
    for row in rows:
        require(isinstance(row, dict) and row.get('variant') == expected.get(row.get('file_name'))
                and row.get('certificate_sha256') == core.CERT
                and type(row.get('bytes')) is int and 0 < row['bytes'] <= core.MAX_APK_BYTES
                and bool(re.fullmatch(r'[0-9a-f]{64}', str(row.get('sha256', '')))),
                'QA receipt contains an invalid APK identity', core)
    return rows


def read_proof(path, core):
    try:
        with zipfile.ZipFile(path) as bundle:
            info = bundle.infolist()
            require(len(info) == 2 and {i.filename for i in info} == {'qa-receipt.json', 'REVIEW-CONTEXT.md'},
                    'QA proof has unexpected, duplicate, nested or unsafe paths', core)
            require(all(0 < i.file_size <= (65536 if i.filename == 'qa-receipt.json' else TEXT_LIMIT) and not i.is_dir()
                        and ((i.external_attr >> 16) & 0o170000) != 0o120000 for i in info),
                    'QA proof contains oversized text or a symlink', core)
            receipt = json.loads(bundle.read('qa-receipt.json').decode('utf-8'))
            context = bundle.read('REVIEW-CONTEXT.md').decode('utf-8')
            return receipt, context
    except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError):
        raise core.DeliveryError('QA proof is not a valid bounded UTF-8 receipt bundle') from None


def validate_runs(receipt, args, sign_run, core):
    require(sign_run.get('path') == '.github/workflows/device-test-apk.yml'
            and sign_run.get('head_branch') == 'local'
            and sign_run.get('event') in ('workflow_run', 'workflow_dispatch'),
            'Signing run is not the trusted local QA workflow', core)
    core.verify_jobs(sign_run, {SIGN_JOB})
    pr = core.api(f'pulls/{args.pr}')
    core.validate_pr(pr, args.head)
    require(not pr['merged'] and pr['state'] == 'open', 'QA PR is no longer open', core)
    validate_base(receipt, pr, core)
    check = core.api(f"actions/runs/{receipt['check_run_id']}")
    require(check.get('path') == '.github/workflows/pr-check.yml'
            and check.get('head_sha') == args.head and check.get('head_branch') == pr['head']['ref']
            and check.get('event') == 'pull_request'
            and check.get('run_attempt', 1) == receipt['check_run_attempt']
            and check.get('status') == 'completed' and check.get('conclusion') == 'success',
            'QA check run is stale, incomplete, failed or unrelated', core)
    core.verify_jobs(check, {core.PR_JOB})
    commit = core.api(f"git/commits/{receipt['source_sha']}")
    parents = [p['sha'] for p in commit.get('parents', [])]
    require(parents == [receipt['base_sha'], args.head],
            'QA source is not the recorded PR merge candidate', core)


def validate_base(receipt, pr, core):
    if pr['base']['sha'] != receipt['base_sha']:
        comparison = core.api(f"compare/{receipt['base_sha']}...{pr['base']['sha']}")
        require(comparison.get('status') in ('ahead', 'identical')
                and comparison.get('merge_base_commit', {}).get('sha') == receipt['base_sha'],
                'Recorded QA base is no longer in local history', core)


def wait_signing(args, deadline, core):
    last = None
    while core.time.monotonic() < deadline:
        run = core.api(f'actions/runs/{args.qa_run}')
        require(run.get('id') == args.qa_run, 'Unexpected signing run ID', core)
        state = (run.get('status'), run.get('conclusion'))
        if state != last:
            print('QA signing:', state, flush=True)
            core.save(args.receipt_dir / 'qa-progress.json', {'run_id': args.qa_run, 'state': state})
            last = state
        if state[0] == 'completed':
            require(state[1] == 'success', 'QA signing run did not succeed', core)
            return run
        core.time.sleep(args.interval)
    raise core.DeliveryError('QA wait expired; no merge, dispatch or duplicate build was started')


def deliver(args, deadline, core):
    """Caller has already checked verifier availability. Never mutates GitHub."""
    require(not args.merge_approved, 'QA delivery cannot merge', core)
    run = wait_signing(args, deadline, core)
    data = core.api(f"actions/runs/{run['id']}/artifacts?per_page=100")
    all_artifacts = data.get('artifacts', [])
    require(data.get('total_count', len(all_artifacts)) <= len(all_artifacts), 'QA artifact listing incomplete', core)
    # A run can only attest one source-check identity. No selection by newest filename.
    proofs = [a for a in all_artifacts if a.get('name', '').startswith('qa-proof-') and not a.get('expired')]
    require(len(proofs) == 1 and type(proofs[0].get('size_in_bytes')) is int
            and 0 < proofs[0]['size_in_bytes'] <= PROOF_LIMIT, 'Missing/duplicate/oversized QA proof', core)
    proof_path = args.receipt_dir / 'qa-proof.zip'
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    core.download(proofs[0], proof_path)
    receipt, context = read_proof(proof_path, core)
    rows = validate_receipt(receipt, args, run, core)
    require(proofs[0]['name'] == f"qa-proof-{receipt['check_run_id']}", 'QA proof artifact identity mismatch', core)
    validate_runs(receipt, args, run, core)
    names = core.artifact_names(args.version, receipt['source_sha'], qa=True)
    artifacts = core.select_artifacts(data, names)
    by_name = {a['name']: a for a in artifacts}
    for row in rows:
        require(by_name[row['file_name']]['size_in_bytes'] == row['bytes'], 'QA APK size/receipt mismatch', core)
    dest = args.downloads / (args.label + '-QA-' + receipt['source_sha'][:7])
    dest.mkdir(parents=True, exist_ok=True)
    verified = []
    for row in sorted(rows, key=lambda r: r['file_name']):
        metadata = core.obtain_apk(by_name[row['file_name']], dest, row['variant'], receipt['source_sha'], args)
        require(metadata['sha256'] == row['sha256'] and metadata['bytes'] == row['bytes'],
                'Downloaded signed APK does not match the QA receipt', core)
        verified.append(metadata)
    # Downloads may take time. A new head must not become an apparently current delivery.
    current = core.api(f'pulls/{args.pr}')
    core.validate_pr(current, args.head)
    require(not current['merged'] and current['state'] == 'open', 'QA PR changed during download', core)
    validate_base(receipt, current, core)
    args.qa_receipt = receipt
    core.save(dest / 'qa-receipt.json', receipt)
    core.atomic_text(dest / 'REVIEW-CONTEXT.md', context)
    core.publish_delivery(args, receipt['source_sha'], run, verified, dest)
    return dest
