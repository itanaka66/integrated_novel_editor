import asyncio

from app import llm_queue
from app.config import settings


def test_second_call_waits_behind_the_first_and_is_listed(monkeypatch):
    monkeypatch.setattr(settings, "ollama_max_concurrency", 1)
    seen = {}

    async def scenario():
        gate = asyncio.Event()

        async def first():
            llm_queue.purpose.set("文章校正")
            async with llm_queue.slot(kind="writer", model="m", url="http://o"):
                await gate.wait()

        async def second():
            llm_queue.purpose.set("AIチャット")
            async with llm_queue.slot(kind="writer", model="m", url="http://o"):
                pass

        t1 = asyncio.create_task(first())
        await asyncio.sleep(0)
        t2 = asyncio.create_task(second())
        await asyncio.sleep(0.05)
        seen["during"] = llm_queue.snapshot()
        gate.set()
        await asyncio.gather(t1, t2)
        seen["after"] = llm_queue.snapshot()

    asyncio.run(scenario())
    during = seen["during"]
    assert [(e["state"], e["purpose"], e["position"]) for e in during] == [
        ("running", "文章校正", 1),
        ("waiting", "AIチャット", 2),
    ]
    assert seen["after"] == []


def test_different_models_do_not_wait_on_each_other(monkeypatch):
    monkeypatch.setattr(settings, "ollama_max_concurrency", 1)
    seen = {}

    async def scenario():
        gate = asyncio.Event()

        async def hold(model):
            async with llm_queue.slot(kind="writer", model=model, url="http://o"):
                await gate.wait()

        tasks = [asyncio.create_task(hold("a")), asyncio.create_task(hold("b"))]
        await asyncio.sleep(0.05)
        seen["states"] = [e["state"] for e in llm_queue.snapshot()]
        gate.set()
        await asyncio.gather(*tasks)

    asyncio.run(scenario())
    assert seen["states"] == ["running", "running"]


def test_zero_concurrency_never_waits_but_still_lists(monkeypatch):
    monkeypatch.setattr(settings, "ollama_max_concurrency", 0)
    seen = {}

    async def scenario():
        gate = asyncio.Event()

        async def hold():
            async with llm_queue.slot(kind="writer", model="m", url="http://o"):
                await gate.wait()

        tasks = [asyncio.create_task(hold()), asyncio.create_task(hold())]
        await asyncio.sleep(0.05)
        seen["states"] = [e["state"] for e in llm_queue.snapshot()]
        gate.set()
        await asyncio.gather(*tasks)

    asyncio.run(scenario())
    assert seen["states"] == ["running", "running"]


def test_entry_is_removed_when_the_call_fails(monkeypatch):
    monkeypatch.setattr(settings, "ollama_max_concurrency", 1)

    async def scenario():
        try:
            async with llm_queue.slot(kind="writer", model="m", url="http://o"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass

    asyncio.run(scenario())
    assert llm_queue.snapshot() == []


def test_queue_endpoint_requires_auth_and_returns_entries(client):
    r = client.get("/api/v1/llm/queue")
    assert r.status_code == 200
    body = r.json()
    assert body["entries"] == []
    assert body["max_concurrency"] == settings.ollama_max_concurrency


def test_queue_entries_name_the_novel(client, project, monkeypatch, db_session_factory):
    from app import db as app_db
    monkeypatch.setattr(app_db, 'SessionLocal', db_session_factory)
    import asyncio
    from app import llm_queue

    async def go():
        llm_queue.set_project(project["id"])
        async with llm_queue.slot(kind="writer", model="m", url="u"):
            return llm_queue.snapshot()
    snap = asyncio.run(go())
    assert snap[0]["project_id"] == project["id"] and snap[0]["project_name"] == project["name"]
