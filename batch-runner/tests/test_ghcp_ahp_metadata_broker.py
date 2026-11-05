"""Read-only broker contract fixtures: no external network, host or SDK."""

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

import ghcp_ahp_metadata_broker as broker
import ghcp_ahp_probe as probe
import ghcp_ahp_thread_policy as policy
import ghcp_ahp_wire_capture as wire
from .test_ghcp_ahp_zero_turn import CANARY, SESSION, WORKSPACE, Wire
from .test_ghcp_ahp_wire_capture import prepared_fixture

MODEL_URL = 'https://api.individual.githubcopilot.com/models'
FIXTURE = Path(__file__).with_name('fixtures') / 'ghcp_ahp_metadata_fixture.cjs'


def message(url=broker.USER_URL):
    return {'method': 'GET', 'url': url, 'headers': {'authorization': 'Bearer ' + CANARY, 'accept': 'application/json'}}


@pytest.fixture
def fake():
    calls = []
    def fetch(url, headers):
        calls.append((url, headers))
        body = ({'login': 'PRIVATE_FIXTURE', 'endpoints': {'api': MODEL_URL.removesuffix('/models')}}
                if url == broker.USER_URL else {'data': [{'id': 'gpt-5.6-sol'}]})
        return 200, {'content-type': 'application/json'}, json.dumps(body).encode()
    return broker.Broker(CANARY, fetch), calls


def test_exact_discovery_then_bound_models_and_cached_replays_have_two_external_gets(fake):
    handler, calls = fake
    assert handler.request(message())['status'] == 200
    assert handler.request(message())['external_request'] is False
    assert handler.models_url == MODEL_URL
    assert handler.request(message(MODEL_URL))['status'] == 200
    assert handler.request(message(MODEL_URL))['external_request'] is False
    assert [url for url, _ in calls] == [broker.USER_URL, MODEL_URL]
    receipt = handler.receipt()
    assert len(receipt['external_requests']) == 2 and receipt['inference_requests'] == 0
    assert receipt['cache_hits'] == 2
    assert CANARY not in json.dumps(receipt) and 'PRIVATE_FIXTURE' not in json.dumps(receipt)
    assert receipt['response_bodies_persisted'] is False and receipt['admission_allowed'] is False


def test_real_unix_protocol_preload_and_broker_with_only_external_https_faked(fake, tmp_path):
    handler, calls = fake
    path = tmp_path / 'bridge.sock'
    with broker.Server(str(path), broker.Handler) as server:
        path.chmod(0o600)
        server.broker = handler
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            result = subprocess.run(['node', str(FIXTURE.with_name('ghcp_ahp_metadata_unix_fixture.cjs')), str(path)],
                capture_output=True, text=True, timeout=20, env={'PATH': '/usr/bin:/bin:/usr/local/bin'})
            assert result.returncode == 0, result.stderr
        finally:
            server.shutdown()
            worker.join(timeout=2)
    assert not worker.is_alive()
    assert len(calls) == 2
    rows = json.loads(result.stdout)
    replies = [row for row in rows if row['kind'] == 'metadata_response']
    assert [row['status'] for row in replies] == [200, 200]
    assert [row['path'] for row in replies] == ['/copilot_internal/user', '/models']
    assert not any(row['kind'] in {'capi_request', 'ipc_request'} for row in rows)


def test_cached_metadata_cannot_change_semantic_headers(fake):
    handler, calls = fake
    assert handler.request(message())['status'] == 200
    changed = message()
    changed['headers']['copilot-integration-id'] = 'different-context'
    assert handler.request(changed) == {'error': 'metadata_cached_headers_changed'}
    assert len(calls) == 1


def test_malformed_local_frame_is_terminal_without_network(fake, tmp_path):
    handler, calls = fake
    path = tmp_path / 'invalid.sock'
    with broker.Server(str(path), broker.Handler) as server:
        server.broker = handler
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(2)
                client.connect(str(path))
                client.sendall(b'not-json\n')
                assert json.loads(client.recv(1024)) == {'error': 'metadata_local_frame_refused'}
        finally:
            server.shutdown()
            worker.join(timeout=2)
    assert calls == [] and handler.failed and handler.receipt()['denials']


def test_logical_replay_limit_is_not_an_external_retry(fake):
    handler, calls = fake
    for _ in range(16):
        assert handler.request(message())['status'] == 200
    assert handler.request(message()) == {'error': 'metadata_local_request_limit'}
    assert len(calls) == 1


