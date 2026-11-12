"""Read-only broker contract fixtures: no external network, host or SDK."""

import base64
import copy
import io
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


@pytest.fixture
def https_transport(monkeypatch):
    state = SimpleNamespace(calls=[], closed=0, status=403, body=b'{}', headers={})

    class Connection:
        def __init__(self, host, port, *, timeout, context):
            assert (host, port, timeout) == ('api.github.com', 443, 10)
            assert context.check_hostname

        def request(self, method, path, *, headers):
            state.calls.append((method, path, dict(headers)))

        def getresponse(self):
            return SimpleNamespace(status=state.status, read=lambda limit: state.body,
                                   getheader=lambda name, default=None: state.headers.get(name, default))

        def close(self):
            state.closed += 1

    monkeypatch.setattr(broker.http.client, 'HTTPSConnection', Connection)
    return state


def test_https_transport_supplies_user_agent_without_changing_pinned_discovery_headers(https_transport):
    # Pinned CopilotApiService discovery has no explicit User-Agent. Native
    # fetch supplies one; Python http.client does not. No real HTTPS here.
    headers = {**message()['headers'], 'x-github-api-version': '2025-04-01'}
    before = dict(headers)
    assert broker.https_get(broker.USER_URL, headers)[0] == 403
    method, path, outgoing = https_transport.calls[0]
    assert (method, path) == ('GET', '/copilot_internal/user')
    assert outgoing == {**before, 'user-agent': 'gdpval-ghcp-ahp-metadata/1.0'}
    assert headers == before and https_transport.closed == 1


def test_https_transport_preserves_explicit_user_agent_and_editor_headers(https_transport):
    headers = {**message()['headers'], 'user-agent': 'pinned-client-fixture/1.0',
               'editor-version': 'vscode/1.144.0', 'editor-plugin-version': 'copilot-fixture/1.0'}
    before = dict(headers)
    broker.https_get(broker.USER_URL, headers)
    assert https_transport.calls == [('GET', '/copilot_internal/user', before)]
    assert headers == before and https_transport.closed == 1


def test_https_transport_returns_only_selected_error_header_presence(https_transport):
    https_transport.headers = {'content-type': 'application/json', 'x-accepted-github-permissions': 'copilot_requests=write',
                               'x-github-sso': 'required; url=https://github.com/orgs/PRIVATE_FIXTURE/sso',
                               'x-oauth-scopes': '', 'set-cookie': CANARY, 'authorization': CANARY}
    status, headers, body = broker.https_get(broker.USER_URL, message()['headers'])
    assert status == 403 and body == b'{}'
    assert headers == {'content-type': 'application/json', 'diagnostic_header_presence': {
        'x-accepted-github-permissions': True, 'x-github-sso': True,
        'x-oauth-scopes': True, 'x-accepted-oauth-scopes': False}}
    assert CANARY not in json.dumps(headers) and 'PRIVATE_FIXTURE' not in json.dumps(headers)


def test_error_receipt_records_only_redacted_message_documentation_and_header_presence(https_transport):
    encoded = base64.b64encode(CANARY.encode()).decode()
    https_transport.body = json.dumps({'message': f'Denied for PRIVATE_FIXTURE: {CANARY} {encoded}',
        'documentation_url': 'https://docs.github.com/rest/using-the-rest-api/troubleshooting-the-rest-api',
        'login': 'PRIVATE_FIXTURE', 'token': CANARY, 'extra': 'not-for-audit'}).encode()
    https_transport.headers = {'x-github-sso': 'required; url=https://github.com/orgs/PRIVATE_FIXTURE/sso'}
    handler = broker.Broker(CANARY, broker.https_get)
    assert handler.request(message())['status'] == 403
    receipt = handler.receipt()
    details = receipt['external_requests'][0]['error_diagnostic']
    assert details == {'message': 'Denied for [REDACTED]: [REDACTED] [REDACTED]',
        'documentation_url': 'https://docs.github.com/rest/using-the-rest-api/troubleshooting-the-rest-api',
        'header_presence': {'x-accepted-github-permissions': False, 'x-github-sso': True,
                            'x-oauth-scopes': False, 'x-accepted-oauth-scopes': False}}
    exported = json.dumps(receipt)
    for private in (CANARY, encoded, 'PRIVATE_FIXTURE', 'not-for-audit', 'body_base64'):
        assert private not in exported
    assert receipt['response_bodies_persisted'] is False
    assert handler.failed and handler.request(message()) == {'error': 'metadata_closed'}
    assert len(https_transport.calls) == 1 and receipt['inference_requests'] == 0


@pytest.mark.parametrize('body', [b'<html>PRIVATE_FIXTURE</html>', b'{bad json', b'[]', b'null',
                                 b'{"message":"one","message":"two"}', b'\xff'])
def test_unparseable_error_body_does_not_replace_http_status_or_leak_body(https_transport, body):
    https_transport.body = body
    handler = broker.Broker(CANARY, broker.https_get)
    assert handler.request(message())['status'] == 403
    row = handler.receipt()['external_requests'][0]
    assert row['status'] == 403 and row['error_diagnostic']['message'] == 'not_reported'
    assert row['error_diagnostic']['documentation_url'] == 'not_reported'
    assert 'PRIVATE_FIXTURE' not in json.dumps(row) and handler.failed
    assert handler.request(message()) == {'error': 'metadata_closed'}
    assert len(https_transport.calls) == 1


@pytest.mark.parametrize('url', ['http://docs.github.com/rest', 'https://evil.invalid/docs',
    'https://docs.github.com.evil.invalid/rest', 'https://docs.github.com:443/rest',
    'https://private@docs.github.com/rest', 'https://docs.github.com/rest?token=private', None])
