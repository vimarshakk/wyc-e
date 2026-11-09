import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.access import require_verified_member
from ...core.audit import write_audit
from ...core.db import emergency_access_events
from ...core.deps import require_role

router=APIRouter(prefix='/emergency-access',tags=['emergency-access'])
class BreakGlass(BaseModel):
    patient_id:str
    reason:str=Field(min_length=20,max_length=500)
    minutes:int=Field(default=30,ge=5,le=60)
@router.post('')
async def activate(body:BreakGlass,user:dict=Depends(require_role('doctor'))):
    await require_verified_member(user)
    now=datetime.now(timezone.utc); event={'event_id':f'bg_{uuid.uuid4().hex[:16]}','patient_id':body.patient_id,'actor_id':user['user_id'],'reason':body.reason,'status':'ACTIVE','created_at':now.isoformat(),'expires_at':(now+timedelta(minutes=body.minutes)).isoformat()}
    await emergency_access_events.insert_one(event);event.pop('_id',None)
    await write_audit(user['user_id'],'chart.break_glass','patient',body.patient_id,{'event_id':event['event_id'],'minutes':body.minutes})
    return event