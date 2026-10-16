"""Rebuild the frozen City Connection final ROM in a new isolated output folder."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-rom',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();source=args.source_rom.resolve();output=args.output_dir.resolve()
    if output.exists():raise SystemExit('Use a new output folder; existing results are never overwritten.')
    # The isolated project must not be nested inside a directory copied below.
    if output.is_relative_to(ROOT/'workspace') or output.is_relative_to(ROOT/'inputs'):
        raise SystemExit('Output folder must be outside workspace and inputs.')
    manifest=json.loads((ROOT/'docs/rebuild/INPUTS.json').read_text(encoding='utf-8'))
    if source.stat().st_size!=manifest['sourceBytes'] or sha(source)!=manifest['sourceSHA256']:
        raise SystemExit('Unsupported original ROM.')
    for row in manifest['files']:
        p=ROOT/row['path']
        if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:
            raise SystemExit('Frozen input differs: '+row['path'])
    output.mkdir(parents=True)
    project=output/'project'
    shutil.copytree(ROOT/'workspace',project/'workspace',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(ROOT/'inputs',project/'inputs')
    (project/'original').mkdir();(project/'work').mkdir()
    shutil.copy2(source,project/'original/City Connection (Japan).nes')
    steps=[('extract_rom.py',[]),('build_rom.py',['--verify']),('audit_strings.py',[]),
           ('build_translation.py',[]),('build_patch.py',['workspace/config/patch_full.json']),
           ('preview_strings.py',['build/city_connection_kr.nes'])]
    for name,extra in steps:
        with (output/(name+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,'-X','utf8','-B',str(project/'workspace/scripts'/name),*extra],cwd=project,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise SystemExit(f'{name} failed; see its log in {output}')
        print('PASS',name,flush=True)
    target=project/'build/city_connection_kr.nes'
    if sha(target)!=manifest['targetSHA256']:raise SystemExit('Rebuild differs from the published final ROM.')
    if sha(source)!=manifest['sourceSHA256']:raise SystemExit('Original source changed.')
    result={'status':'PASS','sourceSHA256':sha(source),'finalSHA256':sha(target),'finalBytes':target.stat().st_size,
            'originalUnchanged':True,'unchangedRoundtrip':'PASS','stringAudit':'PASS','expectedWrite':'PASS',
            'staticStringPreview':'generated; not emulator evidence','titleSource':'approved bitmap config',
            'runtimeVerification':'not performed'}
    (output/'REBUILD_RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('FINAL PASS',sha(target),flush=True)

if __name__=='__main__':main()
