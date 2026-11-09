import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from ...core.db import chart_consents
from ...core.deps import require_role

router=APIRouter(prefix='/consents',tags=['consents'])
class Grant(BaseModel):
    grantee_id:str
    scopes:list[str]=Field(min_length=1)
    expires_at:str
@router.post('')
async def grant(body:Grant,user:dict=Depends(require_role('patient'))):
    doc={'consent_id':f'cc_{uuid.uuid4().hex[:16]}','patient_id':user['user_id'],'grantee_id':body.grantee_id,'scopes':body.scopes,'expires_at':body.expires_at,'status':'active','created_at':datetime.now(timezone.utc).isoformat()}
    await chart_consents.insert_one(doc);doc.pop('_id',None);return doc
@router.get('/mine')
async def mine(user:dict=Depends(require_role('patient'))):
    return await chart_consents.find({'patient_id':user['user_id']},{'_id':0}).to_list(200)