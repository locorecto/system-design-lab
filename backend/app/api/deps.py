from app.core.database import SqliteRepository
from app.services.design_generator import DesignGenerator
from app.services.recommendation_engine import RecommendationEngine
from app.services.run_manager import RunManager


repo = SqliteRepository()
run_manager = RunManager(repo=repo)
recommendation_engine = RecommendationEngine(repo=repo)
design_generator = DesignGenerator()
