"""GDPVal Batch Runner Core Modules"""

from importlib import import_module
from typing import Any


__all__ = [
	"GDPValDataLoader",
	"GDPValTask",
	"DomainFilter",
	"PromptBuilder",
	"PromptConfig",
]

_EXPORT_MODULES = {
	"GDPValDataLoader": ".data_loader",
	"GDPValTask": ".data_loader",
	"DomainFilter": ".domain_filter",
	"PromptBuilder": ".prompt_builder",
	"PromptConfig": ".prompt_builder",
}


def __getattr__(name: str) -> Any:
	module_name = _EXPORT_MODULES.get(name)
	if module_name is None:
		raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
	value = getattr(import_module(module_name, __name__), name)
	globals()[name] = value
	return value
