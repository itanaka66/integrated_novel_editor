"""
Anna-driven auto-write step engine.

Each call to get_next_step() returns the next LLM prompt to execute (or done=True).
Each call to apply_step_result() processes the LLM response and advances job state.

The ine-bridge calls these endpoints in a loop:
  GET /auto-write/{id}/next-step  →  get_next_step()
  POST /auto-write/{id}/submit-step  →  apply_step_result()
"""
import asyncio
import json
import re
import uuid

from sqlalchemy import select

from .db import SessionLocal
from .models import AutoWriteJob, Project, Episode, SeriesPlan, ArcPlan, MiniArcPlan, EpisodePlan
from .context import build
from .planner.series_planner import PROMPT as _SERIES_PROMPT
from .planner.arc_planner import PROMPT as _ARC_PROMPT
from .planner.mini_arc_planner import PROMPT as _MINI_PROMPT
from .planner.episode_planner import PROMPT as _EPISODE_PROMPT
from .rag import index
from .continuity import (
    update_character_states, update_plot_statuses,
    update_foreshadowing_statuses, check_continuity,
)

_WRITER_PROMPT = (
    'あなたはWriter AIです。EP.{n}の完成した日本語小説本文だけを出力してください。\n'
    'Controllerが決めた計画とStory Digital Twinを厳守してください。\n'
    '【Series】{series}\n'
    '【Arc】{arc}\n'
    '【Mini Arc】{mini}\n'
    '【Episode Blueprint】{plan}\n'
    '【Story Digital Twin】{ctx}\n'
    '【作品ルール】{rules}'
)

_GATE_PROMPT = (
    'あなたはStory Controller / Quality Gateです。\n'
    '500話シリーズの上位計画を守り、本文を正本化する前に監査します。\n'
    '担当は「時系列・人物状態・世界観・プロット」の4項目だけです。文章表現の評価はしません。\n'
    'SERIES={series}\n'
    'ARC={arc}\n'
    'MINI_ARC={mini}\n'
    'EPISODE_PLAN={plan}\n'
    'STORY_TWIN={ctx}\n'
    '本文={content}\n'
    'JSONのみ：{{"status":"PASS|WARN|BLOCK","checks":{{"timeline":"PASS|WARN|BLOCK","character":"PASS|WARN|BLOCK","world":"PASS|WARN|BLOCK","plot":"PASS|WARN|BLOCK"}},"issues":[]}}'
)

_REWRITE_PROMPT = (
    'EP.{n}本文を修正し、完成本文のみ出力してください。'
    '変更対象はControllerが指摘した時系列・人物状態・世界観・プロットの矛盾です。\n'
    '監査={gate}\nEpisode Blueprint={plan}\n本文={content}'
)


def _parse_json(text: str) -> dict:
    text = (text or '').strip()
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _make_step(job: AutoWriteJob, db, phase: str, prompt: str, ctx: dict, max_tokens: int = 4096) -> dict:
    step_id = str(uuid.uuid4())
    job.pending_step_id = step_id
    job.current_write_context = json.dumps(ctx, ensure_ascii=False)
    db.commit()
    return {'done': False, 'step_id': step_id, 'phase': phase, 'prompt': prompt, 'max_tokens': max_tokens}


