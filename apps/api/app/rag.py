from qdrant_client import QdrantClient,models
from .config import settings
from .ollama import embed
COL='novel_story_memory'
def client(): return QdrantClient(url=settings.qdrant_url)
def ensure(size):
 c=client()
 try:c.get_collection(COL)
 except:c.create_collection(collection_name=COL,vectors_config=models.VectorParams(size=size,distance=models.Distance.COSINE))
async def index(chunks):
 if not chunks:return 0
 vs=await embed([x['text'] for x in chunks]);ensure(len(vs[0])); c=client(); c.upsert(collection_name=COL,points=[models.PointStruct(id=x['id'],vector=v,payload=x) for x,v in zip(chunks,vs)]);return len(chunks)
async def search(project_id,q,limit=8):
 v=(await embed([q]))[0];ensure(len(v)); r=client().query_points(collection_name=COL,query=v,query_filter=models.Filter(must=[models.FieldCondition(key='project_id',match=models.MatchValue(value=project_id))]),with_payload=True,limit=limit);return [p.payload for p in r.points]
