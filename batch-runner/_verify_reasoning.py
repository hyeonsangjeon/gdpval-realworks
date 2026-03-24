import inspect
from core.llm_client import complete
from core.subprocess_runner import SubprocessRunner
from core.executor import TaskExecutor

assert 'reasoning_effort' in inspect.signature(complete).parameters
print('OK: complete()')

assert 'reasoning_effort' in inspect.signature(SubprocessRunner.__init__).parameters
print('OK: SubprocessRunner')

assert 'reasoning_effort' in inspect.signature(TaskExecutor.__init__).parameters
print('OK: TaskExecutor')

code = open('core/llm_client.py').read()
assert 'if reasoning_effort is not None:' in code
print('OK: null guard')

assert 'reasoning_effort' in code.split('kwargs_filtered')[1].split('}')[0]
print('OK: Anthropic filter')

print('All checks passed!')