async def get_next_step(db, job: AutoWriteJob) -> dict:
    """Return the next LLM step for this job, or {'done': True} when complete."""
    db.refresh(job)
    if job.status == 'stopping':
        job.status = 'stopped'
        job.last_message = '停止しました'
        db.commit()
        return {'done': True, 'status': 'stopped'}

    project_id = job.project_id
    premise = job.premise or ''

    if job.status == 'queued':
        job.status = 'running'
        db.commit()

    # ── Phase 1: Series plan ──────────────────────────────────────────────────
    series = db.scalar(select(SeriesPlan).where(SeriesPlan.project_id == project_id))
    if not series or not series.content:
        project = db.get(Project, project_id)
        state = await build(db, project_id, None, 8)
        prompt = _SERIES_PROMPT.format(
            name=project.name, genre=project.genre, rules=project.rules,
            premise=premise, state=json.dumps(state, ensure_ascii=False),
        )
        job.last_message = 'Series Planner: EP.1〜500 全体構成を計画中'
        return _make_step(job, db, 'series_plan', prompt,
                          {'phase': 'series_plan', 'project_id': project_id})

    # ── Phase 2: Arc plans (5 arcs) ───────────────────────────────────────────
    arcs = db.scalars(select(ArcPlan).where(ArcPlan.project_id == project_id)).all()
    arcs_by_num = {a.arc_number: a for a in arcs if a.content}
    for arc_num in range(1, 6):
        if arc_num not in arcs_by_num:
            series_data = json.loads(series.content)
            arc_data = next(
                (a for a in series_data.get('arcs', []) if a.get('arc_number') == arc_num),
                {'arc_number': arc_num,
                 'start_episode': (arc_num - 1) * 100 + 1,
                 'end_episode': arc_num * 100},
            )
            state = await build(db, project_id, None, 8)
            prompt = _ARC_PROMPT.format(
                series=json.dumps(series_data, ensure_ascii=False),
                arc=json.dumps(arc_data, ensure_ascii=False),
                state=json.dumps(state, ensure_ascii=False),
                arc_number=arc_num,
            )
            job.last_message = f'Arc Planner: Arc {arc_num}/5 を計画中'
            return _make_step(job, db, 'arc_plan', prompt,
                              {'phase': 'arc_plan', 'arc_number': arc_num, 'series_id': series.id})

    # ── Phase 3: Mini arc plans (10 per arc = 50 total) ───────────────────────
    mini_arcs = db.scalars(select(MiniArcPlan).where(MiniArcPlan.project_id == project_id)).all()
    mini_by_key = {(m.arc_plan_id, m.mini_arc_number): m for m in mini_arcs if m.content}
    for arc in sorted(arcs_by_num.values(), key=lambda a: a.arc_number):
        arc_data = json.loads(arc.content)
        for mini_num in range(1, 11):
            if (arc.id, mini_num) not in mini_by_key:
                mini_data = next(
                    (m for m in arc_data.get('mini_arcs', []) if m.get('mini_arc_number') == mini_num),
                    {'mini_arc_number': mini_num,
                     'start_episode': (arc.arc_number - 1) * 100 + (mini_num - 1) * 10 + 1,
                     'end_episode': (arc.arc_number - 1) * 100 + mini_num * 10},
                )
                series_data = json.loads(series.content)
                state = await build(db, project_id, None, 8)
                prompt = _MINI_PROMPT.format(
                    series=json.dumps(series_data, ensure_ascii=False),
                    arc=json.dumps(arc_data, ensure_ascii=False),
                    mini=json.dumps(mini_data, ensure_ascii=False),
                    state=json.dumps(state, ensure_ascii=False),
                    number=mini_num,
                )
                job.last_message = f'Mini Arc Planner: Arc {arc.arc_number} Mini {mini_num}/10 を計画中'
                return _make_step(job, db, 'mini_arc_plan', prompt, {
                    'phase': 'mini_arc_plan',
                    'arc_id': arc.id,
                    'mini_arc_number': mini_num,
                    'mini_data': mini_data,
                })

    # ── Phase 4: Episode plans ────────────────────────────────────────────────
    ep_plans = db.scalars(
        select(EpisodePlan).where(
            EpisodePlan.project_id == project_id,
            EpisodePlan.episode_number >= job.start_episode,
            EpisodePlan.episode_number <= job.end_episode,
        )
    ).all()
    planned_ep_nums = {e.episode_number for e in ep_plans if e.content and e.title}
    for ep_num in range(job.start_episode, job.end_episode + 1):
        if ep_num not in planned_ep_nums:
            arc_num = (ep_num - 1) // 100 + 1
            mini_num = ((ep_num - 1) % 100) // 10 + 1
            arc = arcs_by_num.get(arc_num)
            if not arc:
                continue
            mini = mini_by_key.get((arc.id, mini_num))
            if not mini:
                continue
            series_data = json.loads(series.content)
            arc_data = json.loads(arc.content)
            mini_data = json.loads(mini.content)
            ep_data = next(
                (e for e in mini_data.get('episodes', []) if e.get('episode_number') == ep_num),
                {'episode_number': ep_num},
            )
            state = await build(db, project_id, None, 8)
            prompt = _EPISODE_PROMPT.format(
                series=json.dumps(series_data, ensure_ascii=False),
                arc=json.dumps(arc_data, ensure_ascii=False),
                mini=json.dumps(mini_data, ensure_ascii=False),
                episode=json.dumps(ep_data, ensure_ascii=False),
                state=json.dumps(state, ensure_ascii=False),
                number=ep_num,
            )
            mini_obj = next(
                (m for m in mini_arcs if m.arc_plan_id == arc.id and m.mini_arc_number == mini_num),
                None,
            )
            job.last_message = f'Episode Planner: EP.{ep_num} を計画中'
            return _make_step(job, db, 'episode_plan', prompt, {
                'phase': 'episode_plan',
                'ep_num': ep_num,
                'mini_arc_plan_id': mini_obj.id if mini_obj else None,
            })

    # ── Phase 5: Episode writing ──────────────────────────────────────────────
    # Resume in-progress write sub-phase if any
    write_ctx = {}
    if job.current_write_context:
        try:
            parsed = json.loads(job.current_write_context)
            if parsed.get('sub_phase') in ('write_gate', 'write_rewrite'):
                write_ctx = parsed
        except Exception:
            pass

    if write_ctx:
        return _resume_write(job, db, write_ctx)

    # Find next episode to write, starting from current_episode
    ep_plans_by_num = {e.episode_number: e for e in ep_plans if e.content and e.title}
    ep_num = job.current_episode

    while ep_num <= job.end_episode:
        db.refresh(job)
        if job.status == 'stopping':
            job.status = 'stopped'
            job.last_message = '停止しました'
            db.commit()
            return {'done': True, 'status': 'stopped'}

        existing = db.scalar(
            select(Episode).where(
                Episode.project_id == project_id,
                Episode.number == ep_num,
            )
        )
        if existing and existing.content.strip() and not job.overwrite:
            job.current_episode = ep_num + 1
            db.commit()
            ep_num += 1
            continue

        ep_plan_obj = ep_plans_by_num.get(ep_num)
        if not ep_plan_obj:
            ep_num += 1
            continue

        arc_num = (ep_num - 1) // 100 + 1
        mini_num = ((ep_num - 1) % 100) // 10 + 1
        arc = arcs_by_num.get(arc_num)
        if not arc:
            ep_num += 1
            continue
        mini = mini_by_key.get((arc.id, mini_num))
        if not mini:
            ep_num += 1
            continue

        project = db.get(Project, project_id)
        ctx = await build(db, project_id, existing, 8)
        series_data = json.loads(series.content)
        arc_data = json.loads(arc.content)
        mini_data = json.loads(mini.content)
        plan_data = json.loads(ep_plan_obj.content)

        write_ctx = {
            'sub_phase': 'write_generate',
            'episode_number': ep_num,
            'series': series_data,
            'arc': arc_data,
            'mini': mini_data,
            'plan': plan_data,
            'ctx': ctx,
            'rules': project.rules or '',
        }
        prompt = _WRITER_PROMPT.format(
            n=ep_num,
            series=json.dumps(series_data, ensure_ascii=False),
            arc=json.dumps(arc_data, ensure_ascii=False),
            mini=json.dumps(mini_data, ensure_ascii=False),
            plan=json.dumps(plan_data, ensure_ascii=False),
            ctx=json.dumps(ctx, ensure_ascii=False),
            rules=project.rules or '',
        )
        job.last_message = f'EP.{ep_num}: Writer 執筆中'
        return _make_step(job, db, 'write_generate', prompt, write_ctx, max_tokens=8192)

    job.status = 'completed'
    job.last_message = '全エピソード生成完了'
    db.commit()
    return {'done': True, 'status': 'completed'}


