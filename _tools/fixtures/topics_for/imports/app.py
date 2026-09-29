"""Sign-in helper for PL-SRV-0042. The docstring names kerberos, which is prose, not an import."""
import os
import msal
from ldap3 import Server, Connection
from .local import helper
from vendorlib import *

try:
    import gssapi  # optional
except ImportError:
    gssapi = None

# uses kinit on the host


def lookup():
    import requests_kerberos
    return requests_kerberos, os, Server, Connection, helper
