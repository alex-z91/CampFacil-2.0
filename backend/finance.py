"""MEUCAMP financial core — money amounts are integer centavos; no live charges."""
import uuid
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Literal
router = APIRouter(prefix="/api/finance", tags=["finance"])

class Simulate(BaseModel):
    organizer_id: uuid.UUID
    base_cents: int = Field(ge=100, le=100000000)
    payer_mode: Literal["organizer","athlete","shared"] = "organizer"
    athlete_share_bps: int = Field(ge=0, le=10000, default=0)

class ExternalRegistration(BaseModel):
    organizer_id: uuid.UUID
    reference: str = Field(min_length=3,max_length=120)
    base_cents: int = Field(ge=100,le=100000000)

def commission(base, bps=500, fixed=150):
    return (base*bps+5000)//10000+fixed

def cap_for_ticket(base_cents):
    if base_cents <= 8000: return 10000
    if base_cents <= 15000: return 15000
    return 20000

def quote(base, percent_bps, fixed_cents, mode, share_bps):
    charge=commission(base,percent_bps,fixed_cents)
    share=10000 if mode=="athlete" else (share_bps if mode=="shared" else 0)
    added=(charge*share+5000)//10000
    return {"base_cents":base,"commission_cents":charge,"athlete_fee_cents":added,
            "athlete_total_cents":base+added,"organizer_fee_cents":charge-added}

async def authorized(request, organizer_id, permission="organizer.finance.read"):
    # Existing Neon Auth service verifies the cookie and matches organizer membership.
    from main import authenticated, has_organizer_role, has_platform_role
    user=await authenticated(request)
    pool=request.app.state.pool
    if await has_platform_role(pool,user.user_id,"platform.organizers.manage"):
        return user
    if not await has_organizer_role(pool,user.user_id,str(organizer_id),permission):
        raise HTTPException(403,"Sem permissão financeira nesta organização")
    return user

async def policy(conn, oid):
    row=await conn.fetchrow("SELECT * FROM public.finance_policies WHERE organizer_id=$1",oid)
    if row:return row
    return {"percent_bps":500,"fixed_cents":150,"payer_mode":"organizer","athlete_share_bps":0,"debt_cap_cents":None}

@router.post("/simulate")
async def simulate(p: Simulate, request: Request):
    await authorized(request,p.organizer_id)
    async with request.app.state.pool.acquire() as conn:
        cfg=await policy(conn,p.organizer_id)
    result=quote(p.base_cents,cfg["percent_bps"],cfg["fixed_cents"],p.payer_mode,p.athlete_share_bps)
    result["gateway"]="mercadopago"
    result["mode"]="simulation"
    result["gateway_processing_fee_cents"]=None
    result["split_enabled"]=False
    return result

@router.get("/organizers/{organizer_id}/balance")
async def balance(organizer_id:uuid.UUID,request:Request):
    await authorized(request,organizer_id)
    pool=request.app.state.pool
    debt=await pool.fetchval("SELECT COALESCE(SUM(amount_cents),0) FROM public.finance_ledger WHERE organizer_id=$1",organizer_id)
    rows=await pool.fetch("""SELECT entry_type,amount_cents,created_at,registration_id::text
        FROM public.finance_ledger WHERE organizer_id=$1 ORDER BY created_at DESC LIMIT 50""",organizer_id)
    return {"organizer_id":str(organizer_id),"debt_cents":max(0,debt),"balance_cents":debt,
            "entries":[dict(r) for r in rows]}

@router.post("/external-registration",status_code=201)
async def external_registration(p: ExternalRegistration,request:Request):
    origin=request.headers.get("origin")
    from main import FRONTEND_ORIGIN
    if origin!=FRONTEND_ORIGIN: raise HTTPException(403,"Origem não autorizada")
    user=await authorized(request,p.organizer_id,"organizer.registrations.manage")
    pool=request.app.state.pool
    async with pool.acquire() as conn:
      async with conn.transaction():
        # Serialize all updates on the same organization to enforce its credit cap.
        org=await conn.fetchrow("SELECT id,status FROM public.organizers WHERE id=$1 FOR UPDATE",p.organizer_id)
        if not org or org["status"]!="active":
            raise HTTPException(409,"Organização ainda não está ativa")
        existing=await conn.fetchrow("SELECT id::text,commission_cents FROM public.finance_registrations WHERE organizer_id=$1 AND reference=$2",p.organizer_id,p.reference)
        if existing:
            return {"id":existing["id"],"commission_cents":existing["commission_cents"],"duplicate":True}
        cfg=await policy(conn,p.organizer_id)
        cost=commission(p.base_cents,cfg["percent_bps"],cfg["fixed_cents"])
        cap=cfg["debt_cap_cents"] if cfg["debt_cap_cents"] is not None else cap_for_ticket(p.base_cents)
        debt=await conn.fetchval("SELECT COALESCE(SUM(amount_cents),0) FROM public.finance_ledger WHERE organizer_id=$1",p.organizer_id)
        if max(0,debt)+cost>cap:
            raise HTTPException(409,"Limite de comissão presencial atingido. Quite parte da dívida antes de confirmar novas inscrições.")
        row=await conn.fetchrow("""INSERT INTO public.finance_registrations
            (organizer_id,reference,base_cents,commission_cents,athlete_fee_cents,payment_channel,payment_status,created_by)
            VALUES($1,$2,$3,$4,0,'external','confirmed',$5) RETURNING id::text""",
            p.organizer_id,p.reference,p.base_cents,cost,user.user_id)
        rid=uuid.UUID(row["id"])
        await conn.execute("""INSERT INTO public.finance_ledger
            (organizer_id,registration_id,entry_type,amount_cents,created_by)
            VALUES($1,$2,'external_commission',$3,$4)""",p.organizer_id,rid,cost,user.user_id)
        await conn.execute("""INSERT INTO public.finance_audit
            (organizer_id,actor_user_id,action,reference_id)
            VALUES($1,$2,'external_registration_confirmed',$3)""",p.organizer_id,user.user_id,rid)
    return {"id":row["id"],"commission_cents":cost,"debt_cents":max(0,debt)+cost,
            "debt_cap_cents":cap,"duplicate":False}