def _resume_write(job: AutoWriteJob, db, write_ctx: dict) -> dict:
    """Return the prompt for an in-progress episode gate or rewrite step."""
    sub = write_ctx['sub_phase']
    ep_num = write_ctx['episode_number']

    if sub == 'write_gate':
        prompt = _GATE_PROMPT.format(
            series=json.dumps(write_ctx['series'], ensure_ascii=False),
            arc=json.dumps(write_ctx['arc'], ensure_ascii=False),
            mini=json.dumps(write_ctx['mini'], ensure_ascii=False),
            plan=json.dumps(write_ctx['plan'], ensure_ascii=False),
            ctx=json.dumps(write_ctx['ctx'], ensure_ascii=False),
            content=write_ctx.get('content', ''),
        )
        job.last_message = f'EP.{ep_num}: Controller 最終監査'
        return _make_step(job, db, 'write_gate', prompt, write_ctx)

    if sub == 'write_rewrite':
        prompt = _REWRITE_PROMPT.format(
            n=ep_num,
            gate=json.dumps(write_ctx.get('gate', {}), ensure_ascii=False),
            plan=json.dumps(write_ctx['plan'], ensure_ascii=False),
            content=write_ctx.get('content', ''),
        )
        job.last_message = f'EP.{ep_num}: Writer 再執筆中'
        return _make_step(job, db, 'write_rewrite', prompt, write_ctx, max_tokens=8192)

    return {'done': True, 'status': 'error', 'message': f'unknown sub_phase: {sub}'}


