import time

from app import translator


def test_split_chunks_respects_limit_and_keeps_text():
    text = "\n".join(["あ" * 40] * 10)
    chunks = translator.split_chunks(text, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "\n".join(chunks) == text
    assert translator.split_chunks("x" * 250, limit=100) == ["x" * 100, "x" * 100, "x" * 50]


def test_translate_creates_new_project(client, project, monkeypatch, db_session_factory):
    async def fake_generate(prompt, *a, **k):
        return "EN:" + prompt.rsplit("\n\n", 1)[-1], "m"
    monkeypatch.setattr(translator, "generate", fake_generate)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "転移", "content": "少年は目覚めた。"})
    r = client.post(f"/api/v1/projects/{pid}/translate", json={"language": "en"})
    assert r.status_code == 200
    jid = r.json()["id"]
    for _ in range(50):
        j = client.get(f"/api/v1/translate-jobs/{jid}").json()
        if j["status"] in ("completed", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "completed", j
    assert j["project_id"] != pid and j["progress_percent"] == 100.0
    eps = client.get(f"/api/v1/projects/{j['project_id']}/episodes").json()
    assert client.get(f"/api/v1/projects/{j['project_id']}").json()["language"] == "en"
    assert eps[0]["title"] == "EN:転移" and eps[0]["content"] == "EN:少年は目覚めた。"
    assert client.get(f"/api/v1/projects/{pid}/episodes").json()[0]["content"] == "少年は目覚めた。"


def test_translate_rejects_unknown_language(client, project):
    assert client.post(f"/api/v1/projects/{project['id']}/translate", json={"language": "xx"}).status_code == 400


def test_retranslate_only_fills_missing_or_short_parts(client, project, monkeypatch, db_session_factory):
    import asyncio
    calls = []

    async def fake_generate(prompt, *a, **k):
        text = prompt.rsplit("\n\n", 1)[-1]
        calls.append(text)
        return "EN:" + text, "m"
    monkeypatch.setattr(translator, "generate", fake_generate)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    long_text = "少年は目覚めた。" * 20
    for n in (1, 2, 3):
        client.post(f"/api/v1/projects/{pid}/episodes", json={"number": n, "title": f"題{n}", "content": long_text})

    def run():
        async def go():
            job = translator.new_job(pid, "en")
            await translator.run_translation(job)
            return job
        return asyncio.run(go())
    first = run()
    assert first["status"] == "completed"
    dst = first["project_id"]
    eps = {e["number"]: e for e in client.get(f"/api/v1/projects/{dst}/episodes").json()}
    # Episode 2 was cut off, episode 3 was deleted from the translation.
    from app.models import Episode
    with db_session_factory() as db:
        db.get(Episode, eps[2]["id"]).content = "EN:少"
        db.delete(db.get(Episode, eps[3]["id"]))
        db.commit()
    calls.clear()
    second = run()
    assert second["status"] == "completed" and second["project_id"] == dst
    assert not any(c == "題1" or c == long_text and False for c in calls)
    assert "題1" not in calls and "題2" not in calls and "題3" in calls
    after = {e["number"]: e for e in client.get(f"/api/v1/projects/{dst}/episodes").json()}
    assert set(after) == {1, 2, 3} and after[2]["content"] == "EN:" + long_text and after[3]["content"] == "EN:" + long_text


def test_project_out_exposes_source_project_id(client, project, monkeypatch, db_session_factory):
    async def fake_generate(prompt, *a, **k):
        return "EN", "m"
    monkeypatch.setattr(translator, "generate", fake_generate)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "a", "content": "b"})
    jid = client.post(f"/api/v1/projects/{pid}/translate", json={"language": "en"}).json()["id"]
    for _ in range(80):
        j = client.get(f"/api/v1/translate-jobs/{jid}").json()
        if j["status"] in ("completed", "error"):
            break
        time.sleep(0.1)
    assert client.get(f"/api/v1/projects/{j['project_id']}").json()["source_project_id"] == pid
    assert client.get(f"/api/v1/projects/{pid}").json()["source_project_id"] is None


def test_digest_is_linked_to_its_source(client, project, monkeypatch):
    from app import digest as digest_mod
    pid = project["id"]
    for n in range(1, 5):
        client.post(f"/api/v1/projects/{pid}/episodes", json={"number": n, "title": f"t{n}", "content": "本文" * 50})
    async def fake_pick(*a, **k):
        return None
    r = client.post(f"/api/v1/projects/{pid}/digest", json={"ratio": 0.5})
    if r.status_code == 200:
        assert client.get(f"/api/v1/projects/{r.json()['project']['id']}").json()["source_project_id"] == pid


def test_translate_all_runs_on_the_server_and_lists_as_background_job(client, project, monkeypatch, db_session_factory):
    async def fake_generate(prompt, *a, **k):
        return "X", "m"
    monkeypatch.setattr(translator, "generate", fake_generate)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "a", "content": "b"})
    import asyncio
    langs = [c for c in translator.CORE_LANGUAGES if c != "ja"]
    job = translator.new_all_job(pid, langs)
    assert job["total_languages"] == 7
    asyncio.run(translator.run_all(job))
    j = client.get(f"/api/v1/translate-all-jobs/{job['id']}").json()
    assert j["status"] == "completed" and j["done_languages"] == 7 and j["failed"] == []
    assert client.get(f"/api/v1/projects/{pid}/translate-all").json()["id"] == j["id"]
    assert client.get("/api/v1/background-jobs").json() == {"jobs": []}


