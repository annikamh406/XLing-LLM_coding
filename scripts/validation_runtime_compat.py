"""Accept only proven parameter-order differences, preserving observed runtime metadata."""
import hashlib
import json
import os
from pathlib import Path


def parameter_values(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split(None,1)
        if len(parts)!=2 or parts[0] in result:
            raise ValueError('Ambiguous model parameter text; cannot normalize safely')
        result[parts[0]] = parts[1]
    return result


def compatible_runtime(args, runtime_path):
    """Return an audited runtime file with parameter text in its original order.

    No inference settings or checkpoints are modified. The actual capture stays
    untouched; both original and observed strings/hashes are retained in the
    derived metadata. Every other runtime signature field must match exactly.
    """
    path = Path(runtime_path)
    current = json.loads(path.read_text())
    prefix = f'{args.split}_{args.model.replace(":","_")}_{args.schema_version}_{args.prompt_version}'
    checkpoint = args.results_dir / (prefix+'_checkpoint.json')
    if not checkpoint.exists():
        return path
    state = json.loads(checkpoint.read_text())
    signature = state['provenance']['runtime_signature']
    if current['model_parameters_sha256']==signature['model_parameters_sha256']:
        return path
    if not state['raw_responses']:
        raise ValueError('Cannot prove parameter equivalence without a saved runtime')
    old = state['raw_responses'][-1]['runtime_provenance']
    for key,value in signature.items():
        if key!='model_parameters_sha256' and current.get(key)!=value:
            raise ValueError('Runtime changed beyond parameter order: '+key)
    if sorted(g['name'] for g in current['gpus'])!=state['provenance']['gpu_model']:
        raise ValueError('GPU model changed')
    old_text, new_text = old['model_parameters'],current['model_parameters']
    for text,expected in [(old_text,signature['model_parameters_sha256']),
                          (new_text,current['model_parameters_sha256'])]:
        if hashlib.sha256(text.encode()).hexdigest()!=expected:
            raise ValueError('Parameter text does not match its saved hash')
    if parameter_values(old_text)!=parameter_values(new_text):
        raise ValueError('Model parameter values changed; refusing resume')
    compatible = dict(current)
    compatible['model_parameters_observed'] = new_text
    compatible['model_parameters_observed_sha256'] = current['model_parameters_sha256']
    compatible['model_parameters'] = old_text
    compatible['model_parameters_sha256'] = signature['model_parameters_sha256']
    compatible['parameter_order_equivalence'] = {
        'rule':'identical unique parameter names and values; ordering ignored',
        'observed_runtime_file':str(path),'checkpoint_file':str(checkpoint)}
    target = path.with_name(path.stem+f'_order-compatible-{os.getpid()}.json')
    target.write_text(json.dumps(compatible,indent=2)+'\n')
    return target
