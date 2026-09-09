import os
import sys
from pathlib import Path

# Tests are intentionally independent of the production PostgreSQL URL.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ai_novel_studio.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