def test_episode_list_is_not_cut_off_at_200(client, project, db_session_factory):
    from app.models import Episode
    pid = project["id"]
    with db_session_factory() as db:
        db.add_all([Episode(project_id=pid, number=n, title=f"t{n}", content="") for n in range(1, 261)])
        db.commit()
    eps = client.get(f"/api/v1/projects/{pid}/episodes").json()
    assert len(eps) == 260 and eps[-1]["number"] == 260


def test_translate_job_can_be_cancelled_and_resumed(client, project, monkeypatch, db_session_factory):
    import asyncio
    from app.models import Episode, Project

    async def slow_generate(prompt, *a, **k):
        await asyncio.sleep(0.2)
        return "Y" * 30, "m"
    monkeypatch.setattr(translator, "generate", slow_generate)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    with db_session_factory() as db:
        db.add_all([Episode(project_id=pid, number=n, title=f"t{n}", content="本文" * 30) for n in range(1, 6)])
        db.commit()

    async def go():
        job = translator.new_job(pid, "en")
        task = asyncio.create_task(translator.run_translation(job))
        translator.running[job["id"]] = task
        await asyncio.sleep(0.7)
        assert job["status"] == "running"
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return job
    job = asyncio.run(go())
    assert job["status"] == "cancelled" and "キャンセル" in job["last_message"]
    # What was already translated stays, and a second run continues from it.
    with db_session_factory() as db:
        dst = db.query(Project).filter(Project.source_project_id == pid).one()
        done_before = db.query(Episode).filter_by(project_id=dst.id).count()
    assert 0 <= done_before < 5

    async def again():
        j2 = translator.new_job(pid, "en")
        await translator.run_translation(j2)
        return j2
    j2 = asyncio.run(again())
    assert j2["status"] == "completed" and j2["project_id"] == dst.id
    assert client.post("/api/v1/background-jobs/cancel", json={"kind": "translate", "id": job["id"]}).status_code == 404
    assert client.post("/api/v1/background-jobs/cancel", json={"kind": "nope", "id": 1}).status_code == 400





def test_unfinished_translation_resumes_after_a_restart(client, project, monkeypatch, db_session_factory):
    import asyncio
    from app.models import Episode, Project

    async def fake_generate(prompt, *a, **k):
        return "Z" * 30, "m"
    monkeypatch.setattr(translator, "generate", fake_generate)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    with db_session_factory() as db:
        db.add_all([Episode(project_id=pid, number=n, title=f"t{n}", content="本文" * 30) for n in range(1, 4)])
        db.commit()
    job = translator.new_job(pid, "en")  # saved to disk, status 'queued'
    job["status"] = "running"
    translator._persist()
    translator.jobs.clear()  # "the server restarted": memory is gone

    async def go():
        assert translator.resume_unfinished() == 1
        await asyncio.gather(*list(translator.running.values()))
        return translator.jobs[job["id"]]
    j = asyncio.run(go())
    assert j["status"] == "completed" and j["processed_episodes"] == 3
    with db_session_factory() as db:
        assert db.query(Project).filter(Project.source_project_id == pid).count() == 1
    # a new job after the restart does not reuse the old id
    assert translator.new_job(pid, "fr")["id"] > job["id"]
    assert client.get(f"/api/v1/projects/{pid}/translate-jobs").json()[0]["id"] >= job["id"]


def test_translation_model_is_separate_and_defaults_to_the_controller(client):
    s = client.get("/api/v1/system-settings").json()
    assert s["translator_ollama_model"] == s["controller_ollama_model"] and not s["translator_ollama_model_is_override"]
    r = client.put("/api/v1/system-settings", json={"translator_ollama_model": "trans-model", "translator_ollama_url": "http://t:11434"}).json()
    assert r["translator_ollama_model"] == "trans-model" and r["translator_ollama_model_is_override"]
    assert r["translator_ollama_url"] == "http://t:11434" and r["controller_ollama_model"] == s["controller_ollama_model"]
    back = client.put("/api/v1/system-settings", json={"translator_ollama_model": "", "translator_ollama_url": ""}).json()
    assert back["translator_ollama_model"] == s["controller_ollama_model"] and not back["translator_ollama_model_is_override"]


def test_translation_uses_the_translator_model(monkeypatch):
    from app import ollama
    assert translator.generate is ollama.translator_generate


