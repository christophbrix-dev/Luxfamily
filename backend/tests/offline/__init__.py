"""Offline test package.

Being a package keeps pytest from putting this directory on sys.path, so its
conftest cannot shadow the integration suite's conftest one level up.
"""
