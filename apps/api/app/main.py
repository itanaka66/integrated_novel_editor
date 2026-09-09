from fastapi import FastAPI,Depends,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Base,engine,get_db,SessionLocal
from .config import settings
from .models import *
from .schemas import *
from .ollama import generate
from .rag import index,search
from .context import build
from .continuity import update_character_states, check_continuity
from .auto_writer import run_job, running
from .planner.planner_service import PlannerService
from .models import SeriesPlan, ArcPlan, MiniArcPlan, EpisodePlan
app=FastAPI(title='AI Novel Studio API',version='0.9.0');app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(',')],allow_methods=['*'],allow_headers=['*'])
def chunks(e):
 s=e.content or ''; out=[]; start=0;i=0
 while start<len(s):
  t=s[start:start+1400];out.append({'id':e.id*100000+i,'project_id':e.project_id,'episode_id':e.id,'title':e.title,'source_type':'episode','text':t});i+=1;start+=1200
 return out
@app.on_event('startup')
def init():
 Base.metadata.create_all(bind=engine)
 with SessionLocal() as d:
  if not d.scalar(select(Project).limit(1)):
   p=Project(name='恐竜時代文明開拓記 DEMO',description='現代知識で恐竜時代に文明を築く',genre='SF / 文明開拓',rules='魔法なし。現代知識は実験と失敗を経て再現する。');d.add(p);d.flush()
   d.add_all([Character(project_id=p.id,name='田中',role='主人公',personality='慎重だが好奇心旺盛',speech_style='現代日本語',goal='文明を安全に発展させる'),Character(project_id=p.id,name='リナ',role='仲間',personality='行動派',speech_style='短く率直',goal='集落を守る')])
   d.add_all([WorldEntity(project_id=p.id,name='最初の集落',entity_type='location',description='森の近くの集落',location='大河東岸'),WorldEntity(project_id=p.id,name='鉄器',entity_type='technology',description='まだ存在しない重要技術',rules='鉱石→炉→燃料の順に確立')])
   d.add(Plot(project_id=p.id,title='文明開拓編',plot_type='main_arc',status='active',start_episode=1,end_episode=100,objective='安全な集落を作る',conflict='自然災害と恐竜'))
   d.add(Foreshadowing(project_id=p.id,title='地下の鉱脈',description='集落近くの岩場に金属資源がある',setup_episode=3))
   d.add_all([Episode(project_id=p.id,number=1,title='転移',summary='少年が恐竜時代で目を覚ます',content='少年は見知らぬ森で目を覚ました。遠くから巨大な咆哮が聞こえる。'),Episode(project_id=p.id,number=2,title='最初の火',summary='火を安定利用する',content='乾いた枝を集め、火を起こす方法を試した。何度も失敗した。'),Episode(project_id=p.id,number=3,title='最初の仲間',summary='集落と出会う',content='森を抜けると小さな集落が見えた。')]);d.commit()
@app.get('/api/v1/health')
def health():return {'status':'ok','version':'0.9.0','features':['continuity-checker','character-state-auto-update','story-digital-twin','auto-write-1-500','dual-ollama-controller','hierarchical-series-planner','arc-planner','mini-arc-planner','episode-planner']}

@app.post('/api/v1/planner/series', response_model=PlanOut)
async def planner_series(x:PlanGenerate, db:Session=Depends(get_db)):
    return await PlannerService().ensure_series(db, x.project_id, x.premise)

@app.post('/api/v1/planner/arc', response_model=PlanOut)
async def planner_arc(x:PlanGenerate, db:Session=Depends(get_db)):
    if not x.arc_number or not 1 <= x.arc_number <= 5: raise HTTPException(400,'arc_number must be 1..5')
    return await PlannerService().ensure_arc(db, x.project_id, x.arc_number, x.premise)

