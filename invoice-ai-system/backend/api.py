from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ Allow frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Test route
@app.get("/")
def home():
    return {"message": "API working 🚀"}


# 🔐 LOGIN API (FIXED)
@app.post("/login")
def login(data: dict):
    username = data.get("username")
    password = data.get("password")

    if username == "admin" and password == "admin123":
        return {"token": "success"}
    else:
        return {"error": "Invalid credentials"}