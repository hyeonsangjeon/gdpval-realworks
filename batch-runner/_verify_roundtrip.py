from core.experiment_config import ExperimentConfig

# Verify to_dict() includes reasoning_effort in condition model dict
for f in ['exp013_GPT54_reasoning_high', 'exp016_GPT54_reasoning_null']:
    cfg = ExperimentConfig.from_yaml(f'experiments/{f}.yaml')
    d = cfg.to_dict()
    re_val = d['condition_a']['model'].get('reasoning_effort')
    print(f'{f}: condition_a.model.reasoning_effort = {re_val!r}')

# Verify existing experiments are unaffected
cfg_old = ExperimentConfig.from_yaml('experiments/exp002_GPT52Chat_elicit.yaml')
d_old = cfg_old.to_dict()
re_old = d_old['condition_a']['model'].get('reasoning_effort')
print(f'exp002 (existing): condition_a.model.reasoning_effort = {re_old!r}')
assert re_old is None, "Existing experiments must have reasoning_effort=None"
print('OK: existing experiments unaffected')