def test_clean_translation_strips_model_wrappers_but_not_content():
    c = translator.clean_translation
    assert c("<think>考え中…\nstep 1</think>\n\nHello, world.") == "Hello, world."
    assert c("reasoning without an opening tag</think>Bonjour.") == "Bonjour."
    assert c("```text\nHallo Welt\n```") == "Hallo Welt"
    assert c("Here is the translation:\n\nHe woke up.") == "He woke up."
    assert c("Sure! Here's the English translation:\nHe woke up.\nShe smiled.") == "He woke up.\nShe smiled."
    assert c("以下が翻訳です：\n\n彼は目覚めた。") == "彼は目覚めた。"
    assert c("He woke up.\n\nNote: I kept the honorific.") == "He woke up."
    assert c("He woke up.\n\nI hope this helps!") == "He woke up."
    assert c("訳文です。\n\n（訳注：原文は敬語）") == "訳文です。"
    # real content stays: a story line that merely starts like a preface, notes inside the text
    assert c("Here is the thing: he left.") == "Here is the thing: he left."
    assert c("Translation is hard, he said.\nShe nodded.") == "Translation is hard, he said.\nShe nodded."
    assert c("He wrote a note: meet me.\n\nNote the time.") == "He wrote a note: meet me.\n\nNote the time."
    assert c("Line one.\n\nLine two.") == "Line one.\n\nLine two."
    assert c("  ") == ""


def test_translate_text_cleans_each_chunk(monkeypatch):
    import asyncio

    async def noisy(prompt, *a, **k):
        return "<think>x</think>Here is the translation:\nOK.\n\nNote: done", "m"
    monkeypatch.setattr(translator, "generate", noisy)
    assert asyncio.run(translator.translate_text("あ", "en")) == "OK."


JA = ("夜明け前の集落に、乾いた風が吹いていた。\n「起きろ、ガルド。恐竜が柵を越えた」\n"
      "リナの声に、ガルドは毛皮の寝床から跳ね起きた。槍を掴み、焚き火の残り火を蹴り散らして外へ出る。")


def test_bad_translation_detection():
    bad = translator.bad_translation
    assert bad(JA, "The village before dawn was swept by a dry wind.\n“Wake up.”\nAt Lina's voice, Galdo sprang up and went out.", "en") == ""
    assert bad(JA, JA, "ko") == "untranslated"  # model returned the Japanese unchanged
    assert bad(JA, "« Lève-toi. »\nリナの声に、ガルドは毛皮の寝床から跳ね起きた。槍を掴み、焚き火の残り火を蹴り散らして外へ出る。", "fr") == "untranslated"
    assert bad(JA, "Wake.", "en") == "too short"
    assert bad(JA, "夜明け前、風が吹いていた。「起きろ」とリナが言った。ガルドは跳ね起きて外へ出た。", "zh-CN") == "untranslated"
    assert bad(JA, "黎明前的聚落里吹着干燥的风。“起来，嘎尔德。恐龙越过了围栏。”莉娜的声音让他从毛皮床上跳了起来。", "zh-CN") == ""
    assert bad("short", "x", "en") == ""  # too little text to judge
    assert bad("a long english source sentence that needs translating into Japanese for the reader", "これは翻訳です。長い英語の文章が日本語になりました。", "ja") == ""


def test_translate_text_retries_once_when_the_model_returns_the_source(monkeypatch):
    import asyncio
    calls = []

    async def gen(prompt, *a, **k):
        calls.append(prompt)
        if len(calls) == 1:
            return JA, "m"  # the lazy answer
        return "The village before dawn was swept by a dry wind.\n“Wake up, Gard.”\nAt Lina's voice, Gard sprang up and went out.", "m"
    monkeypatch.setattr(translator, "generate", gen)
    out = asyncio.run(translator.translate_text(JA, "en"))
    assert out.startswith("The village") and len(calls) == 2
    assert "IMPORTANT" in calls[1] and "entirely in English" in calls[0]


def test_translate_text_keeps_the_better_answer_when_retry_also_fails(monkeypatch):
    import asyncio

    async def gen(prompt, *a, **k):
        return JA, "m"
    monkeypatch.setattr(translator, "generate", gen)
    assert asyncio.run(translator.translate_text(JA, "ko")) == JA.strip()


def test_translator_adds_no_think_for_qwen3_and_uses_the_configured_timeout(monkeypatch):
    import asyncio
    from app import ollama
    from app.config import settings
    seen = {}

    async def fake_generate(prompt, model=None, url=None, timeout=240, options=None, api_key=None, kind='writer'):
        seen.update(prompt=prompt, model=model, timeout=timeout, kind=kind)
        return "ok", model
    monkeypatch.setattr(ollama, "generate", fake_generate)
    monkeypatch.setattr(settings, "translator_timeout_seconds", 321)

    class Cfg:
        translator_ollama_model = "qwen3:14b"
        translator_ollama_url = "http://x"
        translator_pool = []
    monkeypatch.setattr(ollama, "get_effective_config", lambda: Cfg())
    asyncio.run(ollama.translator_generate("translate this"))
    assert seen["prompt"].endswith("/no_think") and seen["timeout"] == 321 and seen["kind"] == "translator"
    Cfg.translator_ollama_model = "gemma3:12b"
    asyncio.run(ollama.translator_generate("translate this"))
    assert not seen["prompt"].endswith("/no_think")


LONG_JA = "夜明け前の集落に、乾いた風が吹いていた。\n「起きろ、ガルド。恐竜が柵を越えた」\nリナの声に、ガルドは毛皮の寝床から跳ね起きた。槍を掴み、焚き火の残り火を蹴り散らして外へ出る。東の空はまだ暗く、遠くで巨大な影がゆっくりと動いている。"
GOOD_EN = "The village before dawn was swept by a dry wind.\n“Wake up, Gard. A dinosaur has crossed the fence.”\nAt Lina's voice, Gard sprang from his fur bed, grabbed his spear, kicked the embers apart and stepped outside. The eastern sky was still dark, and a huge shadow moved slowly in the distance."
OMITTED_EN = "The village before dawn was swept by a dry wind.\n“Wake up, Gard.”\nAt Lina's voice, Gard sprang from his fur bed, grabbed his spear and stepped outside. The eastern sky was still dark and a huge shadow moved slowly in the distance."


