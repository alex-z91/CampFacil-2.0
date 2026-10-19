"""Sport registration API: organizer-scoped, server-authorized, pending by default."""
import uuid
from datetime import date
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from finance import authorized, commission, cap_for_ticket, policy

router=APIRouter(prefix="/api/sports",tags=["sports"])
class EventIn(BaseModel):
    organizer_id:uuid.UUID
    name:str=Field(min_length=3,max_length=180)
    event_date:date
    city:str=Field(min_length=2,max_length=120)
class AthleteIn(BaseModel):
    organizer_id:uuid.UUID
    full_name:str=Field(min_length=3,max_length=160)
    birth_date:date
    team:str=Field(default="",max_length=120)
    belt:str=Field(min_length=2,max_length=40)
    weight_grams:int=Field(ge=10000,le=300000)
class CategoryIn(BaseModel):
    organizer_id:uuid.UUID
    event_id:uuid.UUID
    name:str=Field(min_length=2,max_length=120)
    belt:str=Field(min_length=2,max_length=40)
    min_weight_grams:int=Field(ge=0,le=300000)
    max_weight_grams:int=Field(ge=0,le=300000)
    min_birth_year:int=Field(ge=1900,le=2100)
    max_birth_year:int=Field(ge=1900,le=2100)
class EntryIn(BaseModel):
    organizer_id:uuid.UUID
    event_id:uuid.UUID
    athlete_id:uuid.UUID
    category_id:uuid.UUID
    base_cents:int=Field(ge=0,le=100000000)
class ExternalConfirmation(BaseModel):
    organizer_id:uuid.UUID

def require_origin(request):
    from main import trusted_request
    trusted_request(request)

@router.post("/events",status_code=201)
async def create_event(p:EventIn,request:Request):
    require_origin(request)
    user=await authorized(request,p.organizer_id,"organizer.events.manage")
    row=await request.app.state.pool.fetchrow("""INSERT INTO public.sport_events(organizer_id,name,event_date,city,created_by)
        VALUES($1,$2,$3,$4,$5) RETURNING id::text,status""",p.organizer_id,p.name.strip(),p.event_date,p.city.strip(),user.user_id)
    return dict(row)

@router.get("/events/{organizer_id}")
async def list_events(organizer_id:uuid.UUID,request:Request):
    await authorized(request,organizer_id,"organizer.events.read")
    rows=await request.app.state.pool.fetch("""SELECT id::text,name,event_date,city,status FROM public.sport_events
        WHERE organizer_id=$1 ORDER BY event_date DESC LIMIT 100""",organizer_id)
    return {"items":[dict(row) for row in rows]}

@router.post("/athletes",status_code=201)
async def create_athlete(p:AthleteIn,request:Request):
    require_origin(request)
    user=await authorized(request,p.organizer_id,"organizer.registrations.manage")
    if p.birth_date>date.today():raise HTTPException(422,"Data de nascimento inválida")
    row=await request.app.state.pool.fetchrow("""INSERT INTO public.sport_athletes
        (organizer_id,full_name,birth_date,team,belt,weight_grams,created_by)
        VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id::text""",p.organizer_id,p.full_name.strip(),p.birth_date,p.team.strip(),p.belt.strip(),p.weight_grams,user.user_id)
    return dict(row)

@router.post("/categories",status_code=201)
async def create_category(p:CategoryIn,request:Request):
    require_origin(request)
    await authorized(request,p.organizer_id,"organizer.events.manage")
    if p.min_weight_grams>p.max_weight_grams or p.min_birth_year>p.max_birth_year:
        raise HTTPException(422,"Intervalo de categoria inválido")
    try:
        row=await request.app.state.pool.fetchrow("""INSERT INTO public.sport_categories
          (organizer_id,event_id,name,belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year)
          VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id::text""",p.organizer_id,p.event_id,p.name.strip(),p.belt.strip(),p.min_weight_grams,p.max_weight_grams,p.min_birth_year,p.max_birth_year)
    except Exception as e:
        if getattr(e,"sqlstate",None)=="23503":raise HTTPException(404,"Evento não encontrado para esta organização")
        raise
    return dict(row)

