"""Compatibility layer exporting the business_logic package from src."""
from importlib import import_module

_module = import_module("src.business_logic")

globals().update(_module.__dict__)

__all__ = getattr(_module, "__all__", [])
