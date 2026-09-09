from pydantic import BaseModel,ConfigDict
class ProjectCreate(BaseModel): name:str; description:str=''; genre:str=''; rules:str=''; episode_goal:int=500
class ProjectOut(ProjectCreate): id:int; model_config=ConfigDict(from_attributes=True)
class ProjectUpdate(BaseModel): name:str|None=None; description:str|None=None; genre:str|None=None; rules:str|None=None; episode_goal:int|None=None
class EpisodeCreate(BaseModel): number:int; title:str; summary:str=''; content:str=''
class EpisodeOut(EpisodeCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class EpisodeUpdate(BaseModel): title:str|None=None; summary:str|None=None; content:str|None=None
class EpisodeSaveOut(EpisodeOut): warnings:list[str]=[]
class CharacterCreate(BaseModel): name:str; role:str=''; personality:str=''; speech_style:str=''; goal:str=''; status:str='alive'; description:str=''
class CharacterOut(CharacterCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class CharacterUpdate(BaseModel): name:str|None=None; role:str|None=None; personality:str|None=None; speech_style:str|None=None; goal:str|None=None; status:str|None=None; description:str|None=None
class WorldCreate(BaseModel): name:str; entity_type:str='setting'; description:str=''; rules:str=''; location:str=''; era:str=''
class WorldOut(WorldCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class WorldUpdate(BaseModel): name:str|None=None; entity_type:str|None=None; description:str|None=None; rules:str|None=None; location:str|None=None; era:str|None=None
class PlotCreate(BaseModel): title:str; plot_type:str='arc'; status:str='planned'; start_episode:int|None=None; end_episode:int|None=None; objective:str=''; conflict:str=''; resolution:str=''
class PlotOut(PlotCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class PlotUpdate(BaseModel): title:str|None=None; plot_type:str|None=None; status:str|None=None; start_episode:int|None=None; end_episode:int|None=None; objective:str|None=None; conflict:str|None=None; resolution:str|None=None
class ForeshadowCreate(BaseModel): title:str; description:str=''; setup_episode:int|None=None; payoff_episode:int|None=None; status:str='open'
class ForeshadowOut(ForeshadowCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class ForeshadowUpdate(BaseModel): title:str|None=None; description:str|None=None; setup_episode:int|None=None; payoff_episode:int|None=None; status:str|None=None
class TimelineCreate(BaseModel): episode_number:int; title:str; world_time:str=''; description:str=''
class TimelineOut(TimelineCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class TimelineUpdate(BaseModel): episode_number:int|None=None; title:str|None=None; world_time:str|None=None; description:str|None=None
class CharacterRelationCreate(BaseModel): from_character_id:int; to_character_id:int; relation_type:str='関係'; strength:int=1; description:str=''
class CharacterRelationOut(CharacterRelationCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class WorldRelationCreate(BaseModel): from_world_id:int; to_world_id:int; relation_type:str='関連'; strength:int=1; description:str=''
class WorldRelationOut(WorldRelationCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class AIGenerate(BaseModel): project_id:int; episode_id:int|None=None; instruction:str=''; mode:str='continue'; rag_limit:int=6
class RagIndex(BaseModel): project_id:int
class RagSearch(BaseModel): project_id:int; query:str; limit:int=8
class CharacterStateOut(BaseModel):
    id:int; project_id:int; character_id:int; episode_id:int|None; episode_number:int; status:str; location:str; emotion:str; health:str; goal:str; knowledge:str; notes:str
    model_config=ConfigDict(from_attributes=True)
class ContinuityIssueOut(BaseModel):
    id:int; project_id:int; episode_number:int|None; issue_type:str; severity:str; message:str; evidence:str; suggestion:str; status:str; model:str
    model_config=ConfigDict(from_attributes=True)
class ContinuityCheck(BaseModel):
    project_id:int; episode_id:int|None=None
class GraphNode(BaseModel):
    id:int; label:str; node_type:str; meta:dict={}
class GraphEdge(BaseModel):
    source:int; target:int; label:str=''; weight:int=1; meta:dict={}
class GraphOut(BaseModel):
    nodes:list[GraphNode]; edges:list[GraphEdge]

class TwinOut(BaseModel):
    project: dict
    metrics: dict
    health: dict
    characters: GraphOut
    world: GraphOut
    timeline: GraphOut
    recent_states: list[dict]
    continuity: dict
    active_plots: list[dict]
    open_foreshadowings: list[dict]


class AutoWriteStart(BaseModel):
    project_id:int
    start_episode:int=1
    end_episode:int=500
    writer_model:str|None=None
    controller_model:str|None=None
    premise:str=''
    overwrite:bool=False

class AutoWriteJobOut(BaseModel):
    id:int; project_id:int; start_episode:int; end_episode:int; current_episode:int; status:str; writer_model:str; controller_model:str; last_message:str; created_at:object; updated_at:object
    progress_percent:float=0
    completed_episodes:int=0
    total_episodes:int=0
    current_phase:str='queued'
    series_planned:bool=False
    arcs_planned:int=0
    mini_arcs_planned:int=0
    episodes_planned:int=0
    episodes_written:int=0
    model_config=ConfigDict(from_attributes=True)

class PlanGenerate(BaseModel):
    project_id:int
    premise:str=''
    arc_number:int|None=None
    mini_arc_number:int|None=None
    episode_number:int|None=None

class PlanOut(BaseModel):
    id:int; project_id:int; title:str=''; content:str; status:str; model:str
    model_config=ConfigDict(from_attributes=True)

class EpisodeRevisionListOut(BaseModel):
    id:int; title:str; summary:str; created_at:object
    model_config=ConfigDict(from_attributes=True)

class EpisodeRevisionOut(EpisodeRevisionListOut):
    content:str
