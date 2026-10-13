"""Shared code for every backend service. Edit files here, then run bin/sync-shared.sh."""
import os
import sys

# Local (LocalStack hot reload) runs the service folder as-is, so packages are vendored into .vendor.
# On AWS, Terraform installs requirements into the zip and .vendor is excluded from packaging.
_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".vendor")
if os.path.isdir(_VENDOR) and _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
