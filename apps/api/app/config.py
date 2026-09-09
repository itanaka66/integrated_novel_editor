from pydantic_settings import BaseSettings
class Settings(BaseSettings):
database_url:str='postgresql+psycopg2://novel:novel@localhost:5432/novel'; qdrant_url:str='http://localhost:6333'; ollama_url:str='http://localhost:11434'; ollama_model:str='qwen3:8b'; ollama_embed_model:str='nomic-embed-text'; cors_origins:str='http://localhost:3000'
admin_username:str='admin'; admin_password:str='novel-studio-change-me'
qdrant_url:str='http://localhost:6333'
ollama_url:str='http://localhost:11434'
ollama_model:str='qwen3.8:27b'
ollama_embed_model:str='nomic-embed-text'
controller_ollama_url:str='http://localhost:11434'
controller_ollama_model:str='qwen3:14b'
cors_origins:str='http://localhost:3000'
settings=Settings()
