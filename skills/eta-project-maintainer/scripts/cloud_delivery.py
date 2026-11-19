#!/usr/bin/env python3
"""Eta verified dual-APK delivery: stable merged run, or --qa-run without merging.
No push, dispatch, upstream sync, signing keys, installation, or notification changes.
"""
import argparse
import hashlib
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

REPO = 'bianwuya/Eta'
PACKAGE = 'io.github.mangi.eta'
CERT = 'a7a92cca03f7d7390ab74001c97efbfe4ff4289b0dc4ffa21d6ebc3cee1c81a8'
PR_JOB = 'Lint / Test / Debug Build'
BUILD_JOBS = {'验证个人版来源 (local)', 'Lint 与单元测试', '构建 Debug 与 Release APK'}
MAX_APK_BYTES = 150 * 1024 * 1024


class DeliveryError(RuntimeError):
    pass


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(text, encoding='utf-8')
    temp.replace(path)


def save(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True, stderr=subprocess.PIPE, timeout=60).strip()


def api(path):
    """Only GET may be retried. Do not print stderr/credentials/signed redirect URLs."""
    for attempt in range(3):
        try:
            return json.loads(gh('api', '--method', 'GET', f'repos/{REPO}/{path}'))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            detail = str(getattr(error, 'stderr', '') or '').lower()
            transient = isinstance(error, subprocess.TimeoutExpired) or any(marker in detail for marker in
                ('eof', 'connection reset', 'timeout', 'timed out', 'http 429', 'http 500', 'http 502', 'http 503', 'http 504'))
            if not transient or attempt == 2:
                raise DeliveryError('GitHub GET failed; inspect authentication/network before resuming') from None
            print(f'GitHub GET transient failure; retry {attempt + 1}/2.', flush=True)
            time.sleep(2 ** (attempt + 1))


def validate_pr(pr, head):
    if (pr['head']['sha'] != head or pr['base']['ref'] != 'local'
            or pr['head']['repo']['full_name'] != REPO or pr['base']['repo']['full_name'] != REPO):
        raise DeliveryError('PR source/head/base changed; refusing another source')
    if not pr['merged'] and pr['state'] != 'open':
        raise DeliveryError('PR was closed without merging')


def pick_run(runs, sha, branch, event):
    exact = [r for r in runs if r['head_sha'] == sha and r['head_branch'] == branch and r['event'] == event]
    return max(exact, key=lambda r: (r['id'], r.get('run_attempt', 1))) if exact else None


def verify_jobs(run, required):
    data = api(f"actions/runs/{run['id']}/jobs?per_page=100")
    jobs = data['jobs']
    if data.get('total_count', len(jobs)) > len(jobs):
        raise DeliveryError('Job list incomplete; inspect run instead of trusting a partial result')
    by_name = {j['name']: j for j in jobs}
    if not required.issubset(by_name) or any(by_name[n]['conclusion'] != 'success' for n in required):
        raise DeliveryError('Required jobs missing, skipped or failed')
    if any(j['conclusion'] not in ('success', 'skipped') for j in jobs):
        raise DeliveryError('Run contains an unsuccessful job')
    return [{'name': j['name'], 'conclusion': j['conclusion']} for j in jobs]


def merge_once(pr_number, head):
    """One normal server-enforced write. Unknown response: read back, never replay."""
    try:
        gh('api', '--method', 'PUT', f'repos/{REPO}/pulls/{pr_number}/merge',
           '-f', 'merge_method=merge', '-f', f'sha={head}')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    pr = api(f'pulls/{pr_number}')
    validate_pr(pr, head)
    if not pr['merged']:
        raise DeliveryError('Merge not confirmed; PR re-read as unmerged. No write retry was made')
    return pr['merge_commit_sha']


