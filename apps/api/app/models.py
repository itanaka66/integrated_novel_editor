from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Project(Base):
    __tablename__='projects'
    id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(200)); description:Mapped[str]=mapped_column(Text,default=''); genre:Mapped[str]=mapped_column(String(100),default=''); rules:Mapped[str]=mapped_column(Text,default='')
    episodes=relationship('Episode',back_populates='project',cascade='all, delete-orphan'); characters=relationship('Character',back_populates='project',cascade='all, delete-orphan'); worlds=relationship('WorldEntity',back_populates='project',cascade='all, delete-orphan'); plots=relationship('Plot',back_populates='project',cascade='all, delete-orphan'); foreshadowings=relationship('Foreshadowing',back_populates='project',cascade='all, delete-orphan')
class Episode(Base):
    __tablename__='episodes'
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE')); number:Mapped[int]=mapped_column(Integer); title:Mapped[str]=mapped_column(String(300)); summary:Mapped[str]=mapped_column(Text,default=''); content:Mapped[str]=mapped_column(Text,default=''); updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    project=relationship('Project',back_populates='episodes')
class Character(Base):
    __tablename__='characters'
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE')); name:Mapped[str]=mapped_column(String(200)); role:Mapped[str]=mapped_column(String(100),default=''); personality:Mapped[str]=mapped_column(Text,default=''); speech_style:Mapped[str]=mapped_column(Text,default=''); goal:Mapped[str]=mapped_column(Text,default=''); status:Mapped[str]=mapped_column(String(50),default='alive'); description:Mapped[str]=mapped_column(Text,default='')
    project=relationship('Project',back_populates='characters')
class WorldEntity(Base):
    __tablename__='world_entities'
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE')); name:Mapped[str]=mapped_column(String(200)); entity_type:Mapped[str]=mapped_column(String(100),default='setting'); description:Mapped[str]=mapped_column(Text,default=''); rules:Mapped[str]=mapped_column(Text,default=''); location:Mapped[str]=mapped_column(String(200),default=''); era:Mapped[str]=mapped_column(String(200),default='')
    project=relationship('Project',back_populates='worlds')
class Plot(Base):
    __tablename__='plots'
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE')); title:Mapped[str]=mapped_column(String(300)); plot_type:Mapped[str]=mapped_column(String(100),default='arc'); status:Mapped[str]=mapped_column(String(50),default='planned'); start_episode:Mapped[int|None]=mapped_column(nullable=True); end_episode:Mapped[int|None]=mapped_column(nullable=True); objective:Mapped[str]=mapped_column(Text,default=''); conflict:Mapped[str]=mapped_column(Text,default=''); resolution:Mapped[str]=mapped_column(Text,default='')
    project=relationship('Project',back_populates='plots')
class Foreshadowing(Base):
    __tablename__='foreshadowings'
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE')); title:Mapped[str]=mapped_column(String(300)); description:Mapped[str]=mapped_column(Text,default=''); setup_episode:Mapped[int|None]=mapped_column(nullable=True); payoff_episode:Mapped[int|None]=mapped_column(nullable=True); status:Mapped[str]=mapped_column(String(50),default='open')
    project=relationship('Project',back_populates='foreshadowings')
class TimelineEvent(Base):
    __tablename__='timeline_events'
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE')); episode_number:Mapped[int]=mapped_column(Integer); title:Mapped[str]=mapped_column(String(300)); world_time:Mapped[str]=mapped_column(String(200),default=''); description:Mapped[str]=mapped_column(Text,default='')


class CharacterState(Base):
    __tablename__='character_states'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'))
    character_id:Mapped[int]=mapped_column(ForeignKey('characters.id',ondelete='CASCADE'))
    episode_id:Mapped[int|None]=mapped_column(ForeignKey('episodes.id',ondelete='SET NULL'),nullable=True)
    episode_number:Mapped[int]=mapped_column(Integer)
    status:Mapped[str]=mapped_column(String(50),default='')
    location:Mapped[str]=mapped_column(String(300),default='')
    emotion:Mapped[str]=mapped_column(String(300),default='')
    health:Mapped[str]=mapped_column(String(300),default='')
    goal:Mapped[str]=mapped_column(Text,default='')
    knowledge:Mapped[str]=mapped_column(Text,default='')
    notes:Mapped[str]=mapped_column(Text,default='')