@router.post("/entries",status_code=201)
async def create_entry(p:EntryIn,request:Request):
    require_origin(request)
    user=await authorized(request,p.organizer_id,"organizer.registrations.manage")
    async with request.app.state.pool.acquire() as conn:
        event=await conn.fetchrow("SELECT status FROM public.sport_events WHERE id=$1 AND organizer_id=$2",p.event_id,p.organizer_id)
        if not event or event["status"] in ("closed","cancelled"):raise HTTPException(409,"Evento indisponível")
        athlete=await conn.fetchrow("SELECT birth_date,belt,weight_grams FROM public.sport_athletes WHERE id=$1 AND organizer_id=$2",p.athlete_id,p.organizer_id)
        cat=await conn.fetchrow("SELECT belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year FROM public.sport_categories WHERE id=$1 AND event_id=$2 AND organizer_id=$3",p.category_id,p.event_id,p.organizer_id)
        if not athlete or not cat:raise HTTPException(404,"Atleta ou categoria não encontrado")
        if athlete["belt"].casefold()!=cat["belt"].casefold() or not(cat["min_weight_grams"]<=athlete["weight_grams"]<=cat["max_weight_grams"]) or not(cat["min_birth_year"]<=athlete["birth_date"].year<=cat["max_birth_year"]):
            raise HTTPException(422,"Atleta fora dos critérios desta categoria")
        try:
            row=await conn.fetchrow("""INSERT INTO public.sport_entries
                (organizer_id,event_id,athlete_id,category_id,reference,base_cents,created_by)
                VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id::text,payment_status,eligible""",
                p.organizer_id,p.event_id,p.athlete_id,p.category_id,str(uuid.uuid4()),p.base_cents,user.user_id)
        except Exception as e:
            if getattr(e,"sqlstate",None)=="23505":raise HTTPException(409,"Atleta já inscrito nesta categoria")
            raise
    return dict(row)

@router.get("/entries/{organizer_id}/{event_id}")
async def list_entries(organizer_id:uuid.UUID,event_id:uuid.UUID,request:Request):
    await authorized(request,organizer_id,"organizer.events.read")
    rows=await request.app.state.pool.fetch("""SELECT e.id::text,a.full_name,c.name AS category,e.base_cents,e.payment_status,e.eligible
        FROM public.sport_entries e JOIN public.sport_athletes a ON a.id=e.athlete_id
        JOIN public.sport_categories c ON c.id=e.category_id
        WHERE e.organizer_id=$1 AND e.event_id=$2 ORDER BY e.created_at DESC LIMIT 200""",organizer_id,event_id)
    return {"items":[dict(row) for row in rows]}

@router.post("/entries/{entry_id}/confirm-external")
async def confirm_external(entry_id:uuid.UUID,p:ExternalConfirmation,request:Request):
    require_origin(request)
    user=await authorized(request,p.organizer_id,"organizer.registrations.manage")
    pool=request.app.state.pool
    async with pool.acquire() as conn:
      async with conn.transaction():
        org=await conn.fetchrow("SELECT status FROM public.organizers WHERE id=$1 FOR UPDATE",p.organizer_id)
        if not org or org["status"]!="active":raise HTTPException(409,"Organização não ativa")
        entry=await conn.fetchrow("SELECT * FROM public.sport_entries WHERE id=$1 AND organizer_id=$2 FOR UPDATE",entry_id,p.organizer_id)
        if not entry:raise HTTPException(404,"Inscrição não encontrada")
        if entry["payment_status"]=="external_confirmed":return {"ok":True,"duplicate":True}
        if entry["payment_status"]!="pending" or entry["base_cents"]==0:raise HTTPException(409,"Inscrição não elegível à confirmação externa")
        cfg=await policy(conn,p.organizer_id)
        cost=commission(entry["base_cents"],cfg["percent_bps"],cfg["fixed_cents"])
        cap=cfg["debt_cap_cents"] if cfg["debt_cap_cents"] is not None else cap_for_ticket(entry["base_cents"])
        debt=await conn.fetchval("SELECT COALESCE(SUM(amount_cents),0) FROM public.finance_ledger WHERE organizer_id=$1",p.organizer_id)
        if max(0,debt)+cost>cap:raise HTTPException(409,"Limite de comissão atingido. Regularize o saldo antes de confirmar.")
        finance=await conn.fetchrow("""INSERT INTO public.finance_registrations
          (organizer_id,reference,base_cents,commission_cents,athlete_fee_cents,payment_channel,payment_status,created_by)
          VALUES($1,$2,$3,$4,0,'external','confirmed',$5) RETURNING id""",
          p.organizer_id,str(entry_id),entry["base_cents"],cost,user.user_id)
        await conn.execute("""INSERT INTO public.finance_ledger
          (organizer_id,registration_id,entry_type,amount_cents,created_by)
          VALUES($1,$2,'external_commission',$3,$4)""",p.organizer_id,finance["id"],cost,user.user_id)
        await conn.execute("UPDATE public.sport_entries SET payment_status='external_confirmed',eligible=true WHERE id=$1",entry_id)
        await conn.execute("""INSERT INTO public.finance_audit(organizer_id,actor_user_id,action,reference_id)
          VALUES($1,$2,'sport_entry_external_confirmed',$3)""",p.organizer_id,user.user_id,finance["id"])
    return {"ok":True,"commission_cents":cost,"debt_cents":max(0,debt)+cost}