@pytest.mark.parametrize('url', [
    'https://api.githubcopilot.com/responses', 'https://api.githubcopilot.com/chat/completions',
    'https://api.githubcopilot.com/v1/messages', 'https://api.githubcopilot.com/embeddings',
    'https://api.githubcopilot.com/models/session', 'https://api.github.com/copilot_internal/v2/token',
    'https://api.githubcopilot.com.evil.invalid/models', 'https://evil.githubcopilot.com/models',
    'http://api.github.com/copilot_internal/user', 'https://api.github.com:443/copilot_internal/user',
    'https://user@api.github.com/copilot_internal/user', 'https://API.GITHUB.COM/copilot_internal/user',
    'https://api.github.com/copilot_internal/user?', 'https://api.github.com/copilot_internal/user#x',
    'https://api.github.com/x/../copilot_internal/user', 'https://api.github.com/copilot_internal/%75ser',
    'https://api.githubcopilot.com/models/', 'https://127.0.0.1/models', 'file:///models',
])
def test_every_other_host_path_alias_inference_and_token_mint_is_rejected_before_io(fake, url):
    handler, calls = fake
    assert handler.request(message(url)) == {'error': 'metadata_url_refused'}
    assert calls == []


@pytest.mark.parametrize('method', ['POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'CONNECT', 'get', None])
def test_only_literal_get_allowed(fake, method):
    handler, calls = fake
    request = message()
    request['method'] = method
    assert 'error' in handler.request(request) and not calls


@pytest.mark.parametrize('header,value', [('host', 'evil.invalid'), ('x-http-method-override', 'POST'),
    ('authorization', 'Bearer OTHER'), ('accept', 'application/json\r\nx: bad')])
def test_header_credentials_and_method_tunneling_are_refused(fake, header, value):
    handler, calls = fake
    request = message()
    request['headers'][header] = value
    assert 'error' in handler.request(request) and not calls


def test_models_are_not_allowed_before_discovery_or_on_other_known_host(fake):
    handler, calls = fake
    assert handler.request(message(MODEL_URL)) == {'error': 'metadata_catalog_not_bound_to_discovery'}
    assert calls == []
    # A rejected request consumes this broker; no recovery/retry to reopen it.
    assert handler.request(message()) == {'error': 'metadata_closed'}


@pytest.mark.parametrize('origin', ['https://evil.invalid', 'https://evil.githubcopilot.com',
    'https://api.individual.githubcopilot.com/', 'https://api.individual.githubcopilot.com:443',
    'http://api.githubcopilot.com', None])
def test_discovery_cannot_expand_exact_hostname_policy(origin):
    calls = []
    def fetch(*args):
        calls.append(args)
        return 200, {}, json.dumps({'endpoints': {'api': origin}}).encode()
    handler = broker.Broker(CANARY, fetch)
    assert handler.request(message()) == {'error': 'metadata_discovered_origin_refused'}
    assert len(calls) == 1 and handler.models_url is None
    assert 'error' in handler.request(message(MODEL_URL)) and len(calls) == 1


@pytest.mark.parametrize('status', [301, 302, 307, 308, 401, 403, 429, 500])
def test_redirect_errors_and_retry_statuses_never_send_a_second_external_request(status):
    calls = []
    def fetch(*args):
        calls.append(args)
        return status, {'location': 'https://evil.invalid'}, b'{}'
    handler = broker.Broker(CANARY, fetch)
    assert handler.request(message())['status'] == status
    assert handler.request(message()) == {'error': 'metadata_closed'}
    assert len(calls) == 1
    assert handler.receipt()['external_requests'][0]['status'] == status


def test_timeout_and_unknown_exception_do_not_leak_or_retry():
    calls = []
    def fetch(*args):
        calls.append(args)
        raise RuntimeError(CANARY)
    handler = broker.Broker(CANARY, fetch)
    assert handler.request(message()) == {'error': 'metadata_transport_failed'}
    assert handler.request(message()) == {'error': 'metadata_closed'}
    assert len(calls) == 1 and CANARY not in json.dumps(handler.receipt())
    assert handler.receipt()['external_requests'][0]['status'] is None


def test_deadline_is_checked_at_exact_boundary_before_network():
    now = [1.0]
    handler = broker.Broker(CANARY, lambda *args: pytest.fail('expired broker sent HTTP'), clock=lambda: now[0])
    now[0] = 121.0
    assert handler.request(message()) == {'error': 'metadata_closed'}


@pytest.mark.parametrize('scenario', ['user', 'models', 'post', 'body', 'redirect', 'responses', 'chat', 'messages',
    'suffix', 'query', 'encoded', 'path_alias', 'missing_auth', 'broker_error', 'status'])
def test_preload_uses_only_fake_unix_broker_never_original_fetch(scenario):
    result = subprocess.run(['node', str(FIXTURE), scenario], capture_output=True, text=True, timeout=20,
                            env={'PATH': '/usr/bin:/bin:/usr/local/bin'})
    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert all(row['synthetic'] is True for row in rows)
    assert not any(row['kind'] == 'capi_request' for row in rows)


def test_launcher_retains_kernel_namespace_and_privilege_boundaries_without_secret_in_argv(monkeypatch, tmp_path):
    monkeypatch.setenv('COPILOT_GITHUB_TOKEN', CANARY)
    command, environment = broker.isolated_command(tmp_path / 'prepared', tmp_path / 'evidence', tmp_path / 'broker.sock')
    assert command[0] == 'sudo'
    for value in ('unshare', '--mount', '--net', '--pid', '--fork', '--mount-proc', '--kill-child=KILL',
                  '--bounding-set=-all', '--inh-caps=-all', '--ambient-caps=-all', '--no-new-privs',
                  '--authenticated-zero-turn', '--metadata-socket'):
        assert value in command
    assert CANARY not in ' '.join(command) and environment['COPILOT_GITHUB_TOKEN'] == CANARY
    assert 'HOME' not in environment and 'GITHUB_TOKEN' not in environment


def test_local_launcher_refuses_before_credentials_files_or_processes(monkeypatch, tmp_path, capsys):
    def refused():
        raise broker.Refused('synthetic_not_actions')
    monkeypatch.setattr(broker, 'require_runner', refused)
    monkeypatch.setattr(broker, 'validate_credential', lambda *args: pytest.fail('local credential inspection'))
    assert broker.main(['--prepared', str(tmp_path / 'p'), '--evidence', str(tmp_path / 'e')]) == 2
    assert not (tmp_path / 'e').exists()
    assert 'synthetic_not_actions' in capsys.readouterr().out


def test_metadata_socket_requires_auth_and_current_user_mode_0600(prepared_fixture, monkeypatch, tmp_path):
    for key, value in {'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GHCP_AUTHENTICATED_ZERO_TURN': 'true',
                       'GHCP_PAID_EXECUTION': 'false', 'GHCP_CONNECTION_ONLY': 'false'}.items():
        monkeypatch.setenv(key, value)
    root, state, _, _ = prepared_fixture
    socket_path = tmp_path / 'metadata.sock'
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(socket_path))
        socket_path.chmod(0o600)
        result = wire.install(root, state, {'VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS': json.dumps(policy.NATIVE_ARGS)},
            model_free=True, session_policy=True, credential=CANARY, authenticated_zero_turn=True, metadata_socket=socket_path)
    assert result['GHCP_AHP_WIRE_METADATA_SOCKET'] == str(socket_path)
    assert result['GHCP_AHP_WIRE_MODE'] == 'session-only'
    assert json.loads((state / 'wire/bootstrap.json').read_text())['metadata_reads'] is True


@pytest.mark.parametrize('value', [None, True, 0, 'false'])
def test_mcp_flag_must_be_observed_false_before_authenticated_lookup(value):
    fake = Wire()
    receive = fake.receive
    def reply():
        result = receive()
        if fake.sent[-1]['method'] == 'initialize':
            result['result']['snapshots'][0]['state']['config'] = {'values': {'githubMcpServerEnabled': value}}
        return result
    fake.receive = reply
    rpc = probe.Rpc(fake, SESSION, WORKSPACE, session_policy=True, credential=CANARY, require_mcp_disabled=True)
    with pytest.raises(probe.Refused, match='metadata_mcp_disabled_not_reported'):
        policy.exercise(rpc)
    assert len(fake.sent) == 1


def test_mcp_disabled_root_report_allows_auth_but_not_work():
    fake = Wire()
    receive = fake.receive
    def reply():
        value = receive()
        if fake.sent[-1]['method'] == 'initialize':
            value['result']['snapshots'][0]['state']['config'] = {'values': {'githubMcpServerEnabled': False}}
        return value
    fake.receive = reply
    rpc = probe.Rpc(fake, SESSION, WORKSPACE, session_policy=True, credential=CANARY, require_mcp_disabled=True)
    result = policy.exercise(rpc, lambda: {'replies': 1})
    assert list(result) == [*policy.AUTH_METHODS[:-1], 'native_wait', 'disposeSession']
    assert [row['method'] for row in fake.sent] == list(policy.AUTH_METHODS)