@app.post('/api/v1/planner/mini-arc', response_model=PlanOut)
async def planner_mini(x:PlanGenerate, db:Session=Depends(get_db)):
    if not x.arc_number or not x.mini_arc_number or not 1 <= x.arc_number <= 5 or not 1 <= x.mini_arc_number <= 10: raise HTTPException(400,'arc_number 1..5 and mini_arc_number 1..10 required')
    return await PlannerService().ensure_mini(db, x.project_id, x.arc_number, x.mini_arc_number, x.premise)

@app.post('/api/v1/planner/episode', response_model=PlanOut)
async def planner_episode(x:PlanGenerate, db:Session=Depends(get_db)):
    if not x.episode_number or not 1 <= x.episode_number <= 500: raise HTTPException(400,'episode_number must be 1..500')
    return await PlannerService().ensure_episode(db, x.project_id, x.episode_number, x.premise)

@app.get('/api/v1/projects/{pid}/planner')
def planner_tree(pid:int, db:Session=Depends(get_db)):
    series=db.scalar(select(SeriesPlan).where(SeriesPlan.project_id==pid))
    if not series: return {'series':None,'arcs':[]}
    arcs=list(db.scalars(select(ArcPlan).where(ArcPlan.project_id==pid).order_by(ArcPlan.arc_number)).all())
    out=[]
    for a in arcs:
        minis=list(db.scalars(select(MiniArcPlan).where(MiniArcPlan.arc_plan_id==a.id).order_by(MiniArcPlan.mini_arc_number)).all())
        out.append({'arc':a,'mini_arcs':minis})
    return {'series':series,'arcs':out}

@app.post('/api/v1/auto-write/start', response_model=AutoWriteJobOut)
async def auto_write_start(x:AutoWriteStart, db:Session=Depends(get_db)):
    if x.start_episode<1 or x.end_episode>x.start_episode+999 or x.start_episode>x.end_episode: raise HTTPException(400,'episode range must be valid and max 1000 episodes')
    j=AutoWriteJob(project_id=x.project_id,start_episode=x.start_episode,end_episode=x.end_episode,current_episode=x.start_episode,status='queued',writer_model=x.writer_model or settings.ollama_model,controller_model=x.controller_model or settings.controller_ollama_model,last_message='queued')
    db.add(j);db.commit();db.refresh(j)
    import asyncio
    running[j.id]=asyncio.create_task(run_job(j.id,x.premise,x.overwrite))
    return j

def _job_progress(j, db):
    total=max(1, j.end_episode-j.start_episode+1)
    completed=max(0, min(total, j.current_episode-j.start_episode))
    if j.status=='completed': completed=total
    # current_episode is the episode being processed, so completed is the number fully finished.
    percent=round(completed/total*100, 1)
    msg=(j.last_message or '').lower()
    phase='queued'
    if j.status in ('completed','error','stopped'): phase=j.status
    elif 'series planner' in msg: phase='series_planner'
    elif '階層planner' in msg: phase='arc_planner'
    elif 'preflight' in msg: phase='preflight'
    elif 'writer' in msg and '再執筆' not in msg: phase='writer'
    elif '再執筆' in msg: phase='revision'
    elif 'final gate' in msg: phase='quality_gate'
    elif 'completed' in msg: phase='episode_complete'
    elif j.status=='running': phase='episode_planner'
    from .models import SeriesPlan, ArcPlan, MiniArcPlan, EpisodePlan, Episode
    series_planned=db.scalar(select(SeriesPlan).where(SeriesPlan.project_id==j.project_id)) is not None
    arcs=db.scalar(select(ArcPlan).where(ArcPlan.project_id==j.project_id).order_by(ArcPlan.id.desc()))
    arc_count=len(db.scalars(select(ArcPlan).where(ArcPlan.project_id==j.project_id)).all())
    mini_count=len(db.scalars(select(MiniArcPlan).where(MiniArcPlan.project_id==j.project_id)).all())
    epplan_count=len(db.scalars(select(EpisodePlan).where(EpisodePlan.project_id==j.project_id)).all())
    written=len(db.scalars(select(Episode).where(Episode.project_id==j.project_id, Episode.number>=j.start_episode, Episode.number<=j.end_episode, Episode.content!='')).all())
    return {**j.__dict__, 'progress_percent':percent, 'completed_episodes':completed, 'total_episodes':total,
            'current_phase':phase, 'series_planned':series_planned, 'arcs_planned':arc_count,
            'mini_arcs_planned':mini_count, 'episodes_planned':epplan_count, 'episodes_written':written}