def wait_pr(args, deadline):
    last = None
    while time.monotonic() < deadline:
        pr = api(f'pulls/{args.pr}')
        validate_pr(pr, args.head)
        if pr['merged']:
            return pr['merge_commit_sha']
        runs = api(f'actions/workflows/pr-check.yml/runs?head_sha={args.head}&per_page=100')['workflow_runs']
        run = pick_run(runs, args.head, pr['head']['ref'], 'pull_request')
        state = (run['status'], run.get('conclusion')) if run else ('waiting', None)
        if state != last:
            print('PR verification:', state, flush=True)
            save(args.receipt_dir / 'pr-progress.json', {'pr': args.pr, 'head': args.head,
                 'run_id': run['id'] if run else None, 'state': state})
            last = state
        if run and run['status'] == 'completed':
            if run['conclusion'] != 'success':
                raise DeliveryError(f"PR check failed: https://github.com/{REPO}/actions/runs/{run['id']}")
            verify_jobs(run, {PR_JOB})
            if args.merge_approved:
                return merge_once(args.pr, args.head)
        time.sleep(args.interval)
    raise DeliveryError('Wait expired; PR not merged. No build/dispatch/install was started')


def wait_build(args, sha, deadline):
    last = None
    while time.monotonic() < deadline:
        runs = api(f'actions/workflows/android-release.yml/runs?branch=local&head_sha={sha}&per_page=100')['workflow_runs']
        run = pick_run(runs, sha, 'local', 'push')
        state = (run['status'], run.get('conclusion')) if run else ('waiting', None)
        if state != last:
            print('Signed cloud build:', state, flush=True)
            save(args.receipt_dir / 'build-progress.json', {'source': sha,
                 'run_id': run['id'] if run else None, 'state': state})
            last = state
        if run and run['status'] == 'completed':
            if run['conclusion'] != 'success':
                raise DeliveryError(f"Build failed: https://github.com/{REPO}/actions/runs/{run['id']}")
            save(args.receipt_dir / 'cloud-jobs.json', verify_jobs(run, BUILD_JOBS))
            return run
        time.sleep(args.interval)
    raise DeliveryError('Wait expired; no duplicate workflow was dispatched')


def artifact_names(version, sha, qa=False):
    metadata = ('qa-' if qa else '') + sha[:7]
    return {f'Eta-v{version}+{metadata}.apk': 'release', f'Eta-v{version}-debug+{metadata}.apk': 'debug'}


def select_artifacts(data, names):
    artifacts = data['artifacts']
    if data.get('total_count', len(artifacts)) > len(artifacts):
        raise DeliveryError('Artifact list incomplete')
    chosen = [a for a in artifacts if a['name'] in names and not a['expired']]
    if len(chosen) != 2 or {a['name'] for a in chosen} != set(names):
        raise DeliveryError('Missing/duplicate/expired same-source Debug or Release artifact')
    for a in chosen:
        if not 0 < a['size_in_bytes'] <= MAX_APK_BYTES:
            raise DeliveryError('Artifact size outside expected bounded APK range')
    return chosen


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise DeliveryError('Refusing non-HTTPS artifact redirect')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            for source in (redirected.headers, redirected.unredirected_hdrs):
                for key in list(source):
                    if key.lower() == 'authorization':
                        del source[key]
        return redirected


def download(artifact, target):
    url = artifact['archive_download_url']
    if urllib.parse.urlsplit(url).scheme != 'https' or urllib.parse.urlsplit(url).netloc != 'api.github.com':
        raise DeliveryError('Unexpected artifact API origin')
    token = gh('auth', 'token')  # Memory only, not printed or written.
    request = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'})
    size = 0
    with urllib.request.build_opener(SafeRedirect()).open(request, timeout=180) as response, target.open('wb') as out:
        while block := response.read(1024 * 1024):
            size += len(block)
            if size > MAX_APK_BYTES:
                raise DeliveryError('Downloaded APK too large')
            out.write(block)
    if size != artifact['size_in_bytes']:
        raise DeliveryError('Downloaded artifact size mismatch or transfer truncated')


