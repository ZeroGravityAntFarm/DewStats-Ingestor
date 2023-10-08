from fastapi import APIRouter, Depends, HTTPException, Request
from db import controller
from db.session import SessionLocal
from sqlalchemy.orm import Session

router = APIRouter()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db

    finally:
        db.close()


#Endpoint to catch game stats
@router.post("/stats")
async def post_stats(request: Request, db: Session = Depends(get_db)):
    match_request = await request.json()
    stats = controller.create_stats(db, stats=match_request, header=request.headers.get('User-Agent'), ip=request.client.host)

    if not stats:
        return HTTPException(status_code=500, detail="Failed to create stats")
    
    else:
        return HTTPException(status_code=200)
