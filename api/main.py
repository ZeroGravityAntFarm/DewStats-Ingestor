from fastapi import FastAPI
from api.api_v1.api import api_router
from db.models import models
from db.session import engine
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(api_router)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    # Use this for debugging purposes only
    import uvicorn

    uvicorn.run(app, 
                host="0.0.0.0",
                proxy_headers=True, # THIS LINE
                forwarded_allow_ips='*', 
                port=8001, 
                log_level="debug")
