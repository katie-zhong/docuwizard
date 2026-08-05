"""
sources.py — where files come from.

The pipeline only ever sees "a list of (label, path) pairs". Everything that
knows about WHERE files came from lives behind this interface, so adding
SharePoint later is a drop-in and touches nothing else.

  LocalUpload   IMPLEMENTED. Files uploaded through the browser, written to a
                temporary run folder on this machine.

  SyncedFolder  DESIGNED, NOT BUILT. Reads a normal Windows folder that happens
                to be a SharePoint library synced by the OneDrive client
                ("Add shortcut to OneDrive"). This is the preferred future path
                because the tool itself still makes NO network calls - the
                Microsoft-sanctioned sync client does the transport, so the
                on-device guarantee is preserved. Implementing it is essentially
                "point at a path", which is why the seam is this thin.

  GraphSource   DESIGNED, NOT BUILT, AND NOT RECOMMENDED. Pulling from
                SharePoint over Microsoft Graph would require an Entra app
                registration, admin-consented permissions, token handling, and
                a client secret stored on a managed laptop - and would break the
                no-external-calls constraint outright. Kept here only so the
                decision is documented rather than rediscovered.
"""

import os


class Source:
    """Interface: return a list of {"label": str, "path": str}."""

    def collect(self):
        raise NotImplementedError


class LocalUpload(Source):
    """Files already written to a folder by the upload endpoint."""

    def __init__(self, folder):
        self.folder = folder

    def collect(self):
        out = []
        for name in sorted(os.listdir(self.folder)):
            path = os.path.join(self.folder, name)
            if os.path.isfile(path) and not name.startswith("~$"):
                out.append({"label": name, "path": path})
        return out


class SyncedFolder(Source):
    """Planned: a OneDrive-synced SharePoint library folder. Not yet enabled."""

    def __init__(self, folder):
        self.folder = folder

    def collect(self):
        raise NotImplementedError(
            "SharePoint via OneDrive sync is planned but not enabled yet. "
            "Upload files directly for now."
        )


class GraphSource(Source):
    """Planned and deliberately deferred: cloud pull via Microsoft Graph."""

    def collect(self):
        raise NotImplementedError(
            "Cloud access via Microsoft Graph is intentionally not implemented: "
            "it would require an Entra app registration and admin consent, and "
            "would break the on-device constraint."
        )
