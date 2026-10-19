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
    has_gi:bool=True
    has_nogi:bool=False
    has_absolute:bool=False
class AthleteIn(BaseModel):
    organizer_id:uuid.UUID
    full_name:str=Field(min_length=3,max_length=160)
    birth_date:date
    team:str=Field(default="",max_length=120)
    belt:str=Field(min_length=2,max_length=40)
    weight_grams:int=Field(ge=10000,le=300000)
    sex:Literal['male','female']
class CategoryIn(BaseModel):
    organizer_id:uuid.UUID
    event_id:uuid.UUID
    name:str=Field(min_length=2,max_length=120)
    belt:str=Field(min_length=2,max_length=40)
    min_weight_grams:int=Field(ge=0,le=300000)
    max_weight_grams:int=Field(ge=0,le=300000)
    min_birth_year:int=Field(ge=1900,le=2100)
    max_birth_year:int=Field(ge=1900,le=2100)
    sex:Literal['male','female']
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
    if not p.has_gi and not p.has_nogi:
        raise HTTPException(422,"Selecione Gi, No-Gi ou ambos")
    async with request.app.state.pool.acquire() as conn:
      async with conn.transaction():
        row=await conn.fetchrow("""INSERT INTO public.sport_events
            (organizer_id,name,event_date,city,created_by,has_gi,has_nogi,has_absolute)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id::text,status""",
            p.organizer_id,p.name.strip(),p.event_date,p.city.strip(),user.user_id,
            p.has_gi,p.has_nogi,p.has_absolute)
        created=await build_default_categories(conn,p.organizer_id,uuid.UUID(row["id"]),p.event_date.year,
            [m for m,enabled in (("gi",p.has_gi),("nogi",p.has_nogi)) if enabled],p.has_absolute)
    return {**dict(row),"categories_created":created}

@router.get("/events/{organizer_id}")
async def list_events(organizer_id:uuid.UUID,request:Request):
    await authorized(request,organizer_id,"organizer.events.read")
    rows=await request.app.state.pool.fetch("""SELECT id::text,name,event_date,city,status,has_gi,has_nogi,has_absolute FROM public.sport_events
        WHERE organizer_id=$1 ORDER BY event_date DESC LIMIT 100""",organizer_id)
    return {"items":[dict(row) for row in rows]}

@router.post("/athletes",status_code=201)
async def create_athlete(p:AthleteIn,request:Request):
    require_origin(request)
    user=await authorized(request,p.organizer_id,"organizer.registrations.manage")
    if p.birth_date>date.today():raise HTTPException(422,"Data de nascimento inválida")
    row=await request.app.state.pool.fetchrow("""INSERT INTO public.sport_athletes
        (organizer_id,full_name,birth_date,team,belt,weight_grams,created_by,sex)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id::text""",p.organizer_id,p.full_name.strip(),p.birth_date,p.team.strip(),p.belt.strip(),p.weight_grams,user.user_id,p.sex)
    return dict(row)