@app.get('/api/v1/auto-write/{job_id}', response_model=AutoWriteJobOut)
def auto_write_status(job_id:int,db:Session=Depends(get_db)):
    j=db.get(AutoWriteJob,job_id)
    if not j: raise HTTPException(404,'Auto-write job not found')
    return _job_progress(j,db)

@app.post('/api/v1/auto-write/{job_id}/stop', response_model=AutoWriteJobOut)
def auto_write_stop(job_id:int,db:Session=Depends(get_db)):
    j=db.get(AutoWriteJob,job_id)
    if not j: raise HTTPException(404,'Auto-write job not found')
    if j.status in ('queued','running'): j.status='stopping';j.last_message='停止要求を受け付けました';db.commit();db.refresh(j)
    return j

def crud_list(db,model,pid):return list(db.scalars(select(model).where(model.project_id==pid).order_by(model.id)).all())
@app.get('/api/v1/projects',response_model=list[ProjectOut])
def projects(db:Session=Depends(get_db)):return list(db.scalars(select(Project).order_by(Project.id.desc())).all())
@app.get('/api/v1/projects/{pid}',response_model=ProjectOut)
def project(pid:int,db:Session=Depends(get_db)):
 p=db.get(Project,pid)
 if not p:raise HTTPException(404,'Project not found')
 return p
@app.post('/api/v1/projects',response_model=ProjectOut)
def project_add(x:ProjectCreate,db:Session=Depends(get_db)):p=Project(**x.model_dump());db.add(p);db.commit();db.refresh(p);return p
@app.get('/api/v1/projects/{pid}/episodes',response_model=list[EpisodeOut])
def episodes(pid:int,db:Session=Depends(get_db)):return list(db.scalars(select(Episode).where(Episode.project_id==pid).order_by(Episode.number)).all())
@app.post('/api/v1/projects/{pid}/episodes',response_model=EpisodeOut)
def episode_add(pid:int,x:EpisodeCreate,db:Session=Depends(get_db)):e=Episode(project_id=pid,**x.model_dump());db.add(e);db.commit();db.refresh(e);return e
@app.put('/api/v1/episodes/{eid}',response_model=EpisodeOut)
async def episode_put(eid:int,x:EpisodeUpdate,db:Session=Depends(get_db)):
 e=db.get(Episode,eid)
 if not e:raise HTTPException(404,'Episode not found')
 for k,v in x.model_dump(exclude_unset=True).items():setattr(e,k,v)
 db.commit();db.refresh(e)
 try:await index(chunks(e))
 except:pass
 try: await update_character_states(db,e)
 except Exception: pass
 return e
