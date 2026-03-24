from core.experiment_config import ExperimentConfig

files = [
    'exp013_GPT54_reasoning_high',
    'exp014_GPT54_reasoning_medium',
    'exp015_GPT54_reasoning_low',
    'exp016_GPT54_reasoning_null',
]

for f in files:
    cfg = ExperimentConfig.from_yaml(f'experiments/{f}.yaml')
    re_val = cfg.condition_a.model.reasoning_effort
    print(f'{f}: reasoning_effort={re_val!r}')