def verify_apk(path, variant, sha, args):
    with zipfile.ZipFile(path) as archive:
        if 'AndroidManifest.xml' not in archive.namelist():
            raise DeliveryError('Downloaded file is an artifact wrapper/report, not an APK')
    certs = subprocess.check_output(['java', '-jar', str(args.apksigner_jar), 'verify', '--print-certs-pem', str(path)],
                                    text=True, stderr=subprocess.PIPE, timeout=120)
    pem = re.findall(r'-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----', certs)
    if len(pem) != 1:
        raise DeliveryError('Expected exactly one existing signer certificate')
    fingerprint = subprocess.check_output(['openssl', 'x509', '-noout', '-fingerprint', '-sha256'],
                                          input=pem[0], text=True, stderr=subprocess.PIPE, timeout=30)
    digest = fingerprint.strip().split('=', 1)[-1].replace(':', '').lower()
    if digest != CERT:
        raise DeliveryError('APK signer does not match the existing personal version; no replacement key allowed')
    badging = subprocess.check_output([str(args.aapt), 'dump', 'badging', str(path)], text=True, stderr=subprocess.PIPE, timeout=60)
    line = next((line for line in badging.splitlines() if line.startswith('package: ')), '')
    fields = dict(re.findall(r"(\w+)='([^']*)'", line))
    metadata = ('qa-' if getattr(args, 'qa_run', None) else '') + sha[:7]
    version = args.version + ('-debug' if variant == 'debug' else '') + '+' + metadata
    if fields.get('name') != PACKAGE or fields.get('versionName') != version:
        raise DeliveryError('APK package/version/source metadata mismatch')
    with path.open('rb') as stream:
        file_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'bytes': path.stat().st_size, 'sha256': file_digest, 'certificate_sha256': CERT, 'version_name': version}


def obtain_apk(artifact, dest, variant, sha, args):
    final = dest / artifact['name']
    if final.exists() and final.stat().st_size == artifact['size_in_bytes']:
        try:
            return {'path': str(final), **verify_apk(final, variant, sha, args)}
        except (DeliveryError, subprocess.SubprocessError, zipfile.BadZipFile):
            pass  # Keep the old file until a new copy has passed all checks.
    partial = final.with_suffix('.part')
    try:
        download(artifact, partial)
        metadata = verify_apk(partial, variant, sha, args)
        partial.replace(final)
        return {'path': str(final), **metadata}
    finally:
        partial.unlink(missing_ok=True)