async def apply_step_result(db, job: AutoWriteJob, step_id: str, result: str) -> dict:
    """Process an LLM result and advance job state. Returns {'saved': True/False, ...}."""
    if job.pending_step_id and job.pending_step_id != step_id:
        raise ValueError(f'step_id mismatch: expected {job.pending_step_id}, got {step_id}')

    ctx: dict = {}
    if job.current_write_context:
        try:
            ctx = json.loads(job.current_write_context)
        except Exception:
            pass

    phase = ctx.get('sub_phase') or ctx.get('phase', 'unknown')

    # ── series_plan ───────────────────────────────────────────────────────────
    if phase == 'series_plan':
        data = _parse_json(result)
        if not data:
            job.last_message = 'Series Planner: JSON parse failed'
            job.pending_step_id = None
            job.current_write_context = ''
            db.commit()
            return {'saved': False, 'error': 'json_parse_failed'}
        series = db.scalar(select(SeriesPlan).where(SeriesPlan.project_id == job.project_id))
        if not series:
            series = SeriesPlan(
                project_id=job.project_id,
                total_episodes=job.end_episode,
                title=data.get('title', ''),
                premise=data.get('premise', job.premise or ''),
                content=json.dumps(data, ensure_ascii=False),
                status='approved', model='anna',
            )
            db.add(series)
            db.commit()
            db.refresh(series)
            for a in data.get('arcs', []):
                if not db.scalar(select(ArcPlan).where(
                    ArcPlan.project_id == job.project_id,
                    ArcPlan.arc_number == a.get('arc_number', 1),
                )):
                    db.add(ArcPlan(
                        series_plan_id=series.id, project_id=job.project_id,
                        arc_number=a.get('arc_number', 1),
                        start_episode=a.get('start_episode', 1),
                        end_episode=a.get('end_episode', 100),
                        title=a.get('title', ''),
                        content=json.dumps(a, ensure_ascii=False),
                        status='planned', model='anna',
                    ))
            db.commit()
        else:
            series.content = json.dumps(data, ensure_ascii=False)
            series.status = 'approved'
            series.model = 'anna'
            db.commit()
        job.pending_step_id = None
        job.current_write_context = ''
        job.last_message = 'Series Planner: 完了'
        db.commit()
        return {'saved': True}

    # ── arc_plan ──────────────────────────────────────────────────────────────
    if phase == 'arc_plan':
        arc_num = ctx.get('arc_number', 1)
        series_id = ctx.get('series_id')
        data = _parse_json(result)
        arc = db.scalar(select(ArcPlan).where(
            ArcPlan.project_id == job.project_id, ArcPlan.arc_number == arc_num,
        ))
        if arc:
            arc.content = json.dumps(data if data else {}, ensure_ascii=False)
            arc.model = 'anna'
        else:
            arc = ArcPlan(
                series_plan_id=series_id, project_id=job.project_id,
                arc_number=arc_num,
                start_episode=(arc_num - 1) * 100 + 1,
                end_episode=arc_num * 100,
                title=(data or {}).get('title', ''),
                content=json.dumps(data if data else {}, ensure_ascii=False),
                status='planned', model='anna',
            )
            db.add(arc)
        db.commit()
        db.refresh(arc)
        for m in (data or {}).get('mini_arcs', []):
            mini_num = m.get('mini_arc_number', 1)
            if not db.scalar(select(MiniArcPlan).where(
                MiniArcPlan.arc_plan_id == arc.id,
                MiniArcPlan.mini_arc_number == mini_num,
            )):
                db.add(MiniArcPlan(
                    arc_plan_id=arc.id, project_id=job.project_id,
                    mini_arc_number=mini_num,
                    start_episode=m.get('start_episode', (arc_num - 1) * 100 + (mini_num - 1) * 10 + 1),
                    end_episode=m.get('end_episode', (arc_num - 1) * 100 + mini_num * 10),
                    title=m.get('title', ''),
                    content=json.dumps(m, ensure_ascii=False),
                    status='planned', model='anna',
                ))
        db.commit()
        job.pending_step_id = None
        job.current_write_context = ''
        job.last_message = f'Arc Planner: Arc {arc_num} 完了'
        db.commit()
        return {'saved': True}

    # ── mini_arc_plan ─────────────────────────────────────────────────────────
    if phase == 'mini_arc_plan':
        arc_id = ctx.get('arc_id')
        mini_num = ctx.get('mini_arc_number', 1)
        data = _parse_json(result)
        mini = db.scalar(select(MiniArcPlan).where(
            MiniArcPlan.arc_plan_id == arc_id,
            MiniArcPlan.mini_arc_number == mini_num,
        ))
        if mini:
            mini.content = json.dumps(data if data else {}, ensure_ascii=False)
            mini.model = 'anna'
        else:
            mini_data = ctx.get('mini_data', {})
            mini = MiniArcPlan(
                arc_plan_id=arc_id, project_id=job.project_id,
                mini_arc_number=mini_num,
                start_episode=mini_data.get('start_episode', 1),
                end_episode=mini_data.get('end_episode', 10),
                title=mini_data.get('title', ''),
                content=json.dumps(data if data else {}, ensure_ascii=False),
                status='planned', model='anna',
            )
            db.add(mini)
        db.commit()
        db.refresh(mini)
        for e in (data or {}).get('episodes', []):
            ep_num = e.get('episode_number', 1)
            if not db.scalar(select(EpisodePlan).where(
                EpisodePlan.mini_arc_plan_id == mini.id,
                EpisodePlan.episode_number == ep_num,
            )):
                db.add(EpisodePlan(
                    mini_arc_plan_id=mini.id, project_id=job.project_id,
                    episode_number=ep_num, title=e.get('title', ''),
                    content=json.dumps(e, ensure_ascii=False),
                    status='planned', model='anna',
                ))
        db.commit()
        job.pending_step_id = None
        job.current_write_context = ''
        job.last_message = 'Mini Arc Planner: 完了'
        db.commit()
        return {'saved': True}

    # ── episode_plan ──────────────────────────────────────────────────────────
    if phase == 'episode_plan':
        ep_num = ctx.get('ep_num', 1)
        mini_arc_plan_id = ctx.get('mini_arc_plan_id')
        data = _parse_json(result)
        ep_plan = db.scalar(select(EpisodePlan).where(
            EpisodePlan.project_id == job.project_id,
            EpisodePlan.episode_number == ep_num,
        ))
        content_json = json.dumps(data if data else {'episode_number': ep_num}, ensure_ascii=False)
        if ep_plan:
            ep_plan.content = content_json
            ep_plan.title = (data or {}).get('title', '')
            ep_plan.status = 'approved'
            ep_plan.model = 'anna'
        else:
            ep_plan = EpisodePlan(
                mini_arc_plan_id=mini_arc_plan_id, project_id=job.project_id,
                episode_number=ep_num, title=(data or {}).get('title', ''),
                content=content_json, status='approved', model='anna',
            )
            db.add(ep_plan)
        db.commit()
        job.pending_step_id = None
        job.current_write_context = ''
        job.last_message = f'Episode Planner: EP.{ep_num} 完了'
        db.commit()
        return {'saved': True}

    # ── write_generate ────────────────────────────────────────────────────────
    if phase == 'write_generate':
        ctx['content'] = result
        ctx['sub_phase'] = 'write_gate'
        job.current_write_context = json.dumps(ctx, ensure_ascii=False)
        job.pending_step_id = None
        job.last_message = f'EP.{ctx["episode_number"]}: 本文生成完了 → Controller監査へ'
        db.commit()
        return {'saved': True, 'next_phase': 'write_gate'}

    # ── write_gate ────────────────────────────────────────────────────────────
    if phase == 'write_gate':
        gate = _parse_json(result)
        ep_num = ctx['episode_number']
        content = ctx.get('content', '')
        if gate.get('status') == 'BLOCK':
            ctx['gate'] = gate
            ctx['sub_phase'] = 'write_rewrite'
            job.current_write_context = json.dumps(ctx, ensure_ascii=False)
            job.pending_step_id = None
            job.last_message = f'EP.{ep_num}: Controller BLOCK → 再執筆'
            db.commit()
            return {'saved': True, 'next_phase': 'write_rewrite'}
        await _save_episode(db, job, ctx, content, gate)
        return {'saved': True, 'next_phase': 'done'}

    # ── write_rewrite ─────────────────────────────────────────────────────────
    if phase == 'write_rewrite':
        gate = ctx.get('gate', {})
        await _save_episode(db, job, ctx, result, gate)
        return {'saved': True, 'next_phase': 'done'}

    return {'saved': False, 'error': f'unknown phase: {phase}'}