def test_review_finds_an_omission_and_the_chunk_is_translated_again(monkeypatch):
    import asyncio
    from app.config import settings
    monkeypatch.setattr(settings, "translation_review", True)
    gen_prompts, review_prompts = [], []

    async def gen(prompt, *a, **k):
        gen_prompts.append(prompt)
        return (OMITTED_EN if len(gen_prompts) == 1 else GOOD_EN), "m"

    async def review(prompt, *a, **k):
        review_prompts.append(prompt)
        return '<think></think>{"ok": false, "issues": ["「恐竜が柵を越えた」が訳されていない"]}', "m"
    monkeypatch.setattr(translator, "generate", gen)
    monkeypatch.setattr(translator, "review_generate", review)
    stats = {}
    out = asyncio.run(translator.translate_text(LONG_JA, "en", "", stats=stats))
    assert out == GOOD_EN and stats == {"reviewed": 1, "fixed": 1}
    assert "SOURCE:" in review_prompts[0] and "恐竜が柵を越えた" in review_prompts[0]
    assert "reviewer found these problems" in gen_prompts[1] and "恐竜が柵を越えた」が訳されていない" in gen_prompts[1]


def test_review_ok_keeps_the_translation_and_a_broken_checker_is_ignored(monkeypatch):
    import asyncio
    from app.config import settings
    monkeypatch.setattr(settings, "translation_review", True)
    calls = {"gen": 0}

    async def gen(prompt, *a, **k):
        calls["gen"] += 1
        return GOOD_EN, "m"
    monkeypatch.setattr(translator, "generate", gen)

    async def ok(prompt, *a, **k):
        return '{"ok": true}', "m"
    monkeypatch.setattr(translator, "review_generate", ok)
    stats = {}
    assert asyncio.run(translator.translate_text(LONG_JA, "en", "", stats=stats)) == GOOD_EN
    assert calls["gen"] == 1 and stats == {"reviewed": 1}

    async def broken(prompt, *a, **k):
        raise RuntimeError("controller down")
    monkeypatch.setattr(translator, "review_generate", broken)
    assert asyncio.run(translator.translate_text(LONG_JA, "en")) == GOOD_EN and calls["gen"] == 2

    async def garbage(prompt, *a, **k):
        return "I think it looks fine!", "m"
    monkeypatch.setattr(translator, "review_generate", garbage)
    assert asyncio.run(translator.translate_text(LONG_JA, "en")) == GOOD_EN and calls["gen"] == 3


def test_review_is_skipped_for_short_text_and_when_disabled(monkeypatch):
    import asyncio
    from app.config import settings

    async def gen(prompt, *a, **k):
        return "Title", "m"

    async def review(prompt, *a, **k):
        raise AssertionError("must not be called")
    monkeypatch.setattr(translator, "generate", gen)
    monkeypatch.setattr(translator, "review_generate", review)
    monkeypatch.setattr(settings, "translation_review", True)
    assert asyncio.run(translator.translate_text("題名", "en")) == "Title"  # shorter than REVIEW_MIN_CHARS
    monkeypatch.setattr(settings, "translation_review", False)
    assert asyncio.run(translator.translate_text(LONG_JA, "en")) == "Title"  # switched off


def test_reviewer_uses_the_controller_with_no_think_for_qwen3(monkeypatch):
    import asyncio
    from app import ollama
    seen = {}

    async def fake_generate(prompt, model=None, url=None, timeout=240, options=None, api_key=None, kind='writer'):
        seen.update(prompt=prompt, model=model, url=url, kind=kind)
        return "{}", model
    monkeypatch.setattr(ollama, "generate", fake_generate)

    class Cfg:
        controller_ollama_model = "qwen3:14b"
        controller_ollama_url = "http://ctrl"
    monkeypatch.setattr(ollama, "get_effective_config", lambda: Cfg())
    asyncio.run(ollama.reviewer_generate("check"))
    assert seen["model"] == "qwen3:14b" and seen["url"] == "http://ctrl" and seen["kind"] == "controller" and seen["prompt"].endswith("/no_think")


def test_omission_check_retranslates_with_the_missing_sentence_named(monkeypatch):
    import asyncio
    from app.config import settings
    monkeypatch.setattr(settings, "translation_omission_check", True)
    prompts = []

    async def gen(prompt, *a, **k):
        prompts.append(prompt)
        return (OMITTED_EN if len(prompts) == 1 else GOOD_EN), "m"
    monkeypatch.setattr(translator, "generate", gen)
    state = {"calls": 0}

    async def fake_find(src, out, embed):
        state["calls"] += 1
        return ["恐竜が柵を越えた」"] if out == OMITTED_EN else []
    monkeypatch.setattr(translator, "find_omissions", fake_find)
    stats = {}
    out = asyncio.run(translator.translate_text(LONG_JA, "en", "", stats=stats))
    assert out == GOOD_EN and stats == {"omissions_fixed": 1}
    assert "次の文が訳されていません: 恐竜が柵を越えた」" in prompts[1]


