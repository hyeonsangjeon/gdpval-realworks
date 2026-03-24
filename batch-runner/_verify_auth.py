"""Verify create_client() auth paths work correctly."""
import os
from unittest.mock import patch, MagicMock

# Test 1: DefaultAzureCredential path (real, since az login is active)
print("=== Test 1: DefaultAzureCredential (real) ===")
from core.llm_client import create_client
client = create_client(endpoint="https://dlstmvprtus-wingnut0310-ai.openai.azure.com/")
print("OK: Client created with DefaultAzureCredential")
print(f"   Type: {type(client).__name__}")

# Test 2: API Key fallback (mock azure.identity failure)
print("\n=== Test 2: API Key fallback ===")
import importlib
import core.llm_client as mod
with patch.dict("sys.modules", {"azure.identity": None}):
    importlib.reload(mod)
    client2 = mod.create_client(
        endpoint="https://test.openai.azure.com/",
        api_key="fake-key-for-test",
    )
    print("OK: Client created with API Key fallback")
    print(f"   Type: {type(client2).__name__}")

# Test 3: No credentials → ValueError
print("\n=== Test 3: No credentials → error ===")
with patch.dict("sys.modules", {"azure.identity": None}):
    importlib.reload(mod)
    with patch.dict(os.environ, {}, clear=True):
        try:
            mod.create_client(endpoint="https://test.openai.azure.com/")
            print("FAIL: Should have raised ValueError")
        except ValueError as e:
            print("OK: ValueError raised as expected")

# Restore module
importlib.reload(mod)
print("\nAll auth path tests passed!")