def _ep_chunks(ep: Episode) -> list[dict]:
    s = ep.content or ''
    out = []
    start = 0
    i = 0
    while start < len(s):
        out.append({
            'id': ep.id * 100000 + i, 'project_id': ep.project_id,
            'episode_id': ep.id, 'title': ep.title,
            'source_type': 'episode', 'text': s[start:start + 1400],
        })
        i += 1
        start += 1200
    return out


async def _post_char_states(project_id: int, ep_id: int) -> None:
    db2 = SessionLocal()
    try:
        ep = db2.get(Episode, ep_id)
        if ep:
            await update_character_states(db2, project_id, ep)
    except Exception:
        pass
    finally:
        db2.close()


async def _post_foreshadow(project_id: int, ep_id: int) -> None:
    db2 = SessionLocal()
    try:
        ep = db2.get(Episode, ep_id)
        if ep:
            await update_foreshadowing_statuses(db2, project_id, ep)
    except Exception:
        pass
    finally:
        db2.close()


async def _save_episode(db, job: AutoWriteJob, ctx: dict, content: str, gate: dict) -> None:
    """Persist episode content and run post-processing."""
    ep_num = ctx['episode_number']
    project_id = job.project_id
    plan = ctx.get('plan', {})

    existing = db.scalar(
        select(Episode).where(Episode.project_id == project_id, Episode.number == ep_num)
    )
    if existing:
        existing.title = plan.get('title') or existing.title
        existing.summary = plan.get('summary', '')
        existing.content = content
        ep = existing
    else:
        ep = Episode(
            project_id=project_id, number=ep_num,
            title=plan.get('title') or f'第{ep_num}話',
            summary=plan.get('summary', ''), content=content,
        )
        db.add(ep)

    ep_plan = db.scalar(
        select(EpisodePlan).where(
            EpisodePlan.project_id == project_id, EpisodePlan.episode_number == ep_num,
        )
    )
    if ep_plan:
        ep_plan.status = 'completed'

    db.commit()
    db.refresh(ep)
    ep_id = ep.id
    ep_chunks_data = _ep_chunks(ep)

    update_plot_statuses(db, project_id, ep_num)

    await asyncio.gather(
        _post_char_states(project_id, ep_id),
        _post_foreshadow(project_id, ep_id),
        index(ep_chunks_data),
        return_exceptions=True,
    )

    if ep_num % 5 == 0:
        try:
            await check_continuity(db, project_id, ep_id)
        except Exception:
            pass

    job.current_episode = ep_num + 1
    job.pending_step_id = None
    job.current_write_context = ''
    job.last_message = f'EP.{ep_num}: 完了 gate={gate.get("status", "PASS")}'
    db.commit()
