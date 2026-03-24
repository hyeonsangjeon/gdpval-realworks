from core.experiment_config import ExperimentConfig

files = [
    'exp017_GPT54Pro_reasoning_high', 'exp018_GPT54Pro_reasoning_medium',
    'exp019_GPT54Pro_reasoning_low', 'exp020_GPT54Pro_reasoning_null',
    'exp021_GPT54Mini_reasoning_high', 'exp022_GPT54Mini_reasoning_medium',
    'exp023_GPT54Mini_reasoning_low', 'exp024_GPT54Mini_reasoning_null',
]
for f in files:
    cfg = ExperimentConfig.from_yaml('experiments/' + f + '.yaml')
    d = cfg.to_dict()
    dep = d['condition_a']['model']['deployment']
    re_val = d['condition_a']['model'].get('reasoning_effort')
    src = d.get('data', {}).get('source', 'N/A')
    print(f + ': deployment=' + dep + ', reasoning_effort=' + repr(re_val) + ', source=' + src)
