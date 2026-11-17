"""Test-only flash Upload peer. No HA service or real device is contacted."""

import asyncio
from copy import deepcopy
import json

from custom_components.home_panel._core import protocol
from support import FakeTransport, TOKEN, metadata, response


class CandidatePanel(FakeTransport):
    def __init__(self):
        super().__init__(with_capabilities=True)
        self.state.update(storage="flash-nvs", storage_ready=True, sd_ready=False, storage_generation="8",
            write_base_sha256="a" * 64, writable=True, pending_trial=False, uncertain=False,
            high_water_revision=31, storage_status=0, storage_warnings=0)
        self.state["features"].extend(["flash-maintenance.v1", "write-base.v1"])
        self.state["candidate"] = deepcopy(self.state["temporary"])
        self.documents.pop("candidate")

    async def request(self, method, path, *, headers, body, max_bytes):
        if (method, path) != ("POST", protocol.API + "upload"):
            return await super().request(method, path, headers=headers, body=body, max_bytes=max_bytes)
        await asyncio.sleep(0)
        self.calls.append((method, path, dict(headers), body, max_bytes))
        assert headers["Authorization"] == "Bearer " + TOKEN
        for header, key in (("X-Panel-Settings", "session_id"), ("X-Panel-Storage-Generation", "storage_generation"),
                            ("X-Panel-Write-Base", "write_base_sha256"), ("X-Panel-Revision", "revision")):
            if headers.get(header) != str(self.state[key]):
                return response({}, status=409)
        self.next_id += 1
        accepted = {"id": self.next_id, "done": False, "status": 202, "error": "",
            "session_id": self.state["session_id"], "device_id": self.state["device_id"], "revision": self.state["revision"]}
        self.documents["candidate"] = body
        self.state["candidate"] = metadata(body)
        self.state.update(revision=self.state["revision"] + 1,
            storage_generation=str(int(self.state["storage_generation"]) + 1),
            high_water_revision=json.loads(body)["revision"], write_base_sha256="b" * 64)
        self.jobs[self.next_id] = dict(accepted, revision=self.state["revision"], done=True, status=200)
        return self.change(method, "upload", response(accepted, status=202))
