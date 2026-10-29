"""Portable measured-study records and local file replay; no execution gateway.

CLI: python -m mrqlab_experiment.study_records run INPUT --output RECORD
     python -m mrqlab_experiment.study_records replay RECORD --output REPLAY
     python -m mrqlab_experiment.study_records verify RECORD
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import tempfile
import numpy as np
from .lab_study import LabStudy, run_lab_study, fingerprint, import_echo_csv, json_safe


def source_manifest():
    root=Path(__file__).resolve().parents[3]
    files={}
    for folder in ['packages','services/api']:
        for path in sorted((root/folder).rglob('*.py')):
            files[path.relative_to(root).as_posix()]=sha256(path.read_bytes()).hexdigest()
    for name in ['pyproject.toml','uv.lock']:
        path=root/name
        if path.is_file(): files[name]=sha256(path.read_bytes()).hexdigest()
    if not files or 'pyproject.toml' not in files:
        raise ValueError('study replay requires the MRQlab source checkout and dependency manifest')
    return dict(files=files,sha256=fingerprint(files))


IMPORTED_SOURCE_HASH=source_manifest()['sha256']


def runtime_manifest():
    versions={}
    for distribution in ['numpy','pydantic','fastapi','uvicorn']:
        try: versions[distribution]=importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError: versions[distribution]='not installed'
    if versions['numpy']!=np.__version__: raise ValueError('installed NumPy differs from loaded version; restart in the recorded environment')
    return dict(python=platform.python_version(),implementation=platform.python_implementation(),
        system=platform.system(),machine=platform.machine(),packages=versions,
        blas_configuration=json_safe(getattr(np.__config__,'CONFIG',{})))


def _checked_sources():
    sources=source_manifest()
    if sources['sha256']!=IMPORTED_SOURCE_HASH:
        raise ValueError('source changed since process startup; restart before recording or replaying')
    return sources


def create_study_record(study: LabStudy | dict):
    sources=_checked_sources(); request=LabStudy.model_validate(study).model_dump(mode='json')
    result=run_lab_study(request)
    if _checked_sources()!=sources: raise ValueError('source changed during execution')
    body=dict(schema_version='mrqlab-study-record-1',study_kind='measured-tse',canonicalization='typed-json-f64-v1',
        request=request,request_json=json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False),
        request_sha256=fingerprint(request),result=result,result_sha256=fingerprint(result),
        sources=sources,runtime=runtime_manifest())
    return {**body,'record_sha256':fingerprint(body)}


def verify_study_record(record: dict):
    expected={'canonicalization','schema_version','study_kind','request_json','request','request_sha256','result','result_sha256','sources','runtime','record_sha256'}
    if not isinstance(record,dict) or set(record)!=expected or record['schema_version']!='mrqlab-study-record-1' or record['study_kind']!='measured-tse' or record['canonicalization']!='typed-json-f64-v1':
        raise ValueError('unsupported or malformed study record')
    body={k:v for k,v in record.items() if k!='record_sha256'}
    if fingerprint(body)!=record['record_sha256']: raise ValueError('study record integrity hash mismatch')
    if fingerprint(record['request'])!=record['request_sha256'] or fingerprint(record['result'])!=record['result_sha256']:
        raise ValueError('request/result hash mismatch')
    sources=record['sources']
    if not isinstance(sources,dict) or set(sources)!={'files','sha256'} or fingerprint(sources['files'])!=sources['sha256']:
        raise ValueError('source manifest integrity mismatch')
    if not isinstance(record['request_json'],str): raise ValueError('lossless request JSON is required')
    decoded=json.loads(record['request_json'])
    if fingerprint(decoded)!=record['request_sha256']: raise ValueError('lossless request JSON differs from the request object')
    LabStudy.model_validate(decoded)
    return dict(integrity_passed=True,record_sha256=record['record_sha256'],
        result_sha256=record['result_sha256'],scope='integrity only; no simulation or scientific revalidation performed')


def replay_study_record(record: dict):
    verify_study_record(record)
    if _checked_sources()!=record['sources']: raise ValueError('replay source/dependency manifest differs; use the original source anchor')
    if runtime_manifest()!=record['runtime']: raise ValueError('replay runtime differs; use the recorded Python/package/BLAS environment')
    # Legacy ExperimentGraph union fields carry int/float distinctions in their
    # existing plan fingerprints. Preserve their original validated JSON tokens
    # across JavaScript transport, without altering those locked contracts.
    replay=create_study_record(json.loads(record['request_json']))
    if replay['result_sha256']!=record['result_sha256'] or replay['record_sha256']!=record['record_sha256']:
        raise ValueError('computational replay mismatch; do not treat this record as reproduced')
    return replay


def save_study_record(record: dict, destination: str | Path):
    """Atomic create, never overwrite. A failed validation leaves no output."""
    verify_study_record(record); path=Path(destination)
    raw=json.dumps(record,sort_keys=True,indent=2,allow_nan=False).encode()+b'\n'
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.mrqlab-study-',delete=False) as output:
            temporary=Path(output.name); output.write(raw); output.flush(); os.fsync(output.fileno())
        os.link(temporary,path)  # Atomic no-overwrite publication, in the same directory.
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)
    return path


def _read_json(path):
    with Path(path).open('rb') as source: raw=source.read(16000001)
    if len(raw)>16000000: raise ValueError('study JSON exceeds 16 MB')
    return json.loads(raw)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Measured-input MRQlab teaching study records; no scanner/clinical certification')
    sub=parser.add_subparsers(dest='action',required=True)
    for name in ['run','replay','verify']:
        command=sub.add_parser(name); command.add_argument('input')
        if name!='verify': command.add_argument('--output',required=True)
        if name=='run': command.add_argument('--measurements-csv')
    args=parser.parse_args(argv)
    try:
        data=_read_json(args.input)
        if args.action=='verify': print(json.dumps(verify_study_record(data),sort_keys=True)); return 0
        if args.action=='replay': record=replay_study_record(data)
        else:
            if args.measurements_csv:
                metadata=data['dataset']
                with Path(args.measurements_csv).open('rb') as source: raw=source.read(1000001)
                data['dataset']=import_echo_csv(raw,source_ref=metadata['source_ref'],origin=metadata['origin'],
                    echo_spacing_s=metadata.get('echo_spacing_s',.008),tr_s=metadata.get('tr_s',.4)).model_dump(mode='json')
            record=create_study_record(data)
        save_study_record(record,args.output)
        print(json.dumps(dict(path=str(Path(args.output).resolve()),record_sha256=record['record_sha256'],
            result_sha256=record['result_sha256'],validation=record['result']['validation']),sort_keys=True))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        parser.exit(2,f'study {args.action} failed: {exc}\n')


if __name__=='__main__': main()
