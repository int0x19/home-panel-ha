"""Synthetic flash Apply lifecycle; never controls an actual panel or HA entity."""

import asyncio
from copy import deepcopy
import json

from candidate_panel import CandidatePanel
from support import DEVICE_ID, TOKEN, response


class ActivationPanel(CandidatePanel):
    def __init__(self):
        super().__init__()
        self.state.update(apply_enabled=True, boot_phase=1)
        self.reference = None
        self.auto = None
        self.probes = 0

    async def request(self, method, path, *, headers, body, max_bytes):
        if self.reference and path.endswith("/status") and self.auto:
            self.probes += 1
            if self.probes == 2: self.reboot()
            if self.probes == 3:
                self.rollback() if self.auto == "rollback" else self.confirm()
        if (method, path) != ("POST", "/panel/runtime/api/apply"):
            return await super().request(method, path, headers=headers, body=body, max_bytes=max_bytes)
        await asyncio.sleep(0)
        self.calls.append((method, path, dict(headers), body, max_bytes))
        assert headers["Authorization"] == "Bearer " + TOKEN
        envelope = json.loads(body)
        if (headers["X-Panel-Settings"] != self.state["session_id"] or
                headers["X-Panel-Storage-Generation"] != self.state["storage_generation"] or
                headers["X-Panel-Write-Base"] != self.state["write_base_sha256"] or
                envelope != {"revision":self.state["revision"], "sha256":self.state["candidate"]["sha256"]}):
            return response({}, status=409)
        self.reference = deepcopy(self.state)
        self.documents_before = deepcopy(self.documents)
        self.next_id += 1
        accepted = {"id":self.next_id, "done":False, "status":202, "error":"",
            "device_id":DEVICE_ID, "session_id":self.state["session_id"], "revision":self.state["revision"]}
        self.state.update(revision=self.state["revision"] + 1, pending_trial=True, writable=False,
            restarting=True, storage_generation=str(int(self.state["storage_generation"]) + 1),
            write_base_sha256="c" * 64)
        self.jobs[self.next_id] = dict(accepted, done=True, status=200, revision=self.state["revision"])
        return self.change(method, "apply", response(accepted, status=202))

    def reboot(self):
        self.state.update(session_id="2" * 32, csrf="2" * 32, revision=1, restarting=False,
            boot_phase=2, loaded_source="flash-trial", loaded_revision=self.state["candidate"]["revision"],
            storage_generation=str(int(self.reference["storage_generation"]) + 2), write_base_sha256="d" * 64)
        self.jobs.clear(); self.next_id = 0

    def confirm(self):
        self.state.update(boot_phase=4, pending_trial=False, writable=True,
            storage_generation=str(int(self.reference["storage_generation"]) + 3), write_base_sha256="e" * 64)
        self.state["backup"] = deepcopy(self.reference["active"])
        self.documents["backup"] = self.documents_before["active"]
        self.state["active"] = deepcopy(self.state["candidate"])
        self.documents["active"] = self.documents.pop("candidate")
        self.state["candidate"] = deepcopy(self.state["temporary"])

    def rollback(self):
        self.state.update(session_id="3" * 32, csrf="3" * 32, boot_phase=1,
            pending_trial=False, writable=True, restarting=False,
            loaded_source="flash-confirmed", loaded_revision=self.reference["active"]["revision"],
            storage_generation=str(int(self.reference["storage_generation"]) + 3), write_base_sha256="f" * 64)
        self.state["candidate"] = deepcopy(self.state["temporary"])
        self.documents.pop("candidate", None)
