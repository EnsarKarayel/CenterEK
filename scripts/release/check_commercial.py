"""Fail closed: a preview, unsigned build or incomplete acceptance is not sale-ready."""
import argparse
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import sys
import re
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import installer_core
import release_signing


def assess(manifest, acceptance, legal):
    issues = []
    if manifest.get('qa_only') is True:
        issues.append('A QA-only bundle cannot be sold')
    if not re.fullmatch(r'\d+\.\d+\.\d+', manifest.get('version', '')):
        issues.append('A non-preview release version is required')
    if manifest.get('signed') is not True:
        issues.append('Trusted timestamped publisher signatures are missing')
    if manifest.get('license_mode') != 'commercial':
        issues.append('Commercial annual subscription enforcement is not enabled')
    if not manifest.get('eula_sha256') or legal.get('approved_eula_sha256') != manifest.get('eula_sha256'):
        issues.append('Final publisher-approved EULA hash is missing or mismatched')
    if not manifest.get('third_party_sha256') or legal.get('third_party_review_sha256') != manifest.get('third_party_sha256'):
        issues.append('Third-party license inventory review is missing or mismatched')
    if legal.get('approved') is not True or any(not legal.get(k) for k in ('seller', 'country', 'support_email', 'publisher_thumbprint')):
        issues.append('Seller identity, support contact and publisher approval are incomplete')
    if acceptance.get('ok') is not True or acceptance.get('kind') != 'isolated-windows' or acceptance.get('python_absent') is not True:
        issues.append('Clean isolated Windows acceptance without Python has not passed')
    if acceptance.get('version') != manifest.get('version') or acceptance.get('license_mode') != 'active':
        issues.append('Acceptance must exercise this exact commercial version with an active subscription')
    if acceptance.get('publisher_thumbprint') != legal.get('publisher_thumbprint'):
        issues.append('Clean Windows must trust the approved publisher certificate')
    for key in ('reboot_test', 'uac_interaction', 'outer_setup_ui'):
        if acceptance.get(key) != 'passed':
            issues.append(key + ' requires verified acceptance')
    for step in ('trusted_signature', 'install', 'login', 'https', 'system_tasks', 'endpoint_received', 'windows_registration', 'uninstall_preserves_data', 'restored_same_account'):
        if acceptance.get('steps', {}).get(step) is not True:
            issues.append('Missing acceptance step: ' + step)
    return issues


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def assess_artifacts(folder, manifest, acceptance, legal):
    """Bind approvals to the actual archive, extracted payload and outer setup."""
    issues = []
    for field, hash_field in (('setup', 'setup_sha256'), ('archive', 'sha256')):
        name = manifest.get(field)
        if not isinstance(name, str) or not name or '/' in name or '\\' in name or ':' in name or name in ('.', '..'):
            issues.append('Invalid ' + field + ' filename')
            continue
        path = folder / name
        if path.is_symlink() or not path.is_file() or digest(path) != manifest.get(hash_field):
            issues.append(field + ' digest mismatch or file missing')
    if issues:
        return issues
    if acceptance.get('setup_sha256') != manifest.get('setup_sha256'):
        issues.append('Outer setup acceptance belongs to a different binary')
    bundle = folder / 'dist/CenterEK-Setup'
    try:
        with zipfile.ZipFile(folder / manifest['archive']) as archive:
            seen = set()
            for entry in archive.infolist():
                path = PurePosixPath(entry.filename)
                if ('\\' in entry.filename or ':' in entry.filename or path.is_absolute()
                        or '..' in path.parts or not path.parts or path.parts[0] != 'CenterEK-Setup'):
                    raise ValueError('Unsafe archive member')
                if entry.is_dir():
                    continue
                relative = Path(*path.parts[1:])
                key = relative.as_posix().casefold()
                if key in seen:
                    raise ValueError('Duplicate archive member')
                seen.add(key)
                extracted = bundle / relative
                if any(parent.is_symlink() for parent in (extracted, *extracted.parents)) or not extracted.is_file():
                    raise ValueError('Missing or linked extracted member')
                with archive.open(entry) as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != digest(extracted):
                        raise ValueError('Extracted payload differs from archive')
            actual = {p.relative_to(bundle).as_posix().casefold() for p in bundle.rglob('*') if p.is_file()}
            if actual != seen:
                raise ValueError('Extracted payload contains unexpected files')
        if digest(bundle / 'CenterEK-Setup.exe') != acceptance.get('bundle_exe_sha256'):
            issues.append('Clean Windows report belongs to a different binary')
        assets = bundle / '_internal'
        for name, field in (('EULA.txt', 'eula_sha256'), ('THIRD-PARTY.txt', 'third_party_sha256')):
            if digest(assets / name) != manifest.get(field):
                issues.append('Packaged ' + name + ' digest mismatch')
        policy = json.loads((assets / 'release-policy.json').read_text(encoding='utf-8-sig'))
        if policy.get('mode') != 'commercial' or not policy.get('public_keys'):
            issues.append('Packaged commercial license policy is missing')
        publisher = json.loads((assets / 'publisher.json').read_text(encoding='utf-8-sig'))
        if any(publisher.get(key) != legal.get(key) for key in ('seller', 'country', 'support_email')):
            issues.append('Packaged seller differs from approved seller')
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as error:
        issues.append('Payload integrity verification failed: ' + type(error).__name__)
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('release', type=Path)
    parser.add_argument('--acceptance', type=Path)
    parser.add_argument('--legal-approval', type=Path)
    parser.add_argument('--report-only', action='store_true', help='CI audit only; never authorizes publication')
    args = parser.parse_args()
    folder = args.release.resolve()
    (folder / 'commercial-readiness-report.json').write_text(json.dumps({'sale_ready': False, 'issues': ['Verification incomplete']}), encoding='utf-8')
    manifest = json.loads((folder / 'release-manifest.json').read_text(encoding='utf-8-sig'))
    if Path(manifest.get('setup', '')).name != manifest.get('setup'):
        raise ValueError('Invalid setup filename')
    acceptance = json.loads(args.acceptance.read_text(encoding='utf-8-sig')) if args.acceptance else {}
    legal = json.loads(args.legal_approval.read_text(encoding='utf-8-sig')) if args.legal_approval else {}
    issues = assess(manifest, acceptance, legal)
    issues.extend(assess_artifacts(folder, manifest, acceptance, legal))
    if not issues:
        thumbprint = legal['publisher_thumbprint']
        bundle = folder / 'dist/CenterEK-Setup'
        for path in (folder / manifest['setup'], bundle / 'CenterEK-Setup.exe', *(bundle / '_internal' / name for name in installer_core.SCRIPTS)):
            release_signing.verify(path, thumbprint)
    report = {'sale_ready': not issues, 'version': manifest.get('version'), 'issues': issues}
    (folder / 'commercial-readiness-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if args.report_only or not issues else 1


if __name__ == '__main__':
    raise SystemExit(main())
