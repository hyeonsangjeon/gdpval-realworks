"""The hosted readiness job must not become a paid/authenticated model path."""

from pathlib import Path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/gpt56-native-runner-check.yml'


@pytest.fixture
def document():
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


def test_only_model_free_push_and_pr_events(document):
    assert set(document['on']) == {'push', 'pull_request'}
    assert document['on']['push']['branches'] == ['leader/runner-receipt-20261029']
    assert set(document['jobs']) == {'native-runner-check'}


def test_host_is_fixed_and_has_no_identity_or_secret_capability(document):
    job = document['jobs']['native-runner-check']
    assert document['permissions'] == {'contents': 'read'}
    assert job['runs-on'] == 'ubuntu-24.04'
    assert job['timeout-minutes'] == '15'
    assert 'environment' not in job and 'permissions' not in job
    assert set(job['env']) == {'PYTHONDONTWRITEBYTECODE', 'HF_HUB_OFFLINE',
                               'HF_DATASETS_OFFLINE'}
    assert all('runner.' not in value for value in job['env'].values())
    text = WORKFLOW.read_text()
    for forbidden in ('secrets.', 'id-token:', 'azure/login', '--send-request',
                      'step2_run_inference.py', 'step8_grade.py',
                      'diagnose_codex_foundry_connection.py', '--valid-request',
                      '--closing-sweep', 'continue-on-error'):
        assert forbidden not in text


def test_actions_and_runtime_inputs_are_pinned(document):
    steps = document['jobs']['native-runner-check']['steps']
    for step in steps:
        if 'uses' in step:
            assert re.fullmatch(r'[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+@[0-9a-f]{40}', step['uses'])
    assert steps[0]['with'] == {'fetch-depth': '0', 'persist-credentials': 'false'}
    assert steps[1]['with']['python-version'] == '3.10.12'
    assert steps[2]['run'] == 'python -m pip install -r requirements.txt'
    requirements = (ROOT / 'batch-runner/requirements.txt').read_text()
    assert re.search(r'^openai-codex==0\.147\.0\s*$', requirements, re.MULTILINE)
    assert re.search(r'^openai-codex-cli-bin==0\.147\.0\s*$', requirements, re.MULTILINE)


def test_closed_step_order_and_readiness_failure_cannot_be_ignored(document):
    steps = document['jobs']['native-runner-check']['steps']
    assert [step['name'] for step in steps] == [
        'Checkout exact source', 'Set up Python', 'Install the registered dependencies',
        'Run offline admission contracts', 'Install system bubblewrap if absent',
        'Prove the pinned local sandbox without a model',
        'Retain bounded runner and sandbox evidence',
    ]
    assert "-m 'not integration'" in steps[3]['run']
    assert steps[3]['env'] == {
        'GDPVAL_CODEX_RUN_ROOT': '${{ runner.temp }}/native-offline-workspaces'}
    probe = steps[5]
    assert 'if' not in probe and 'continue-on-error' not in probe
    assert probe['working-directory'] == 'batch-runner'
    assert probe['run'] == ('set -euo pipefail\n'
        'python scripts/prepare_codex_sandbox_host.py \\\n'
        '  --out "$RUNNER_TEMP/native-sandbox-proof.json"\n')
    upload = steps[6]
    assert upload['if'] == 'always()'
    assert upload['with']['path'] == '${{ runner.temp }}/native-sandbox-proof.json'
    assert upload['with']['if-no-files-found'] == 'error'


@pytest.mark.parametrize('field', ['secrets.COPILOT_GITHUB_TOKEN', 'secrets.AZURE_CLIENT_ID',
                                  'inputs.send_request'])
def test_no_paid_inputs_or_secret_expressions_are_present(field):
    assert field not in WORKFLOW.read_text()