def publish_delivery(args, sha, run, rows, dest):
    if len(rows) != 2:
        raise DeliveryError('Both verified APKs are required before publishing delivery')
    url = f'https://github.com/{REPO}/actions/runs/{run["id"]}'
    report = {'source': sha, 'feature_head': args.head, 'pr': f'https://github.com/{REPO}/pull/{args.pr}',
              'run': url, 'conclusion': 'success', 'apks': rows, 'installed': False, 'user_accepted': False}
    qa = getattr(args, 'qa_run', None) is not None
    if qa:
        report['channel'] = 'pr-qa'
        report['qa_provenance'] = args.qa_receipt
        report['merged'] = False
    for row in rows:
        path = Path(row['path'])
        atomic_text(dest / (path.name + '.sha256'), row['sha256'] + '  ' + path.name + '\n')
    save(dest / '交付回执.json', report)
    channel_text = '未合入PR的QA包，单独覆盖安装不等于合并多个功能。\n' if qa else ''
    atomic_text(dest / '说明.txt', f'{args.label}\n源码: {sha}\n{url}\n' + channel_text + '原签名标准双包，手动任选一包覆盖安装；不卸载、不清数据。\n'
                '未自动安装、改模型设置或收费测试。CI/签名校验不等于用户功能验收。\n')
    save(args.receipt_dir / 'delivery.json', report)
    (args.receipt_dir / 'delivery-failure.json').unlink(missing_ok=True)
    latest_name = f'最新QA-PR{args.pr}.txt' if qa else '最新测试包.txt'
    atomic_text(dest.parent / latest_name, args.label + '，源码 ' + sha[:7] + '\n' + '\n'.join(r['path'] for r in rows)
                + '\n两包原证书/元数据/SHA256已核验，任选一包手动覆盖；未安装，功能待用户实测。\nActions Artifacts: ' + url + '\n')
    print('两包已下载并核验；最新入口已更新：' + str(dest), flush=True)
    print('请主代理给出实际APK引用并核实完成通知；通知许可不等于用户已看到。', flush=True)
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pr', type=int, required=True)
    parser.add_argument('--head', required=True, help='Exact 40-hex feature HEAD, read from git/API')
    parser.add_argument('--version', required=True, help='Actual base app version, e.g. 3.4.0')
    parser.add_argument('--label', required=True, help='Task-specific delivery directory label')
    parser.add_argument('--receipt-dir', type=Path, required=True)
    parser.add_argument('--merge-approved', action='store_true', help='Use only with explicit merge authorization for this task')
    parser.add_argument('--qa-run', type=int, help='Exact Device Test APK signing run ID; never merges or dispatches')
    parser.add_argument('--downloads', type=Path, default=Path('/sdcard/Download/Eta-测试包'))
    parser.add_argument('--apksigner-jar', type=Path, default=Path('/workspace/toolchains/eta/android-sdk/build-tools/37.0.0/lib/apksigner.jar'))
    parser.add_argument('--aapt', type=Path, default=Path('/workspace/toolchains/eta/bin/aapt2'))
    parser.add_argument('--interval', type=int, default=60, choices=range(30, 301), metavar='30..300')
    parser.add_argument('--timeout', type=int, default=7200, choices=range(60, 14401), metavar='60..14400')
    args = parser.parse_args(argv)
    if args.qa_run is not None and (args.qa_run <= 0 or args.merge_approved):
        parser.error('--qa-run needs a positive signing run ID and cannot authorize merging')
    if (args.pr <= 0 or not re.fullmatch(r'[0-9a-f]{40}', args.head)
            or not re.fullmatch(r'\d+\.\d+\.\d+(?:[.-][A-Za-z0-9]+)*', args.version)
            or not args.label.strip() or any(c in args.label for c in '/\\\r\n') or args.label in ('.', '..')):
        parser.error('Invalid PR/head/version/label; use exact live values')
    args.receipt_dir = args.receipt_dir.resolve()
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        if not args.apksigner_jar.is_file() or not args.aapt.is_file():
            raise DeliveryError('Verification tools missing; supply actual --apksigner-jar/--aapt before merging')
        deadline = time.monotonic() + args.timeout
        if args.qa_run is not None:
            from qa_delivery import deliver
            import sys
            deliver(args, deadline, sys.modules[__name__])
            return 0
        sha = wait_pr(args, deadline)
        if not re.fullmatch(r'[0-9a-f]{40}', sha or ''):
            raise DeliveryError('Missing exact merged source SHA')
        save(args.receipt_dir / 'merged-source.json', {'source': sha, 'feature_head': args.head, 'pr': args.pr})
        run = wait_build(args, sha, deadline)
        names = artifact_names(args.version, sha)
        artifacts = select_artifacts(api(f"actions/runs/{run['id']}/artifacts?per_page=100"), names)
        dest = args.downloads / (args.label + '-' + sha[:7])
        dest.mkdir(parents=True, exist_ok=True)
        rows = [obtain_apk(a, dest, names[a['name']], sha, args) for a in sorted(artifacts, key=lambda a: a['name'])]
        publish_delivery(args, sha, run, rows, dest)
        return 0
    except Exception as error:
        # Avoid persisting arbitrary stderr or token-bearing URLs from failed downloads.
        message = str(error) if isinstance(error, DeliveryError) else 'Tool/transfer failed; inspect the failed stage without exposing credentials'
        save(args.receipt_dir / 'delivery-failure.json', {'error_type': type(error).__name__, 'message': message})
        print(type(error).__name__ + ': ' + message, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