@app.get('/api/v1/projects/{pid}/characters',response_model=list[CharacterOut])
def chars(pid:int,db:Session=Depends(get_db)):return crud_list(db,Character,pid)
@app.post('/api/v1/projects/{pid}/characters',response_model=CharacterOut)
def char_add(pid:int,x:CharacterCreate,db:Session=Depends(get_db)):o=Character(project_id=pid,**x.model_dump());db.add(o);db.commit();db.refresh(o);return o
@app.get('/api/v1/projects/{pid}/world',response_model=list[WorldOut])
def worlds(pid:int,db:Session=Depends(get_db)):return crud_list(db,WorldEntity,pid)
@app.post('/api/v1/projects/{pid}/world',response_model=WorldOut)
def world_add(pid:int,x:WorldCreate,db:Session=Depends(get_db)):o=WorldEntity(project_id=pid,**x.model_dump());db.add(o);db.commit();db.refresh(o);return o
@app.get('/api/v1/projects/{pid}/plots',response_model=list[PlotOut])
def plots(pid:int,db:Session=Depends(get_db)):return crud_list(db,Plot,pid)
@app.post('/api/v1/projects/{pid}/plots',response_model=PlotOut)
def plot_add(pid:int,x:PlotCreate,db:Session=Depends(get_db)):o=Plot(project_id=pid,**x.model_dump());db.add(o);db.commit();db.refresh(o);return o
@app.get('/api/v1/projects/{pid}/foreshadowings',response_model=list[ForeshadowOut])
def fs(pid:int,db:Session=Depends(get_db)):return crud_list(db,Foreshadowing,pid)
@app.post('/api/v1/projects/{pid}/foreshadowings',response_model=ForeshadowOut)
def fs_add(pid:int,x:ForeshadowCreate,db:Session=Depends(get_db)):o=Foreshadowing(project_id=pid,**x.model_dump());db.add(o);db.commit();db.refresh(o);return o
@app.post('/api/v1/rag/index')
async def rag_index(x:RagIndex,db:Session=Depends(get_db)):
 es=db.scalars(select(Episode).where(Episode.project_id==x.project_id)).all(); cs=[c for e in es for c in chunks(e)]
 try:return {'indexed':await index(cs)}
 except Exception as e:raise HTTPException(503,str(e))
@app.post('/api/v1/rag/search')
async def rag_search(x:RagSearch,db:Session=Depends(get_db)):
 try:return {'source':'qdrant','results':await search(x.project_id,x.query,x.limit)}
 except:
  rows=db.scalars(select(Episode).where(Episode.project_id==x.project_id,Episode.content.ilike('%'+x.query+'%')).limit(x.limit)).all();return {'source':'postgresql','results':[{'episode_id':e.id,'title':e.title,'text':e.content} for e in rows]}
@app.post('/api/v1/ai/generate')
async def ai(x:AIGenerate,db:Session=Depends(get_db)):
 e=db.get(Episode,x.episode_id) if x.episode_id else None;c=await build(db,x.project_id,e,x.rag_limit)
 task={'continue':'本文の続きを書く','summary':'本文を要約する','plot':'次の展開を提案する','proofread':'設定・表現・時系列を校正する'}.get(x.mode,'依頼を実行する')
 prompt=f'''あなたは長編小説の編集長AIです。作品の正本設定を最優先してください。\n作業:{task}\n\nContext:\n{__import__("json").dumps(c,ensure_ascii=False,indent=2)}\n\n指示:{x.instruction}\n日本語で出力してください。'''
 try:t,m=await generate(prompt)
 except Exception as ex:raise HTTPException(503,f'Ollama error: {ex}')
 return {'text':t,'model':m,'context':{'characters':len(c['characters']),'world':len(c['world']),'plots':len(c['plots']),'foreshadowings':len(c['foreshadowings']),'rag':len(c['rag'])}}


@app.get('/api/v1/projects/{pid}/characters/{cid}/states',response_model=list[CharacterStateOut])
def character_states(pid:int,cid:int,db:Session=Depends(get_db)):
    return list(db.scalars(select(CharacterState).where(CharacterState.project_id==pid,CharacterState.character_id==cid).order_by(CharacterState.episode_number.desc())).all())

@app.get('/api/v1/projects/{pid}/continuity/issues',response_model=list[ContinuityIssueOut])
def continuity_issues(pid:int,db:Session=Depends(get_db)):
    return list(db.scalars(select(ContinuityIssue).where(ContinuityIssue.project_id==pid).order_by(ContinuityIssue.id.desc()).limit(100)).all())

@app.post('/api/v1/continuity/check')
async def continuity_check(x:ContinuityCheck,db:Session=Depends(get_db)):
    try:
        issues=await check_continuity(db,x.project_id,x.episode_id)
        return {'count':len(issues),'issues':[ContinuityIssueOut.model_validate(i).model_dump() for i in issues]}
    except Exception as ex: raise HTTPException(503,str(ex))

