from pydantic import BaseModel,ConfigDict
class ProjectCreate(BaseModel): name:str; description:str=''; genre:str=''; rules:str=''
class ProjectOut(ProjectCreate): id:int; model_config=ConfigDict(from_attributes=True)
class EpisodeCreate(BaseModel): number:int; title:str; summary:str=''; content:str=''
class EpisodeOut(EpisodeCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class EpisodeUpdate(BaseModel): title:str|None=None; summary:str|None=None; content:str|None=None
class CharacterCreate(BaseModel): name:str; role:str=''; personality:str=''; speech_style:str=''; goal:str=''; status:str='alive'; description:str=''
class CharacterOut(CharacterCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class WorldCreate(BaseModel): name:str; entity_type:str='setting'; description:str=''; rules:str=''; location:str=''; era:str=''
class WorldOut(WorldCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class PlotCreate(BaseModel): title:str; plot_type:str='arc'; status:str='planned'; start_episode:int|None=None; end_episode:int|None=None; objective:str=''; conflict:str=''; resolution:str=''
class PlotOut(PlotCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class ForeshadowCreate(BaseModel): title:str; description:str=''; setup_episode:int|None=None; payoff_episode:int|None=None; status:str='open'
class ForeshadowOut(ForeshadowCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
class TimelineCreate(BaseModel): episode_number:int; title:str; world_time:str=''; description:str=''
class TimelineOut(TimelineCreate): id:int; project_id:int; model_config=ConfigDict(from_attributes=True)
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
