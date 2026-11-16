"""One bounded host-model executor job per entry, across disconnected waiters."""

import asyncio

from homeassistant.core import HomeAssistant

from .const import DOMAIN

DATA_KEY = DOMAIN + "_model_checks"


class ModelCheckBusy(Exception):
    """A model check or change summary is already running for this entry."""


async def async_model_job(hass: HomeAssistant, entry_id: str, worker, *args) -> dict:
    tasks = hass.data.setdefault(DATA_KEY, {})
    if entry_id in tasks:
        raise ModelCheckBusy

    async def run():
        return await hass.async_add_executor_job(worker, *args)

    task = hass.async_create_task(run(), "Home Panel host model job")
    tasks[entry_id] = task

    def finished(completed):
        if tasks.get(entry_id) is completed:
            tasks.pop(entry_id)
        if not completed.cancelled():
            completed.exception()

    task.add_done_callback(finished)
    return await asyncio.shield(task)
