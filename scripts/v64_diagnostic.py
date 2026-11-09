"""Shared integrity checks for the frozen v6.4 training diagnostic."""
import hashlib
import json
from pathlib import Path

import run_bloom_coding as runner
from validation_runtime_compat import parameter_values

BASE = Path(__file__).resolve().parents[1]
MANIFEST = BASE/'v6/dev_train_diagnostic_6_4_freeze.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(base=BASE, manifest=MANIFEST):
    frozen = json.loads(manifest.read_text())
    if frozen['intervention']!='6.4' or frozen['model']!='gemma4:31b' or frozen['batch_size']!=1:
        raise ValueError('Unexpected diagnostic configuration')
    parent_path=base/'v6/dev_train_diagnostic_6_1_freeze.json'
    if digest(parent_path)!=frozen['parent_manifest_sha256']:
        raise ValueError('Parent 6.1 freeze changed')
    parent=json.loads(parent_path.read_text())
    if digest(base/'v6/dev_train_diagnostic_6_3_1_freeze.json')!=frozen['prior_prompt_freeze_sha256']:
        raise ValueError('Prior 6.3.1 prompt freeze changed')
    for key in ('model','batch_size','max_retries','timeout','decoding_options','ollama_version','weights_blob_sha256','selection_seed','selection_policy'):
        if frozen[key]!=parent[key]:raise ValueError('Inherited diagnostic setting changed: '+key)
    for language,c in frozen['languages'].items():
        for key in ('input','human_reference','baseline','records','selection','counts','broad_requested_quotas','broad_actual_class_counts'):
            if c[key]!=parent['languages'][language][key]:
                raise ValueError('Diagnostic subset or seed mapping changed: '+language+' '+key)
    for name, expected in frozen['files_sha256'].items():
        if digest(base/name)!=expected:raise ValueError('Frozen diagnostic file changed: '+name)
    seen=set();groups={}
    for language,c in frozen['languages'].items():
        ids=[r['record_id'] for r in runner.read_jsonl(base/c['input'])]
        if ids!=[s['record_id'] for s in c['selection']] or len(ids)!=c['records'] or len(set(ids))!=len(ids):
            raise ValueError('Diagnostic membership/order mismatch: '+language)
        if seen.intersection(ids):raise ValueError('Duplicate diagnostic IDs')
        seen.update(ids)
        for s in c['selection']:
            groups[s['group']]=groups.get(s['group'],0)+1
            expected={**frozen['decoding_options'],'seed':frozen['decoding_options']['seed']+s['original_batch_number']-1}
            if s['original_effective_options']!=expected:raise ValueError('Original seed mismatch')
        for key in ('human_reference','baseline','parent_predictions','comparison_predictions','v62_predictions'):
            if [r['record_id'] for r in runner.read_jsonl(base/c[key])]!=ids:
                raise ValueError('Reference/baseline alignment mismatch')
    if len(seen)!=200 or groups!={'targeted':40,'relevant_control':80,'broad_control':80}:
        raise ValueError('Unexpected diagnostic sizes')
    return frozen


def paths(frozen, language, base=BASE):
    folder=base/frozen['results_dir']; prefix=language+'_gemma_v64'
    return {name:folder/(prefix+'_'+suffix) for name,suffix in {
        'checkpoint':'checkpoint.json','predictions':'predictions.jsonl',
        'raw':'raw_responses.jsonl','failure':'failure.json','lock':'run.lock'}.items()}


def check_runtime(runtime, frozen, condition):
    expected=condition['selection'][0]['runtime_signature']
    for key in ('model_digest','ollama_version','template_sha256'):
        if runtime.get(key)!=expected[key]:raise ValueError('Baseline runtime mismatch: '+key)
    text=runtime.get('model_parameters','')
    if parameter_values(text)!=expected['model_parameters']:
        raise ValueError('Baseline model parameters changed')
    if digest_text(text)!=runtime.get('model_parameters_sha256'):
        raise ValueError('Captured model parameter hash mismatch')
    if frozen['weights_blob_sha256'] not in runtime.get('model_modelfile',''):
        raise ValueError('Model weights changed')
    if [g['name'] for g in runtime.get('gpus',[])]!=['NVIDIA L40S']:
        raise ValueError('Expected one NVIDIA L40S')
    if frozen.get('excluded_gpu_uuid') and runtime['gpus'][0].get('uuid')==frozen['excluded_gpu_uuid']:
        raise ValueError('Previously faulty GPU is excluded')


def digest_text(text):return hashlib.sha256(text.encode()).hexdigest()


def provenance(frozen, condition, manifest=MANIFEST):
    return {'manifest_sha256':digest(manifest),'intervention':'6.4',
            'prompt_version':condition['prompt_version'],'input_sha256':frozen['files_sha256'][condition['input']]}


def check_saved(state, frozen, condition, expected_provenance):
    if state.get('provenance')!=expected_provenance:raise ValueError('Checkpoint provenance mismatch')
    predictions=state['predictions'];batches=state['raw_responses']
    if len(predictions)!=len(batches) or len(batches)>condition['records']:
        raise ValueError('Invalid checkpoint size')
    for p,b,s in zip(predictions,batches,condition['selection']):
        rid=s['record_id']
        runner.validate_response({'schema_version':frozen['schema_version'],'predictions':[p]},[rid],frozen['schema_version'])
        if b['record_ids']!=[rid] or b['original_batch_number']!=s['original_batch_number'] or b['effective_decoding_options']!=s['original_effective_options'] or b['attempt_count']!=1:
            raise ValueError('Saved record/seed/settings mismatch: '+rid)
        if b.get('intervention')!='6.4' or b.get('prompt_version')!=condition['prompt_version']:
            raise ValueError('Saved intervention identity mismatch')
        check_runtime(b['runtime_provenance'],frozen,condition)
    return len(predictions)


if __name__=='__main__':
    f=verify();print('Verified v6.4 diagnostic: 200 dev_train records, 40/80/80 groups, five languages.')