@app.post('/api/v1/episodes/{eid}/character-states')
async def character_state_update(eid:int,db:Session=Depends(get_db)):
    e=db.get(Episode,eid)
    if not e: raise HTTPException(404,'Episode not found')
    try:
        states=await update_character_states(db,e.project_id,e)
        return {'count':len(states),'states':[CharacterStateOut.model_validate(x).model_dump() for x in states]}
    except Exception as ex: raise HTTPException(503,str(ex))

@app.get('/api/v1/projects/{pid}/graphs/characters', response_model=GraphOut)
def character_graph(pid:int,db:Session=Depends(get_db)):
    chars=list(db.scalars(select(Character).where(Character.project_id==pid).order_by(Character.id)).all())
    nodes=[GraphNode(id=c.id,label=c.name,node_type='character',meta={'role':c.role,'status':c.status}) for c in chars]
    edges=[]
    rels=list(db.scalars(select(CharacterRelation).where(CharacterRelation.project_id==pid)).all())
    for r in rels: edges.append(GraphEdge(source=r.from_character_id,target=r.to_character_id,label=r.relation_type,weight=r.strength,meta={'description':r.description}))
    # Fallback/augmentation: co-occurrence in episode text creates weak semantic links.
    eps=list(db.scalars(select(Episode).where(Episode.project_id==pid)).all())
    for i,a in enumerate(chars):
        for b in chars[i+1:]:
            count=sum(1 for e in eps if a.name in (e.content or '') and b.name in (e.content or ''))
            if count and not any((x.source==a.id and x.target==b.id) or (x.source==b.id and x.target==a.id) for x in edges):
                edges.append(GraphEdge(source=a.id,target=b.id,label='共演',weight=min(count,5),meta={'episodes':count}))
    return GraphOut(nodes=nodes,edges=edges)

@app.get('/api/v1/projects/{pid}/graphs/world', response_model=GraphOut)
def world_graph(pid:int,db:Session=Depends(get_db)):
    worlds=list(db.scalars(select(WorldEntity).where(WorldEntity.project_id==pid).order_by(WorldEntity.id)).all())
    nodes=[GraphNode(id=w.id,label=w.name,node_type='world',meta={'type':w.entity_type,'location':w.location,'era':w.era}) for w in worlds]
    edges=[]
    rels=list(db.scalars(select(WorldRelation).where(WorldRelation.project_id==pid)).all())
    for r in rels: edges.append(GraphEdge(source=r.from_world_id,target=r.to_world_id,label=r.relation_type,weight=r.strength,meta={'description':r.description}))
    eps=list(db.scalars(select(Episode).where(Episode.project_id==pid)).all())
    for i,a in enumerate(worlds):
        for b in worlds[i+1:]:
            count=sum(1 for e in eps if a.name in (e.content or '') and b.name in (e.content or ''))
            if count and not any((x.source==a.id and x.target==b.id) or (x.source==b.id and x.target==a.id) for x in edges):
                edges.append(GraphEdge(source=a.id,target=b.id,label='共起',weight=min(count,5),meta={'episodes':count}))
    return GraphOut(nodes=nodes,edges=edges)

@app.get('/api/v1/projects/{pid}/graphs/timeline', response_model=GraphOut)
def timeline_graph(pid:int,db:Session=Depends(get_db)):
    eps=list(db.scalars(select(Episode).where(Episode.project_id==pid).order_by(Episode.number)).all())
    events=list(db.scalars(select(TimelineEvent).where(TimelineEvent.project_id==pid).order_by(TimelineEvent.episode_number,TimelineEvent.id)).all())
    nodes=[]
    for e in eps:
        nodes.append(GraphNode(id=1000000+e.id,label=f'EP.{e.number} {e.title}',node_type='episode',meta={'episode':e.number,'summary':e.summary}))
    for t in events:
        nodes.append(GraphNode(id=2000000+t.id,label=t.title,node_type='event',meta={'episode':t.episode_number,'world_time':t.world_time,'description':t.description}))
    edges=[]
    for a,b in zip(eps,eps[1:]): edges.append(GraphEdge(source=1000000+a.id,target=1000000+b.id,label='次話',weight=1))
    for t in events: edges.append(GraphEdge(source=1000000+next((e.id for e in eps if e.number==t.episode_number),0),target=2000000+t.id,label=t.world_time or '出来事',weight=1))
    return GraphOut(nodes=nodes,edges=edges)


