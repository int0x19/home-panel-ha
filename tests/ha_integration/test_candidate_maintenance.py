"""HA administrator workflow for flash candidate removal and backup staging."""

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

import pytest

from activation_panel import ActivationPanel
from custom_components.home_panel._core import TransportError, encode_document
from support import TOKEN, metadata, response
from test_candidate_apply import stage
from test_websocket_api import command, connect_ws, entry, ws


class MaintenancePanel(ActivationPanel):
    def __init__(self):
        super().__init__()
        self.state["features"].append("recover-candidate.v1")

    async def request(self, method, path, *, headers, body, max_bytes):
        suffix = path.rsplit("/", 1)[-1]
        if method != "POST" or suffix not in {"discard", "recover"}:
            return await super().request(method, path, headers=headers, body=body, max_bytes=max_bytes)
        self.calls.append((method, path, dict(headers), body, max_bytes))
        assert headers["Authorization"] == "Bearer " + TOKEN
        assert headers["X-Panel-Write-Base"] == self.state["write_base_sha256"]
        assert headers["X-Panel-Storage-Generation"] == self.state["storage_generation"]
        assert headers["X-Panel-Settings"] == self.state["session_id"]
        envelope = {"revision": self.state["revision"]}
        if suffix == "recover":
            envelope["sha256"] = self.state["backup"]["sha256"]
        assert json.loads(body) == envelope
        self.next_id += 1
        accepted = {"id": self.next_id, "done": False, "status": 202, "error": "",
                    "revision": self.state["revision"], "session_id": self.state["session_id"],
                    "device_id": self.state["device_id"]}
        self.state.update(revision=self.state["revision"] + 1,
                          storage_generation=str(int(self.state["storage_generation"]) + 1),
                          write_base_sha256=("d" if suffix == "discard" else "e") * 64)
        job = dict(accepted, done=True, status=200, revision=self.state["revision"])
        if suffix == "discard":
            self.documents.pop("candidate")
            self.state["candidate"] = deepcopy(self.state["temporary"])
        else:
            document = json.loads(self.documents["backup"])
            document["revision"] = self.state["high_water_revision"] + 1
            self.documents["candidate"] = encode_document(document)
            self.state["candidate"] = info = metadata(self.documents["candidate"])
            self.state["high_water_revision"] = info["revision"]
            job["candidate"] = {"revision": info["revision"], "sha256": info["sha256"],
                                "storage_generation": self.state["storage_generation"]}
        self.jobs[self.next_id] = job
        return self.change(method, suffix, response(accepted, status=202))

    def mutations(self):
        return [path.rsplit("/", 1)[-1] for method, path, *_ in self.calls if method == "POST"
                and path.rsplit("/", 1)[-1] in {"discard", "recover", "apply"}]


@pytest.fixture
def panel():
    return MaintenancePanel()


async def review(ws, entry, source):
    result = await command(ws, entry, "import", source=source)
    assert result["success"]
    return result["result"]["import_id"]


async def test_discard_then_recover_requires_matching_import_and_preserves_known_good(ws, entry, panel):
    before = deepcopy(panel.state)
    sent = await stage(ws, entry)
    for operation, source in (("discard", "active"), ("recover", "backup")):
        marker = await review(ws, entry, source)
        assert (await command(ws, entry, operation, import_id=marker))["error"]["code"] == "candidate_conflict"
    assert panel.mutations() == []
    marker = await review(ws, entry, "candidate")
    discarded = await command(ws, entry, "discard", import_id=marker)
    assert discarded["success"] and discarded["result"]["activation"] is None
    assert discarded["result"]["status"]["high_water_revision"] == sent["candidate"]["revision"]
    assert not discarded["result"]["status"]["files"]["candidate"]["present"]
    assert (await command(ws, entry, "apply", apply_id=sent["apply_id"]))["error"]["code"] == "candidate_conflict"
    assert (await command(ws, entry, "discard", import_id=marker))["error"]["code"] == "candidate_conflict"
    marker = await review(ws, entry, "backup")
    recovered = await command(ws, entry, "recover", import_id=marker)
    assert recovered["success"] and recovered["result"]["apply_id"]
    assert recovered["result"]["activation"]["state"] == "ready"
    assert json.loads(panel.documents["candidate"]) == {**json.loads(panel.documents["backup"]), "revision": 33}
    for key in ("active", "backup", "loaded_source", "loaded_revision", "restarting", "pending_trial"):
        assert panel.state[key] == before[key]
    assert panel.mutations() == ["discard", "recover"]


@pytest.mark.parametrize("operation,source", [("discard", "candidate"), ("recover", "backup")])
async def test_stale_tabs_and_same_generation_base_change_fail_before_mutation(ws, entry, panel, connect_ws, operation, source):
    if operation == "discard":
        await stage(ws, entry)
    old = await review(ws, entry, source)
    other = await connect_ws()
    current = await review(other, entry, source)
    assert (await command(ws, entry, operation, import_id=old))["error"]["code"] == "candidate_conflict"
    panel.state["write_base_sha256"] = "f" * 64
    assert (await command(other, entry, operation, import_id=current))["error"]["code"] == "candidate_conflict"
    assert panel.mutations() == []


@pytest.mark.parametrize("failure", ["lost", "receipt"])
async def test_uncertain_recovery_revokes_import_and_does_not_offer_apply(ws, entry, panel, failure):
    marker = await review(ws, entry, "backup")
    def change(method, suffix, result):
        if failure == "lost" and suffix == "recover":
            raise TransportError("Lost receipt")
        if failure == "receipt" and suffix.startswith("jobs/"):
            job = json.loads(result.body)
            if "candidate" in job:
                job["candidate"]["sha256"] = "f" * 64
                return response(job)
        return result
    panel.change = change
    assert (await command(ws, entry, "recover", import_id=marker))["error"]["code"] == "outcome_unknown"
    status = (await command(ws, entry, "status"))["result"]
    assert status["status"]["files"]["candidate"]["valid"] and status["activation"] is None
    assert (await command(ws, entry, "recover", import_id=marker))["error"]["code"] == "candidate_conflict"
    assert panel.mutations() == ["recover"]


@pytest.mark.skipif(not shutil.which("node") or (os.environ.get("HA_BROWSER_MANAGED_PLAYWRIGHT") != "1" and
                    not Path("/usr/bin/chromium").exists()), reason="Chromium/Node required")
async def test_candidate_maintenance_in_chromium(hass, entry, panel, hass_client, hass_access_token):
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.setup import async_setup_component
    from custom_components.home_panel.frontend import async_setup_panel
    root = Path(__file__).resolve().parents[2]
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_panel(hass)
    await hass.http.async_register_static_paths([
        StaticPathConfig("/home_panel_browser_fixture", str(root / "tests/fixtures/ha_frontend"), False)])
    client = await hass_client()
    process = await asyncio.create_subprocess_exec("node", str(root / "tests/ha_frontend_apply.cjs"), cwd=root,
        env={**os.environ, "HA_BROWSER_ORIGIN":str(client.make_url("/")).rstrip("/"),
             "HA_BROWSER_TOKEN":hass_access_token, "HA_BROWSER_ENTRY":entry.entry_id,
             "HA_APPLY_OUTCOME":"maintenance"}, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 120)
        assert process.returncode == 0, stdout.decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await hass.async_block_till_done()
    assert panel.mutations() == ["discard", "recover"]
    assert panel.state["loaded_revision"] == 17 and panel.state["candidate"]["revision"] == 33