def test_omission_check_keeps_the_first_answer_when_the_retry_is_no_better(monkeypatch):
    import asyncio
    from app.config import settings
    monkeypatch.setattr(settings, "translation_omission_check", True)

    async def gen(prompt, *a, **k):
        return OMITTED_EN, "m"
    monkeypatch.setattr(translator, "generate", gen)

    async def fake_find(src, out, embed):
        return ["恐竜が柵を越えた」"]
    monkeypatch.setattr(translator, "find_omissions", fake_find)
    assert asyncio.run(translator.translate_text(LONG_JA, "en")) == OMITTED_EN


ALL_LANGS = ["ja", "en", "zh-CN", "ko", "es", "fr", "de", "pt-BR", "it", "other"]


class _PoolCfg:
    translator_ollama_url = "http://ctrl:11434"
    translator_ollama_model = "qwen3:14b"
    translator_pool = [{"url": "http://t1:11434", "model": "qwen3:8b"}, {"url": "http://t2:11434", "model": "qwen3:8b"},
                       {"url": "http://t3:11434", "model": "gemma3:12b"}]


def test_translator_calls_spread_over_idle_translation_llms(monkeypatch):
    import asyncio
    from app import ollama
    seen = []

    async def fake_generate(prompt, model=None, url=None, timeout=240, options=None, api_key=None, kind='writer'):
        seen.append((url, model, prompt))
        await asyncio.sleep(0.05)
        return "ok", model
    monkeypatch.setattr(ollama, "generate", fake_generate)
    monkeypatch.setattr(ollama, "get_effective_config", lambda: _PoolCfg())

    async def go():
        await asyncio.gather(*(ollama.translator_generate(f"p{i}") for i in range(3)))
        await asyncio.gather(*(ollama.translator_generate(f"q{i}") for i in range(3)))
    asyncio.run(go())
    first, second = {u for u, _, _ in seen[:3]}, {u for u, _, _ in seen[3:]}
    assert first == second == {"http://t1:11434", "http://t2:11434", "http://t3:11434"}  # three at once go to three LLMs
    assert not any(u == "http://ctrl:11434" for u, _, _ in seen)  # the Controller is not used while others exist
    assert next(p for u, m, p in seen if m == "qwen3:8b").endswith("/no_think")
    assert not next(p for u, m, p in seen if m == "gemma3:12b").endswith("/no_think")
    assert not any(v for v in ollama._busy.values())  # nothing left marked busy


def test_controller_translates_when_no_other_translation_llm_exists(monkeypatch):
    import asyncio
    from app import ollama
    seen = []

    async def fake_generate(prompt, model=None, url=None, timeout=240, options=None, api_key=None, kind='writer'):
        seen.append((url, model))
        return "ok", model

    class NoPool(_PoolCfg):
        translator_pool = []
    monkeypatch.setattr(ollama, "generate", fake_generate)
    monkeypatch.setattr(ollama, "get_effective_config", lambda: NoPool())
    asyncio.run(ollama.translator_generate("x"))
    assert seen == [("http://ctrl:11434", "qwen3:14b")]
    assert ollama.translator_endpoints(NoPool()) == [{"url": "http://ctrl:11434", "model": "qwen3:14b"}]


def test_episodes_are_translated_in_parallel_across_the_pool(client, project, monkeypatch, db_session_factory):
    import asyncio
    from app.models import Episode
    running = {"now": 0, "max": 0}

    async def slow(prompt, *a, **k):
        running["now"] += 1
        running["max"] = max(running["max"], running["now"])
        await asyncio.sleep(0.05)
        running["now"] -= 1
        return "T" * 40, "m"
    monkeypatch.setattr(translator, "generate", slow)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    monkeypatch.setattr(translator, "translator_count", lambda language=None: 3)
    pid = project["id"]
    with db_session_factory() as db:
        db.add_all([Episode(project_id=pid, number=n, title=f"t{n}", content="本文" * 30) for n in range(1, 7)])
        db.commit()

    async def go():
        job = translator.new_job(pid, "en")
        await translator.run_translation(job)
        return job
    job = asyncio.run(go())
    assert job["status"] == "completed" and job["processed_episodes"] == 6
    assert 2 <= running["max"] <= 12  # several calls ran at once (3 episodes x their fields)
    with db_session_factory() as db:
        dst = db.query(translator.Project).filter(translator.Project.source_project_id == pid).one()
        nums = [e.number for e in db.query(Episode).filter_by(project_id=dst.id).order_by(Episode.number)]
    assert nums == [1, 2, 3, 4, 5, 6]