@app.get('/api/v1/projects/{pid}/story-twin', response_model=TwinOut)
def story_twin(pid:int,db:Session=Depends(get_db)):
    p=db.get(Project,pid)
    if not p: raise HTTPException(404,'Project not found')
    # Build the Digital Twin from the authoritative relational model plus derived graph views.
    eps=list(db.scalars(select(Episode).where(Episode.project_id==pid).order_by(Episode.number)).all())
    chars=list(db.scalars(select(Character).where(Character.project_id==pid)).all())
    worlds=list(db.scalars(select(WorldEntity).where(WorldEntity.project_id==pid)).all())
    plots=list(db.scalars(select(Plot).where(Plot.project_id==pid)).all())
    fs=list(db.scalars(select(Foreshadowing).where(Foreshadowing.project_id==pid)).all())
    states=list(db.scalars(select(CharacterState).where(CharacterState.project_id==pid).order_by(CharacterState.episode_number.desc(),CharacterState.id.desc()).limit(50)).all())
    issues=list(db.scalars(select(ContinuityIssue).where(ContinuityIssue.project_id==pid,ContinuityIssue.status=='open').all()))
    cg=character_graph(pid,db); wg=world_graph(pid,db); tg=timeline_graph(pid,db)
    completed=sum(1 for e in eps if (e.content or '').strip())
    open_fs=sum(1 for f in fs if f.status=='open')
    high=sum(1 for i in issues if i.severity=='high')
    # Coverage is a practical quality signal, not an AI confidence score.
    coverage=round((completed/len(eps))*100) if eps else 0
    health_score=max(0,min(100,round(100 - high*15 - max(0,len(issues)-high)*4 + min(20,coverage*0.2))))
    health_label='healthy' if health_score>=85 else ('attention' if health_score>=60 else 'risk')
    recent=[CharacterStateOut.model_validate(x).model_dump() for x in states]
    return TwinOut(
      project={'id':p.id,'name':p.name,'genre':p.genre,'description':p.description},
      metrics={'episodes':len(eps),'characters':len(chars),'world_entities':len(worlds),'plots':len(plots),'foreshadowings':len(fs),'states':len(states),'continuity_open':len(issues),'continuity_high':high,'graph_nodes':len(cg.nodes)+len(wg.nodes)+len(tg.nodes),'graph_edges':len(cg.edges)+len(wg.edges)+len(tg.edges)},
      health={'score':health_score,'label':health_label,'episode_coverage':coverage,'explanation':'作品の構造化データ・状態履歴・未解決矛盾から算出した運用指標です。'},
      characters=cg,world=wg,timeline=tg,recent_states=recent,
      continuity={'open':len(issues),'high':high,'medium':sum(1 for i in issues if i.severity=='medium'),'low':sum(1 for i in issues if i.severity=='low')},
      active_plots=[{'id':x.id,'title':x.title,'status':x.status,'start_episode':x.start_episode,'end_episode':x.end_episode} for x in plots if x.status in ('active','planned')],
      open_foreshadowings=[{'id':x.id,'title':x.title,'setup_episode':x.setup_episode,'payoff_episode':x.payoff_episode,'status':x.status} for x in fs if x.status=='open']
    )

@app.get('/api/v1/projects/{pid}/timeline',response_model=list[TimelineOut])
def timeline(pid:int,db:Session=Depends(get_db)): return list(db.scalars(select(TimelineEvent).where(TimelineEvent.project_id==pid).order_by(TimelineEvent.episode_number,TimelineEvent.id)).all())
@app.post('/api/v1/projects/{pid}/timeline',response_model=TimelineOut)
def timeline_add(pid:int,x:TimelineCreate,db:Session=Depends(get_db)):
    o=TimelineEvent(project_id=pid,**x.model_dump());db.add(o);db.commit();db.refresh(o);return o
