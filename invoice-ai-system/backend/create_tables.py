from database.db import engine
from models.schemas import Base, Invoice
from modules.agents import AgentAction   

# 🔥 This line creates tables automatically
Base.metadata.create_all(bind=engine)

print("✅ Tables created automatically!")