def test_translator_pool_setting_round_trip_and_validation(client):
    s = client.get("/api/v1/system-settings").json()
    assert s["translator_pool"] == []
    pool = [{"url": "http://a:11434/", "model": "qwen3:8b"}, {"url": "http://b:11434", "model": "qwen3:8b"}, {"url": "http://a:11434", "model": "qwen3:8b"}, {"url": "", "model": "x"}]
    r = client.put("/api/v1/system-settings", json={"translator_pool": pool}).json()
    assert r["translator_pool"] == [{"url": "http://a:11434", "model": "qwen3:8b", "enabled": True, "languages": ALL_LANGS, "v": 2}, {"url": "http://b:11434", "model": "qwen3:8b", "enabled": True, "languages": ALL_LANGS, "v": 2}]  # trimmed, de-duplicated, enabled by default
    pool2 = [{"url": "http://a:11434", "model": "qwen3:8b", "enabled": False}, {"url": "http://b:11434", "model": "qwen3:8b"}]
    assert [p["enabled"] for p in client.put("/api/v1/system-settings", json={"translator_pool": pool2}).json()["translator_pool"]] == [False, True]  # the toggle is kept
    assert client.put("/api/v1/system-settings", json={"translator_pool": [{"url": "ftp://x", "model": "m"}]}).status_code == 400
    assert client.put("/api/v1/system-settings", json={"translator_pool": [{"url": f"http://h{i}", "model": "m"} for i in range(9)]}).status_code == 400
    assert client.put("/api/v1/system-settings", json={"translator_pool": []}).json()["translator_pool"] == []


def test_disabled_translation_llms_are_listed_but_not_used():
    from app import ollama

    class Cfg(_PoolCfg):
        translator_pool = [{"url": "http://t1:11434", "model": "m", "enabled": False}, {"url": "http://t2:11434", "model": "m", "enabled": True},
                           {"url": "http://t3:11434", "model": "m"}]  # a missing flag means enabled
    assert [e["url"] for e in ollama.translator_endpoints(Cfg())] == ["http://t2:11434", "http://t3:11434"]

    class AllOff(_PoolCfg):
        translator_pool = [{"url": "http://t1:11434", "model": "m", "enabled": False}]
    # nothing enabled -> the Controller translates (same as an empty list)
    assert ollama.translator_endpoints(AllOff()) == [{"url": "http://ctrl:11434", "model": "qwen3:14b"}]


def test_translation_llms_are_chosen_by_target_language(monkeypatch):
    import asyncio
    from app import ollama

    class Cfg(_PoolCfg):
        translator_pool = [
            {"url": "http://en:11434", "model": "m", "enabled": True, "languages": ["en", "fr"]},
            {"url": "http://cjk:11434", "model": "m", "enabled": True, "languages": ["ja", "zh-CN", "ko"]},
            {"url": "http://off:11434", "model": "m", "enabled": False, "languages": ["en", "ko"]},
            {"url": "http://old:11434", "model": "m"},  # saved before languages existed: handles anything
        ]
    urls = lambda lang: [e["url"] for e in ollama.translator_endpoints(Cfg(), lang)]  # noqa: E731
    assert urls("en") == ["http://en:11434", "http://old:11434"]
    assert urls("ko") == ["http://cjk:11434", "http://old:11434"]
    assert urls("de") == ["http://old:11434"]
    assert len(urls(None)) == 3

    class Narrow(_PoolCfg):
        translator_pool = [{"url": "http://en:11434", "model": "m", "enabled": True, "languages": ["en"]}]
    # no enabled LLM handles Korean -> the Controller translates it
    assert ollama.translator_endpoints(Narrow(), "ko") == [{"url": "http://ctrl:11434", "model": "qwen3:14b"}]

    seen = []

    async def fake_generate(prompt, model=None, url=None, timeout=240, options=None, api_key=None, kind='writer'):
        seen.append(url)
        return "ok", model
    monkeypatch.setattr(ollama, "generate", fake_generate)
    monkeypatch.setattr(ollama, "get_effective_config", lambda: Cfg())

    async def go():
        for _ in range(4):
            await ollama.translator_generate("x", language="ko")
    asyncio.run(go())
    assert set(seen) <= {"http://cjk:11434", "http://old:11434"} and "http://en:11434" not in seen


def test_language_boxes_round_trip_and_default_to_all(client):
    pool = [{"url": "http://a:11434", "model": "m", "languages": ["en", "xx", "ko"]}, {"url": "http://b:11434", "model": "m"}]
    got = client.put("/api/v1/system-settings", json={"translator_pool": pool}).json()["translator_pool"]
    assert got[0]["languages"] == ["en", "ko"]  # unknown codes dropped, canonical order kept
    assert got[1]["languages"] == ["ja", "en", "zh-CN", "ko", "es", "fr", "de", "pt-BR", "it", "other"]  # nothing given = all
    got2 = client.put("/api/v1/system-settings", json={"translator_pool": [{"url": "http://a:11434", "model": "m", "languages": []}]}).json()["translator_pool"]
    assert got2[0]["languages"] == []  # an explicitly empty list is kept (the row handles nothing)