class ContinuityIssue(Base):
    __tablename__='continuity_issues'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'))
    episode_number:Mapped[int|None]=mapped_column(Integer,nullable=True)
    issue_type:Mapped[str]=mapped_column(String(50),default='other')
    severity:Mapped[str]=mapped_column(String(20),default='medium')
    message:Mapped[str]=mapped_column(Text)
    evidence:Mapped[str]=mapped_column(Text,default='')
    suggestion:Mapped[str]=mapped_column(Text,default='')
    status:Mapped[str]=mapped_column(String(30),default='open')
    model:Mapped[str]=mapped_column(String(100),default='')

class CharacterRelation(Base):
    __tablename__='character_relations'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'))
    from_character_id:Mapped[int]=mapped_column(ForeignKey('characters.id',ondelete='CASCADE'))
    to_character_id:Mapped[int]=mapped_column(ForeignKey('characters.id',ondelete='CASCADE'))
    relation_type:Mapped[str]=mapped_column(String(100),default='関係')
    strength:Mapped[int]=mapped_column(Integer,default=1)
    description:Mapped[str]=mapped_column(Text,default='')

class WorldRelation(Base):
    __tablename__='world_relations'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'))
    from_world_id:Mapped[int]=mapped_column(ForeignKey('world_entities.id',ondelete='CASCADE'))
    to_world_id:Mapped[int]=mapped_column(ForeignKey('world_entities.id',ondelete='CASCADE'))
    relation_type:Mapped[str]=mapped_column(String(100),default='関連')
    strength:Mapped[int]=mapped_column(Integer,default=1)
    description:Mapped[str]=mapped_column(Text,default='')


class AutoWriteJob(Base):
    __tablename__='auto_write_jobs'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'))
    start_episode:Mapped[int]=mapped_column(Integer,default=1)
    end_episode:Mapped[int]=mapped_column(Integer,default=500)
    current_episode:Mapped[int]=mapped_column(Integer,default=1)
    status:Mapped[str]=mapped_column(String(30),default='queued')
    writer_model:Mapped[str]=mapped_column(String(150),default='qwen3.8:27b')
    controller_model:Mapped[str]=mapped_column(String(150),default='qwen3:14b')
    last_message:Mapped[str]=mapped_column(Text,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class SeriesPlan(Base):
    __tablename__='series_plans'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),unique=True)
    total_episodes:Mapped[int]=mapped_column(Integer,default=500)
    title:Mapped[str]=mapped_column(String(300),default='')
    premise:Mapped[str]=mapped_column(Text,default='')
    content:Mapped[str]=mapped_column(Text,default='')
    status:Mapped[str]=mapped_column(String(30),default='draft')
    model:Mapped[str]=mapped_column(String(150),default='')

class ArcPlan(Base):
    __tablename__='arc_plans'
    id:Mapped[int]=mapped_column(primary_key=True)
    series_plan_id:Mapped[int]=mapped_column(ForeignKey('series_plans.id',ondelete='CASCADE'))
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'))
    arc_number:Mapped[int]=mapped_column(Integer)
    start_episode:Mapped[int]=mapped_column(Integer)
    end_episode:Mapped[int]=mapped_column(Integer)
    title:Mapped[str]=mapped_column(String(300),default='')
    content:Mapped[str]=mapped_column(Text,default='')
    status:Mapped[str]=mapped_column(String(30),default='planned')
    model:Mapped[str]=mapped_column(String(150),default='')

class MiniArcPlan(Base):
    __tablename__='mini_arc_plans'
    id:Mapped[int]=mapped_column(primary_key=True)
    arc_plan_id:Mapped[int]=mapped_column(ForeignKey('arc_plans.id',ondelete='CASCADE'))
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'))
    mini_arc_number:Mapped[int]=mapped_column(Integer)
    start_episode:Mapped[int]=mapped_column(Integer)
    end_episode:Mapped[int]=mapped_column(Integer)
    title:Mapped[str]=mapped_column(String(300),default='')
    content:Mapped[str]=mapped_column(Text,default='')
    status:Mapped[str]=mapped_column(String(30),default='planned')
    model:Mapped[str]=mapped_column(String(150),default='')

class EpisodePlan(Base):
    __tablename__='episode_plans'
    id:Mapped[int]=mapped_column(primary_key=True)
    mini_arc_plan_id:Mapped[int]=mapped_column(ForeignKey('mini_arc_plans.id',ondelete='CASCADE'))
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'))
    episode_number:Mapped[int]=mapped_column(Integer)
    title:Mapped[str]=mapped_column(String(300),default='')
    content:Mapped[str]=mapped_column(Text,default='')
    status:Mapped[str]=mapped_column(String(30),default='planned')
    model:Mapped[str]=mapped_column(String(150),default='')