class AthleteEdit(BaseModel):
    full_name:str=Field(min_length=3,max_length=160)
    team:str=Field(default="",max_length=120)
    birth_date:date
    belt:str=Field(min_length=2,max_length=40)
    weight_grams:int=Field(ge=10000,le=300000)

@router.get("/athletes/{organizer_id}")
async def list_athletes(organizer_id:uuid.UUID,request:Request):
    await authorized(request,organizer_id,"organizer.events.read")
    rows=await request.app.state.pool.fetch("""SELECT id::text,full_name,birth_date,team,belt,weight_grams
      FROM public.sport_athletes WHERE organizer_id=$1 ORDER BY created_at DESC LIMIT 500""",organizer_id)
    return {"items":[dict(row) for row in rows]}

@router.get("/categories/{organizer_id}/{event_id}")
async def list_categories(organizer_id:uuid.UUID,event_id:uuid.UUID,request:Request):
    await authorized(request,organizer_id,"organizer.events.read")
    rows=await request.app.state.pool.fetch("""SELECT id::text,name,belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year
      FROM public.sport_categories WHERE organizer_id=$1 AND event_id=$2 ORDER BY name LIMIT 300""",organizer_id,event_id)
    return {"items":[dict(row) for row in rows]}

@router.patch("/athletes/{organizer_id}/{athlete_id}")
async def edit_athlete(organizer_id:uuid.UUID,athlete_id:uuid.UUID,p:AthleteEdit,request:Request):
    require_origin(request)
    await authorized(request,organizer_id,"organizer.registrations.manage")
    if p.birth_date>date.today():raise HTTPException(422,"Nascimento inválido")
    pool=request.app.state.pool
    async with pool.acquire() as conn:
      async with conn.transaction():
        current=await conn.fetchrow("SELECT id FROM public.sport_athletes WHERE id=$1 AND organizer_id=$2 FOR UPDATE",athlete_id,organizer_id)
        if not current:raise HTTPException(404,"Atleta não encontrado")
        entries=await conn.fetch("""SELECT e.payment_status,c.belt,c.min_weight_grams,c.max_weight_grams,c.min_birth_year,c.max_birth_year
          FROM public.sport_entries e JOIN public.sport_categories c ON c.id=e.category_id
          WHERE e.athlete_id=$1 AND e.organizer_id=$2""",athlete_id,organizer_id)
        for e in entries:
            if e["payment_status"] not in ("pending","cancelled"):
                raise HTTPException(409,"Dados esportivos de atleta confirmado exigem revisão administrativa")
            if e["payment_status"]=="pending" and not(e["belt"].casefold()==p.belt.casefold()
                and e["min_weight_grams"]<=p.weight_grams<=e["max_weight_grams"]
                and e["min_birth_year"]<=p.birth_date.year<=e["max_birth_year"]):
                raise HTTPException(409,"A edição deixaria uma inscrição pendente fora da categoria")
        await conn.execute("""UPDATE public.sport_athletes
          SET full_name=$1,team=$2,birth_date=$3,belt=$4,weight_grams=$5
          WHERE id=$6 AND organizer_id=$7""",p.full_name.strip(),p.team.strip(),p.birth_date,p.belt.strip(),p.weight_grams,athlete_id,organizer_id)
    return {"ok":True}