def test_same_work_and_language_never_translates_twice_at_once(client, project, monkeypatch, db_session_factory):
    import asyncio
    from app.models import Episode, Project
    calls = []
    running = {"now": 0, "max": 0}

    async def slow(prompt, *a, **k):
        calls.append(prompt)
        running["now"] += 1
        running["max"] = max(running["max"], running["now"])
        await asyncio.sleep(0.03)
        running["now"] -= 1
        return "T" * 40, "m"
    monkeypatch.setattr(translator, "generate", slow)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    with db_session_factory() as db:
        db.add_all([Episode(project_id=pid, number=n, title=f"t{n}", content="本文" * 30) for n in range(1, 4)])
        db.commit()

    async def go():
        a, b = translator.new_job(pid, "en"), translator.new_job(pid, "en")  # e.g. a double click
        await asyncio.gather(translator.run_translation(a), translator.run_translation(b))
        return a, b
    a, b = asyncio.run(go())
    assert a["status"] == b["status"] == "completed"
    assert running["max"] == 1  # one at a time (translator_count is 1 here and the jobs did not overlap)
    with db_session_factory() as db:
        dsts = db.query(Project).filter(Project.source_project_id == pid).all()
        assert len(dsts) == 1  # one translated work, not two
        nums = sorted(e.number for e in db.query(Episode).filter_by(project_id=dsts[0].id))
    assert nums == [1, 2, 3]  # each episode exactly once
    body_calls = [c for c in calls if c.rstrip().endswith("本文" * 30)]
    assert len(body_calls) == 3  # every episode body was translated once - the second job did not repeat any
    assert a["processed_episodes"] + b["processed_episodes"] == 6  # the later one counted them as already done


def test_translate_endpoint_returns_the_running_job_instead_of_starting_another(client, project):
    pid = project["id"]
    translator.jobs.clear()  # other tests leave jobs behind; ids of projects repeat across tests

    class LiveTask:
        def done(self):
            return False
    running = translator.new_job(pid, "fr")
    running["status"] = "running"
    translator.running[running["id"]] = LiveTask()
    r = client.post(f"/api/v1/projects/{pid}/translate", json={"language": "fr"}).json()
    assert r["id"] == running["id"]
    other = translator.new_job(pid, "de")
    other["status"] = "completed"  # a finished job does not block a new one
    assert translator.active_job_for(pid, "de") is None
    running["status"] = "completed"
    translator.running.pop(running["id"], None)
    stale = translator.new_job(pid, "es")
    stale["status"] = "running"  # no live task behind it (e.g. left over): must not block a new translation
    assert translator.active_job_for(pid, "es") is None


def test_one_episode_is_translated_by_a_single_llm_but_episodes_spread(monkeypatch):
    import asyncio
    from types import SimpleNamespace as NS
    from app import ollama
    used = {}

    async def fake_generate(prompt, model=None, url=None, timeout=240, options=None, api_key=None, kind='writer'):
        used.setdefault(prompt.rsplit("\n\n", 1)[-1][:12], []).append(url)
        await asyncio.sleep(0.02)
        return "T" * 60, model
    monkeypatch.setattr(ollama, "generate", fake_generate)
    monkeypatch.setattr(ollama, "get_effective_config", lambda: _PoolCfg())
    monkeypatch.setattr(translator, "pin_translator", ollama.pin_translator)  # the suite stubs it out by default
    monkeypatch.setattr(translator, "generate", ollama.translator_generate)
    long_a = "\n".join(["あ" * 400] * 20)  # several chunks
    long_b = "\n".join(["い" * 400] * 20)
    ep = lambda n, body: NS(number=n, title=f"題{n}", summary="要約" * 5, chapter="", content=body)  # noqa: E731

    async def go():
        job = {}
        return await asyncio.gather(translator._translate_episode(ep(1, long_a), None, "en", "", job),
                                    translator._translate_episode(ep(2, long_b), None, "en", "", job))
    a, b = asyncio.run(go())
    assert len(translator.split_chunks(long_a)) >= 3 and a["content"] and b["content"]
    urls_a = {u for k, v in used.items() if k.startswith("あ") for u in v}
    urls_b = {u for k, v in used.items() if k.startswith("い") for u in v}
    assert len(urls_a) == 1 and len(urls_b) == 1  # every chunk of an episode on the same LLM
    assert urls_a != urls_b  # the two episodes were given different LLMs
    assert not any(ollama._busy.values())  # busy counters are released


def test_more_languages_are_supported_end_to_end(client, project):
    from app import export
    assert len(translator.LANGUAGES) == 22 and {"it", "nl", "pl", "uk", "tr", "ar", "hi", "vi", "th", "id", "sv", "el", "fa", "ms"} <= set(translator.LANGUAGES)
    assert set(translator.LANGUAGES) == set(translator._PROMPT_LANG) == set(export.LABELS)  # every language has a prompt name and export wording
    assert translator.CORE_LANGUAGES == ("ja", "en", "zh-CN", "ko", "es", "fr", "de", "pt-BR")  # 全翻訳 keeps the eight
    pid = project["id"]
    translator.jobs.clear()
    assert client.post(f"/api/v1/projects/{pid}/translate", json={"language": "xx"}).status_code == 400
    # the untranslated-source check works for every target language
    jp = "夜明け前の集落に、乾いた風が吹いていた。リナの声に、ガルドは毛皮の寝床から跳ね起きた。槍を掴み外へ出た。"
    for lang in ("it", "ar", "th", "hi", "uk", "el", "fa", "vi"):
        assert translator.bad_translation(jp, jp, lang) == "untranslated"
    assert translator.bad_translation(jp, "Prima dell'alba un vento secco soffiava sul villaggio. Alla voce di Lina, Gard saltò giù dal letto di pelliccia.", "it") == ""