@router.post("/categories",status_code=201)
async def create_category(p:CategoryIn,request:Request):
    require_origin(request)
    await authorized(request,p.organizer_id,"organizer.events.manage")
    if p.min_weight_grams>p.max_weight_grams or p.min_birth_year>p.max_birth_year:
        raise HTTPException(422,"Intervalo de categoria inválido")
    try:
        row=await request.app.state.pool.fetchrow("""INSERT INTO public.sport_categories
          (organizer_id,event_id,name,belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year,sex)
          VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id::text""",p.organizer_id,p.event_id,p.name.strip(),p.belt.strip(),p.min_weight_grams,p.max_weight_grams,p.min_birth_year,p.max_birth_year,p.sex)
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
        athlete=await conn.fetchrow("SELECT birth_date,belt,weight_grams,sex FROM public.sport_athletes WHERE id=$1 AND organizer_id=$2",p.athlete_id,p.organizer_id)
        cat=await conn.fetchrow("SELECT belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year,sex FROM public.sport_categories WHERE id=$1 AND event_id=$2 AND organizer_id=$3",p.category_id,p.event_id,p.organizer_id)
        if not athlete or not cat:raise HTTPException(404,"Atleta ou categoria não encontrado")
        if not athlete["sex"] or athlete["sex"]!=cat["sex"] or athlete["belt"].casefold()!=cat["belt"].casefold() or not(cat["min_weight_grams"]<=athlete["weight_grams"]<=cat["max_weight_grams"]) or not(cat["min_birth_year"]<=athlete["birth_date"].year<=cat["max_birth_year"]):
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
    rows=await request.app.state.pool.fetch("""SELECT e.id::text,e.athlete_id::text,e.category_id::text,a.full_name,c.name AS category,e.base_cents,e.payment_status,e.eligible
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
    rows=await request.app.state.pool.fetch("""SELECT id::text,full_name,birth_date,team,belt,weight_grams,sex
      FROM public.sport_athletes WHERE organizer_id=$1 ORDER BY created_at DESC LIMIT 500""",organizer_id)
    return {"items":[dict(row) for row in rows]}

@router.get("/categories/{organizer_id}/{event_id}")
async def list_categories(organizer_id:uuid.UUID,event_id:uuid.UUID,request:Request):
    await authorized(request,organizer_id,"organizer.events.read")
    rows=await request.app.state.pool.fetch("""SELECT id::text,name,belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year,sex,modality,is_absolute
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

# Templates inspired by IBJJF adult/master Gi divisions. Weight includes kimono.
GI_WEIGHTS = {
 "male":[("Galo",57500),("Pluma",64000),("Pena",70000),("Leve",76000),("Médio",82300),("Meio-pesado",88300),("Pesado",94300),("Superpesado",100500),("Pesadíssimo",300000)],
 "female":[("Galo",48500),("Pluma",53500),("Pena",58500),("Leve",64000),("Médio",69000),("Meio-pesado",74000),("Pesado",79300),("Superpesado",300000)]
}
NO_GI_WEIGHTS = {
 "male":[("Galo",55500),("Pluma",61500),("Pena",67500),("Leve",73500),("Médio",79500),("Meio-pesado",85500),("Pesado",91500),("Superpesado",97500),("Pesadíssimo",300000)],
 "female":[("Galo",46500),("Pluma",51500),("Pena",56500),("Leve",61500),("Médio",66500),("Meio-pesado",71500),("Pesado",76500),("Superpesado",300000)]
}
# Central catalog: year-of-birth age groups and eligible belts (IBJJF-inspired).
AGE_BELTS = {
 "mighty1":(4,4,["Branca","Cinza"]),
 "mighty2":(5,5,["Branca","Cinza"]),
 "mighty3":(6,6,["Branca","Cinza"]),
 "peewee1":(7,7,["Branca","Cinza","Amarela"]),
 "peewee2":(8,8,["Branca","Cinza","Amarela"]),
 "peewee3":(9,9,["Branca","Cinza","Amarela"]),
 "junior1":(10,10,["Branca","Cinza","Amarela","Laranja"]),
 "junior2":(11,11,["Branca","Cinza","Amarela","Laranja"]),
 "junior3":(12,12,["Branca","Cinza","Amarela","Laranja"]),
 "teen1":(13,13,["Branca","Cinza","Amarela","Laranja","Verde"]),
 "teen2":(14,14,["Branca","Cinza","Amarela","Laranja","Verde"]),
 "teen3":(15,15,["Branca","Cinza","Amarela","Laranja","Verde"]),
 "juvenile1":(16,16,["Branca","Azul","Roxa"]),
 "juvenile2":(17,17,["Branca","Azul","Roxa"]),
 "adult":(18,120,["Branca","Azul","Roxa","Marrom","Preta"]),
 "master1":(30,120,["Branca","Azul","Roxa","Marrom","Preta"]),
 "master2":(36,120,["Branca","Azul","Roxa","Marrom","Preta"]),
 "master3":(41,120,["Branca","Azul","Roxa","Marrom","Preta"]),
 "master4":(46,120,["Branca","Azul","Roxa","Marrom","Preta"]),
 "master5":(51,120,["Branca","Azul","Roxa","Marrom","Preta"]),
 "master6":(56,120,["Azul","Roxa","Marrom","Preta"]),
 "master7":(61,120,["Azul","Roxa","Marrom","Preta"])
}
@router.get("/category-catalog")
async def category_catalog(request:Request):
    # Public static definitions, not organizer data.
    return {"age_groups":[{"key":key,"min_age":age[0],"max_age":age[1],"belts":age[2],
         "auto_weights_available":key in ("adult","master1","master2","master3","master4","master5","master6","master7")}
         for key,age in AGE_BELTS.items()],
        "modalities":["gi","nogi"],"sex_divisions":["male","female"],
        "notice":"Infantil e juvenil: pesos dependem de tabela específica e do evento; não aplicar pesos adultos."}

class TemplateBatch(BaseModel):
    organizer_id:uuid.UUID
    event_id:uuid.UUID
    sex:Literal["male","female"]
    age_group:Literal["adult","master1","master2","master3","master4","master5","master6","master7"]
    belts:list[Literal["Branca","Azul","Roxa","Marrom","Preta"]]=Field(min_length=1,max_length=5)
    modality:Literal["gi","nogi"]="gi"

@router.post("/categories/templates",status_code=201)
async def create_category_templates(p:TemplateBatch,request:Request):
    require_origin(request)
    await authorized(request,p.organizer_id,"organizer.events.manage")
    pool=request.app.state.pool
    async with pool.acquire() as conn:
      async with conn.transaction():
        event=await conn.fetchrow("SELECT event_date,status FROM public.sport_events WHERE id=$1 AND organizer_id=$2 FOR UPDATE",p.event_id,p.organizer_id)
        if not event:raise HTTPException(404,"Evento não encontrado")
        if event["status"] in ("closed","cancelled"):raise HTTPException(409,"Evento encerrado")
        year=event["event_date"].year
        ages={"adult":(18,120),"master1":(30,120),"master2":(36,120),"master3":(41,120),"master4":(46,120),"master5":(51,120),"master6":(56,120),"master7":(61,120)}
        minage,maxage=ages[p.age_group]
        # Masters can register in younger age divisions; age cap is intentionally open.
        born_min=max(1900,year-maxage);born_max=min(2100,year-minage)
        if any(b not in AGE_BELTS[p.age_group][2] for b in p.belts):
            raise HTTPException(422,"Faixa não permitida para esta divisão etária no catálogo padrão")
        created=0
        for belt in dict.fromkeys(p.belts):
          for label,upper in (NO_GI_WEIGHTS if p.modality=="nogi" else GI_WEIGHTS)[p.sex]:
            name=("NO-GI" if p.modality=="nogi" else "GI")+" · "+p.age_group.upper()+" · "+("Masculino" if p.sex=="male" else "Feminino")+" · "+label
            result=await conn.execute("""
                INSERT INTO public.sport_categories
                (organizer_id,event_id,name,belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year,sex,modality)
                VALUES($1,$2,$3,$4,0,$5,$6,$7,$8,$9)
                ON CONFLICT (event_id,sex,belt,name) DO NOTHING
            """,p.organizer_id,p.event_id,name,belt,upper,born_min,born_max,p.sex,p.modality)
            if result=="INSERT 0 1":created+=1
    return {"created":created,"requested":len(dict.fromkeys(p.belts))*len((NO_GI_WEIGHTS if p.modality=="nogi" else GI_WEIGHTS)[p.sex]),"rules":p.modality+"_weight_with_uniform","event_year":year}

async def build_default_categories(conn,oid,eid,year,modalities,absolute):
    """Adult/master preset; do not apply adult weight limits to children."""
    created=0
    for modality in modalities:
      weights=GI_WEIGHTS if modality=="gi" else NO_GI_WEIGHTS
      for group in ("adult","master1","master2","master3","master4","master5","master6","master7"):
        low,high,belts=AGE_BELTS[group]
        first=max(1900,year-high); last=min(2100,year-low)
        for sex in ("male","female"):
          for belt in belts:
            previous_max=0
            for label,maxweight in weights[sex]:
              name=f"{modality.upper()} · {group.upper()} · {'Masculino' if sex=='male' else 'Feminino'} · {label}"
              result=await conn.execute("""INSERT INTO public.sport_categories
                  (organizer_id,event_id,name,belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year,sex,modality,is_absolute)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,false)
                  ON CONFLICT (event_id,sex,belt,name) DO NOTHING""",
                  oid,eid,name,belt,previous_max+1,maxweight,first,last,sex,modality)
              previous_max=maxweight
              created+=result=="INSERT 0 1"
            if absolute:
              name=f"{modality.upper()} · {group.upper()} · {'Masculino' if sex=='male' else 'Feminino'} · Absoluto"
              result=await conn.execute("""INSERT INTO public.sport_categories
                  (organizer_id,event_id,name,belt,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year,sex,modality,is_absolute)
                  VALUES($1,$2,$3,$4,0,300000,$5,$6,$7,$8,true)
                  ON CONFLICT (event_id,sex,belt,name) DO NOTHING""",
                  oid,eid,name,belt,first,last,sex,modality)
              created+=result=="INSERT 0 1"
    return created

class CategoryUpdate(BaseModel):
    organizer_id:uuid.UUID
    name:str=Field(min_length=2,max_length=120)
    belt:str=Field(min_length=2,max_length=40)
    sex:Literal["male","female"]
    modality:Literal["gi","nogi"]
    min_weight_grams:int=Field(ge=0,le=300000)
    max_weight_grams:int=Field(ge=0,le=300000)
    min_birth_year:int=Field(ge=1900,le=2100)
    max_birth_year:int=Field(ge=1900,le=2100)

@router.patch("/categories/{category_id}")
async def update_category(category_id:uuid.UUID,p:CategoryUpdate,request:Request):
    require_origin(request)
    await authorized(request,p.organizer_id,"organizer.events.manage")
    if p.min_weight_grams>p.max_weight_grams or p.min_birth_year>p.max_birth_year:
        raise HTTPException(422,"Intervalos inválidos")
    async with request.app.state.pool.acquire() as conn:
      async with conn.transaction():
        cat=await conn.fetchrow("""SELECT c.*,e.status AS event_status FROM public.sport_categories c
          JOIN public.sport_events e ON e.id=c.event_id
          WHERE c.id=$1 AND c.organizer_id=$2 FOR UPDATE OF c""",category_id,p.organizer_id)
        if not cat: raise HTTPException(404,"Categoria não encontrada")
        if cat["event_status"] in ("closed","cancelled"):raise HTTPException(409,"Evento encerrado")
        count=await conn.fetchval("SELECT COUNT(*) FROM public.sport_entries WHERE category_id=$1",category_id)
        if count:raise HTTPException(409,"Esta categoria possui inscrições. Não é possível alterar seus critérios; crie uma nova categoria.")
        if cat["is_absolute"] and (p.min_weight_grams!=0 or p.max_weight_grams!=300000):
            raise HTTPException(422,"O absoluto precisa permanecer sem limite de peso")
        try:
            await conn.execute("""UPDATE public.sport_categories SET name=$1,belt=$2,sex=$3,modality=$4,
               min_weight_grams=$5,max_weight_grams=$6,min_birth_year=$7,max_birth_year=$8
               WHERE id=$9 AND organizer_id=$10""",p.name.strip(),p.belt.strip(),p.sex,p.modality,
               p.min_weight_grams,p.max_weight_grams,p.min_birth_year,p.max_birth_year,category_id,p.organizer_id)
        except Exception as e:
            if getattr(e,"sqlstate",None)=="23505":raise HTTPException(409,"Já existe uma categoria equivalente")
            raise
    return {"ok":True}

class CategoryDelete(BaseModel):
    organizer_id:uuid.UUID

@router.post("/categories/{category_id}/delete")
async def delete_category(category_id:uuid.UUID,p:CategoryDelete,request:Request):
    require_origin(request)
    await authorized(request,p.organizer_id,"organizer.events.manage")
    async with request.app.state.pool.acquire() as conn:
      async with conn.transaction():
        cat=await conn.fetchrow("""SELECT c.id,e.status event_status FROM public.sport_categories c
           JOIN public.sport_events e ON e.id=c.event_id
           WHERE c.id=$1 AND c.organizer_id=$2 FOR UPDATE OF c""",category_id,p.organizer_id)
        if not cat:raise HTTPException(404,"Categoria não encontrada")
        if cat["event_status"] in ("closed","cancelled"):raise HTTPException(409,"Evento encerrado")
        count=await conn.fetchval("SELECT COUNT(*) FROM public.sport_entries WHERE category_id=$1",category_id)
        if count:raise HTTPException(409,"Categoria com inscrições não pode ser excluída. Remaneje os atletas primeiro.")
        await conn.execute("DELETE FROM public.sport_categories WHERE id=$1 AND organizer_id=$2",category_id,p.organizer_id)
    return {"ok":True}

class CategorySync(BaseModel):
    organizer_id:uuid.UUID

@router.post("/events/{event_id}/sync-categories")
async def sync_event_categories(event_id:uuid.UUID,p:CategorySync,request:Request):
    require_origin(request)
    await authorized(request,p.organizer_id,"organizer.events.manage")
    async with request.app.state.pool.acquire() as conn:
      async with conn.transaction():
        event=await conn.fetchrow("""SELECT * FROM public.sport_events
            WHERE id=$1 AND organizer_id=$2 FOR UPDATE""",event_id,p.organizer_id)
        if not event:raise HTTPException(404,"Evento não encontrado")
        if event["status"] in ("closed","cancelled"):raise HTTPException(409,"Evento encerrado")
        modalities=[m for m,enabled in (("gi",event["has_gi"]),("nogi",event["has_nogi"])) if enabled]
        created=await build_default_categories(conn,p.organizer_id,event_id,event["event_date"].year,modalities,event["has_absolute"])
    return {"created":created,"message":"Categorias ausentes adicionadas sem modificar inscrições existentes"}

@router.get("/eligible-categories/{organizer_id}/{event_id}/{athlete_id}")
async def eligible_categories(organizer_id:uuid.UUID,event_id:uuid.UUID,athlete_id:uuid.UUID,request:Request):
    await authorized(request,organizer_id,"organizer.events.read")
    pool=request.app.state.pool
    athlete=await pool.fetchrow("""SELECT birth_date,belt,weight_grams,sex FROM public.sport_athletes
        WHERE id=$1 AND organizer_id=$2""",athlete_id,organizer_id)
    if not athlete:raise HTTPException(404,"Atleta não encontrado")
    rows=await pool.fetch("""SELECT c.id::text,c.name,c.belt,c.sex,c.modality,c.is_absolute,
      c.min_weight_grams,c.max_weight_grams,c.min_birth_year,c.max_birth_year
      FROM public.sport_categories c
      WHERE c.organizer_id=$1 AND c.event_id=$2 AND c.sex=$3
        AND lower(c.belt)=lower($4)
        AND $5::int BETWEEN c.min_birth_year AND c.max_birth_year
        AND $6::int BETWEEN c.min_weight_grams AND c.max_weight_grams
        AND NOT EXISTS(SELECT 1 FROM public.sport_entries e WHERE e.athlete_id=$7 AND e.category_id=c.id AND e.payment_status<>'cancelled')
      ORDER BY c.modality,c.is_absolute,c.max_weight_grams,c.name LIMIT 500
    """,organizer_id,event_id,athlete["sex"],athlete["belt"],athlete["birth_date"].year,athlete["weight_grams"],athlete_id)
    return {"items":[dict(x) for x in rows]}

class EntryChange(BaseModel):
    organizer_id:uuid.UUID
    category_id:uuid.UUID
    base_cents:int=Field(ge=0,le=100000000)

class EntryCancel(BaseModel):
    organizer_id:uuid.UUID

@router.patch("/entries/{entry_id}")
async def edit_entry(entry_id:uuid.UUID,p:EntryChange,request:Request):
    require_origin(request)
    user=await authorized(request,p.organizer_id,"organizer.registrations.manage")
    async with request.app.state.pool.acquire() as conn:
      async with conn.transaction():
        entry=await conn.fetchrow("""SELECT e.*,v.status event_status FROM public.sport_entries e
          JOIN public.sport_events v ON v.id=e.event_id
          WHERE e.id=$1 AND e.organizer_id=$2 FOR UPDATE OF e""",entry_id,p.organizer_id)
        if not entry:raise HTTPException(404,"Inscrição não encontrada")
        if entry["payment_status"]!="pending":raise HTTPException(409,"Inscrição com pagamento confirmado ou cancelada exige revisão financeira; edição bloqueada")
        if entry["event_status"] in ("closed","cancelled"):raise HTTPException(409,"Campeonato encerrado")
        athlete=await conn.fetchrow("SELECT birth_date,belt,weight_grams,sex FROM public.sport_athletes WHERE id=$1 AND organizer_id=$2",entry["athlete_id"],p.organizer_id)
        cat=await conn.fetchrow("""SELECT belt,sex,min_weight_grams,max_weight_grams,min_birth_year,max_birth_year
          FROM public.sport_categories WHERE id=$1 AND event_id=$2 AND organizer_id=$3""",p.category_id,entry["event_id"],p.organizer_id)
        if not cat:raise HTTPException(404,"Categoria não encontrada neste evento")
        if not athlete or not athlete["sex"] or athlete["sex"]!=cat["sex"] or athlete["belt"].casefold()!=cat["belt"].casefold() or not(cat["min_weight_grams"]<=athlete["weight_grams"]<=cat["max_weight_grams"]) or not(cat["min_birth_year"]<=athlete["birth_date"].year<=cat["max_birth_year"]):
            raise HTTPException(422,"Categoria incompatível com sexo, faixa, idade ou peso do atleta")
        try:
            await conn.execute("UPDATE public.sport_entries SET category_id=$1,base_cents=$2 WHERE id=$3 AND organizer_id=$4",p.category_id,p.base_cents,entry_id,p.organizer_id)
        except Exception as e:
            if getattr(e,"sqlstate",None)=="23505":raise HTTPException(409,"Atleta já possui inscrição nesta categoria")
            raise
        await conn.execute("""INSERT INTO public.finance_audit(organizer_id,actor_user_id,action,reference_id)
          VALUES($1,$2,$3,$4)""",p.organizer_id,user.user_id,
          "sport_entry_edited:"+str(entry["category_id"])+":"+str(entry["base_cents"])+"->"+str(p.category_id)+":"+str(p.base_cents),entry_id)
    return {"ok":True}

@router.post("/entries/{entry_id}/cancel")
async def cancel_entry(entry_id:uuid.UUID,p:EntryCancel,request:Request):
    require_origin(request)
    user=await authorized(request,p.organizer_id,"organizer.registrations.manage")
    async with request.app.state.pool.acquire() as conn:
      async with conn.transaction():
        entry=await conn.fetchrow("SELECT payment_status FROM public.sport_entries WHERE id=$1 AND organizer_id=$2 FOR UPDATE",entry_id,p.organizer_id)
        if not entry:raise HTTPException(404,"Inscrição não encontrada")
        if entry["payment_status"]=="cancelled":raise HTTPException(409,"Inscrição já cancelada")
        if entry["payment_status"]!="pending":raise HTTPException(409,"Pagamento já confirmado. É necessária revisão financeira antes do cancelamento")
        await conn.execute("""UPDATE public.sport_entries SET payment_status='cancelled',eligible=false WHERE id=$1 AND organizer_id=$2""",entry_id,p.organizer_id)
        await conn.execute("""INSERT INTO public.finance_audit(organizer_id,actor_user_id,action,reference_id)
          VALUES($1,$2,'sport_entry_cancelled', $3)""",p.organizer_id,user.user_id,entry_id)
    return {"ok":True}