def test_error_diagnostic_does_not_export_noncanonical_documentation_urls(https_transport, url):
    https_transport.body = json.dumps({'message': 'Denied', 'documentation_url': url}).encode()
    handler = broker.Broker(CANARY, broker.https_get)
    assert handler.request(message())['status'] == 403
    assert handler.receipt()['external_requests'][0]['error_diagnostic']['documentation_url'] == 'not_reported'


def test_error_message_is_redacted_before_length_limit(https_transport):
    https_transport.body = json.dumps({'message': 'x' * 1000 + CANARY + 'y' * 1000}).encode()
    handler = broker.Broker(CANARY, broker.https_get)
    handler.request(message())
    text = handler.receipt()['external_requests'][0]['error_diagnostic']['message']
    assert text == 'x' * 1000 + '[REDACTED]' + 'y' * 14
    assert len(text) == 1024


def test_missing_diagnostic_headers_are_unknown_not_absent():
    handler = broker.Broker(CANARY, lambda *args: (403, {}, b'{"message":"Denied"}'))
    assert handler.request(message())['status'] == 403
    details = handler.receipt()['external_requests'][0]['error_diagnostic']
    assert set(details['header_presence'].values()) == {'not_reported'}


def local_handler(handler, frame, writer):
    instance = object.__new__(broker.Handler)
    instance.connection = SimpleNamespace(settimeout=lambda _: None,
        getsockopt=lambda *args: broker.struct.pack('3i', 123, os.getuid(), os.getgid()))
    instance.server = SimpleNamespace(broker=handler)
    instance.rfile, instance.wfile = io.BytesIO(frame), writer
    return instance


def test_local_eof_is_distinct_from_malformed_frame_and_never_writes_or_fetches(fake):
    handler, calls = fake
    output = io.BytesIO()
    local_handler(handler, b'', output).handle()
    assert output.getvalue() == b'' and calls == []
    assert handler.failed and handler.receipt()['denials'] == [{'reason': 'metadata_local_disconnected'}]
    assert handler.request(message()) == {'error': 'metadata_closed'}
    assert calls == []


@pytest.mark.parametrize('error_type', [BrokenPipeError, ConnectionResetError])
def test_local_write_disconnect_retains_original_403_and_never_retries(error_type, capsys):
    calls = []
    def fetch(*args):
        calls.append(args)
        return 403, {}, b'{"message":"Forbidden"}'
    handler = broker.Broker(CANARY, fetch)
    writes = []
    def write(data):
        writes.append(data)
        raise error_type('synthetic peer cancelled')
    instance = local_handler(handler, json.dumps(message()).encode() + b'\n', SimpleNamespace(write=write))
    instance.handle()
    assert len(calls) == len(writes) == 1
    receipt = handler.receipt()
    assert receipt['external_requests'][0]['status'] == 403
    assert receipt['denials'] == [{'reason': 'metadata_local_disconnected'}]
    assert handler.failed and handler.request(message()) == {'error': 'metadata_closed'}
    assert len(calls) == 1 and capsys.readouterr() == ('', '')


def test_local_read_reset_is_terminal_without_error_reply_or_network(fake):
    handler, calls = fake
    output = io.BytesIO()
    instance = local_handler(handler, b'', output)
    def reset(_):
        raise ConnectionResetError('synthetic peer cancelled')
    instance.rfile = SimpleNamespace(readline=reset)
    instance.handle()
    assert output.getvalue() == b'' and calls == []
    assert handler.failed and handler.receipt()['denials'] == [{'reason': 'metadata_local_disconnected'}]


def test_malformed_frame_stays_terminal_if_error_reply_hits_broken_pipe(fake):
    handler, calls = fake
    def broken_pipe(_):
        raise BrokenPipeError('synthetic peer cancelled')
    local_handler(handler, b'not-json\n', SimpleNamespace(write=broken_pipe)).handle()
    assert calls == [] and handler.failed
    assert handler.receipt()['denials'] == [{'reason': 'metadata_local_frame_refused'},
                                          {'reason': 'metadata_local_disconnected'}]


def test_real_unix_peer_cancellation_keeps_403_without_server_traceback(tmp_path, capsys):
    started, release = threading.Event(), threading.Event()
    calls = []
    def fetch(*args):
        calls.append(args)
        started.set()
        assert release.wait(3), 'fixture response was not released'
        return 403, {}, b'{"message":"Forbidden"}'
    handler = broker.Broker(CANARY, fetch)
    path = tmp_path / 'cancelled.sock'
    with broker.Server(str(path), broker.Handler) as server:
        server.broker = handler
        server.timeout = 3
        worker = threading.Thread(target=server.handle_request, daemon=True)
        worker.start()
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(3)
                client.connect(str(path))
                client.sendall(json.dumps(message()).encode() + b'\n')
                assert started.wait(3)
                client.shutdown(socket.SHUT_RDWR)
            # The peer is closed before the HTTP response is released: no race
            # or sleep to manufacture a BrokenPipe, and still only fake HTTPS.
        finally:
            release.set()
            worker.join(timeout=3)
    assert not worker.is_alive() and capsys.readouterr() == ('', '')
    assert len(calls) == 1 and handler.failed
    assert handler.receipt()['external_requests'][0]['status'] == 403
    assert handler.receipt()['denials'] == [{'reason': 'metadata_local_disconnected'}]
    assert handler.request(message()) == {'error': 'metadata_closed'}
    assert len(calls) == 1


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