def test_other_languages_are_governed_by_the_italian_and_other_boxes():
    from app import ollama
    class Cfg(_PoolCfg):
        translator_pool = [
            {"url": "http://main:11434", "model": "m", "enabled": True, "languages": ["ja", "en"]},
            {"url": "http://it:11434", "model": "m", "enabled": True, "languages": ["it"]},
            {"url": "http://rest:11434", "model": "m", "enabled": True, "languages": ["other"]},
        ]
    urls = lambda lang: [e["url"] for e in ollama.translator_endpoints(Cfg(), lang)]  # noqa: E731
    assert urls("it") == ["http://it:11434"]
    assert urls("th") == urls("ar") == urls("ms") == ["http://rest:11434"]  # every language without its own box -> 'other'
    assert urls("en") == ["http://main:11434"]
    class NoOther(_PoolCfg):
        translator_pool = [{"url": "http://main:11434", "model": "m", "enabled": True, "languages": ["ja", "en", "it"]}]
    assert ollama.translator_endpoints(NoOther(), "pl") == [{"url": "http://ctrl:11434", "model": "qwen3:14b"}]  # nobody handles 'other' -> Controller


def test_legacy_all_eight_selection_means_everything_but_a_new_save_is_exact():
    from app import runtime_config as rc
    import json
    old8 = ["ja", "en", "zh-CN", "ko", "es", "fr", "de", "pt-BR"]
    legacy = rc.parse_pool(json.dumps([{"url": "http://a", "model": "m", "languages": old8}, {"url": "http://b", "model": "m", "languages": ["en", "fr"]}]))
    assert legacy[0]["languages"] == old8 + ["it", "other"]  # saved when "all" meant the eight
    assert legacy[1]["languages"] == ["en", "fr"]  # a deliberate subset stays
    resaved = rc.parse_pool(json.dumps([{"url": "http://a", "model": "m", "languages": old8, "v": 2}]))
    assert resaved[0]["languages"] == old8  # an exact selection saved by the new UI is not upgraded


def _run_all_with_tracking(db_session_factory, project_id, langs, monkeypatch, limit=None):
    import asyncio
    from app.config import settings
    inflight, peak, started = set(), [0], []

    async def gen(prompt, *a, language=None, **k):
        inflight.add(language)
        started.append(language)
        peak[0] = max(peak[0], len(inflight))
        await asyncio.sleep(0.05)
        inflight.discard(language)
        return "T" * 40, "m"
    monkeypatch.setattr(translator, "generate", gen)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    if limit is not None:
        monkeypatch.setattr(settings, "translation_parallel_languages", limit)
    job = translator.new_all_job(project_id, langs)
    asyncio.run(translator.run_all(job))
    return job, peak[0], started


def test_translate_all_runs_up_to_four_languages_at_once(client, project, monkeypatch, db_session_factory):
    from app.models import Episode
    pid = project["id"]
    with db_session_factory() as db:
        db.add(Episode(project_id=pid, number=1, title="t", content="本文" * 30))
        db.commit()
    langs = ["en", "ko", "fr", "de", "es", "zh-CN"]
    job, peak, _ = _run_all_with_tracking(db_session_factory, pid, langs, monkeypatch)
    assert job["status"] == "completed" and job["done_languages"] == 6 and job["failed"] == []
    assert peak == 4  # the default limit: four languages at the same time, the rest as slots free up
    assert sorted(job["finished_languages"]) == sorted(langs) and len(job["project_ids"]) == 6


def test_translate_all_parallel_limit_is_configurable(client, project, monkeypatch, db_session_factory):
    from app.models import Episode
    pid = project["id"]
    with db_session_factory() as db:
        db.add(Episode(project_id=pid, number=1, title="t", content="本文" * 30))
        db.commit()
    job, peak, _ = _run_all_with_tracking(db_session_factory, pid, ["en", "ko", "fr", "de"], monkeypatch, limit=2)
    assert job["status"] == "completed" and peak == 2
    translator.jobs.clear()
    job1, peak1, _ = _run_all_with_tracking(db_session_factory, pid, ["it", "nl"], monkeypatch, limit=1)
    assert peak1 == 1  # 1 = the old one-after-another behaviour


def test_resumed_translate_all_skips_the_finished_languages(client, project, monkeypatch, db_session_factory):
    from app.models import Episode
    pid = project["id"]
    with db_session_factory() as db:
        db.add(Episode(project_id=pid, number=1, title="t", content="本文" * 30))
        db.commit()
    import asyncio
    async def gen(prompt, *a, language=None, **k):
        started.add(language)
        return "T" * 40, "m"
    started = set()
    monkeypatch.setattr(translator, "generate", gen)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    job = translator.new_all_job(pid, ["en", "ko", "fr"])
    job["finished_languages"] = ["en"]  # as restored from translate_jobs.json
    asyncio.run(translator.run_all(job))
    assert started == {"ko", "fr"} and job["done_languages"] == 3 and job["status"] == "completed"
    old = translator.new_all_job(pid, ["en", "ko", "fr"])
    old["done_languages"] = 2  # saved by the older one-after-another version
    asyncio.run(translator.run_all(old))
    assert len(old["project_ids"]) == 1 and old["finished_languages"] == ["en", "ko", "fr"]  # only the third language was run (its work already existed, so nothing needed translating)
