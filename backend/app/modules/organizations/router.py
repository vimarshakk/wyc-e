import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.db import organization_memberships, organizations
from ...core.deps import require_role

router=APIRouter(prefix='/organizations',tags=['organizations'])
class Create(BaseModel): name:str=Field(min_length=2,max_length=160); kind:str
@router.post('')
async def create(body:Create,user:dict=Depends(require_role('admin'))):
    org={'organization_id':f'org_{uuid.uuid4().hex[:16]}','name':body.name,'kind':body.kind,'status':'VERIFICATION_PENDING','created_at':datetime.now(timezone.utc).isoformat()}
    await organizations.insert_one(org);org.pop('_id',None);return org
@router.post('/{organization_id}/members/{user_id}')
async def add_member(organization_id:str,user_id:str,user:dict=Depends(require_role('admin'))):
    if not await organizations.find_one({'organization_id':organization_id},{'_id':0}):raise HTTPException(404,'Organization not found')
    await organization_memberships.update_one({'organization_id':organization_id,'user_id':user_id},{'$set':{'organization_id':organization_id,'user_id':user_id,'status':'ACTIVE','updated_at':datetime.now(timezone.utc).isoformat()}},upsert=True)
    return {'ok':True}