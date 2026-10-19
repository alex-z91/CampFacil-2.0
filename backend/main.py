"""MEUCAMP 2.0 — API inicial de autenticação e autorização.

Execute atrás de HTTPS e proxy reverso na mesma origem do frontend.
Não exponha credenciais DATABASE_URL ao navegador.
"""
import os
from typing import Annotated

import asyncpg
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DATABASE_URL = os.environ.get("DATABASE_URL")
NEON_AUTH_URL = os.environ.get("NEON_AUTH_URL", "").rstrip("/")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "https://meucamp.alexcoder.space")
app = FastAPI(title="MEUCAMP API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN], allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])


@app.on_event("startup")
async def start() -> None:
    if not DATABASE_URL or not NEON_AUTH_URL:
        raise RuntimeError("Configure DATABASE_URL e NEON_AUTH_URL no servidor")
    app.state.pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)


@app.on_event("shutdown")
async def shutdown() -> None:
    await app.state.pool.close()


class Identity(BaseModel):
    user_id: str
    email: str


async def authenticated(request: Request) -> Identity:
    # Validação no servidor a cada requisição. Não confie em roles enviadas pelo frontend.
    token = request.cookies.get("meucamp_session")
    cookie_name = request.cookies.get("meucamp_session_name", "better-auth.session_token")
    if cookie_name not in ("better-auth.session_token", "__Secure-better-auth.session_token"):
        raise HTTPException(401, "Sessão inválida")
    cookie = f"{cookie_name}={token}" if token else ""
    if not cookie:
        raise HTTPException(401, "Autenticação necessária")
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
        response = await client.get(f"{NEON_AUTH_URL}/get-session", headers={"cookie": cookie})
    if response.status_code != 200:
        raise HTTPException(401, "Sessão inválida")
    try:
        data = response.json()
        user = data.get("user") if isinstance(data, dict) else None
        uid = user.get("id") if isinstance(user, dict) else None
        email = user.get("email") if isinstance(user, dict) else None
    except (ValueError, AttributeError):
        raise HTTPException(401, "Sessão inválida")
    if not uid or not email:
        raise HTTPException(401, "Sessão inválida")
    return Identity(user_id=str(uid), email=str(email))


async def has_platform_role(pool, user_id: str, permission: str) -> bool:
    return bool(await pool.fetchval("""
      SELECT true FROM public.platform_access a
      JOIN public.role_permissions rp ON rp.role_key=a.role
      WHERE a.user_id=$1 AND a.enabled=true AND rp.permission_key=$2 LIMIT 1
    """, user_id, permission))


async def has_organizer_role(pool, user_id: str, organizer_id: str, permission: str) -> bool:
    return bool(await pool.fetchval("""
      SELECT true FROM public.organizer_members m
      JOIN public.organizers o ON o.id=m.organizer_id
      JOIN public.role_permissions rp ON rp.role_key=m.role
      WHERE m.user_id=$1 AND m.organizer_id=$2::uuid
        AND m.status='active' AND o.status='active'
        AND rp.permission_key=$3 LIMIT 1
    """, user_id, organizer_id, permission))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/me")
async def me(user: Annotated[Identity, Depends(authenticated)], request: Request):
    pool = request.app.state.pool
    master = await has_platform_role(pool, user.user_id, "platform.organizers.read")
    rows = await pool.fetch("""
        SELECT m.organizer_id::text AS id, o.name, m.role
        FROM public.organizer_members m JOIN public.organizers o ON o.id=m.organizer_id
        WHERE m.user_id=$1 AND m.status='active' AND o.status='active'
        ORDER BY o.name
    """, user.user_id)
    return {"email": user.email, "master": master,
            "organizations": [dict(row) for row in rows]}


@app.get("/api/platform/organizers")
async def organizers(user: Annotated[Identity, Depends(authenticated)], request: Request):
    pool = request.app.state.pool
    if not await has_platform_role(pool, user.user_id, "platform.organizers.read"):
        raise HTTPException(403, "Acesso não autorizado")
    rows = await pool.fetch("SELECT id::text, name, status, created_at FROM public.organizers ORDER BY created_at DESC LIMIT 100")
    return {"items": [dict(row) for row in rows]}


@app.get("/api/organizers/{organizer_id}/permissions")
async def organizer_permissions(organizer_id: str, user: Annotated[Identity, Depends(authenticated)], request: Request):
    pool = request.app.state.pool
    try:
        import uuid
        uuid.UUID(organizer_id)
    except ValueError:
        raise HTTPException(404, "Organização não encontrada")
    if not await has_organizer_role(pool, user.user_id, organizer_id, "organizer.events.read"):
        raise HTTPException(403, "Acesso não autorizado")
    rows = await pool.fetch("""
      SELECT rp.permission_key FROM public.organizer_members m
      JOIN public.role_permissions rp ON rp.role_key=m.role
      WHERE m.user_id=$1 AND m.organizer_id=$2::uuid AND m.status='active'
    """, user.user_id, organizer_id)
    return {"permissions": [r["permission_key"] for r in rows]}


from pydantic import EmailStr
from http.cookies import SimpleCookie


class LoginInput(BaseModel):
    email: str
    password: str
    remember: bool = True


def trusted_request(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin != FRONTEND_ORIGIN:
        raise HTTPException(403, "Origem não autorizada")


@app.post("/api/auth/login")
async def login(payload: LoginInput, request: Request, response: Response):
    trusted_request(request)
    if not payload.email or not payload.password:
        raise HTTPException(400, "E-mail e senha obrigatórios")
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=False) as client:
            result = await client.post(
                f"{NEON_AUTH_URL}/sign-in/email",
                json={"email": payload.email, "password": payload.password, "rememberMe": payload.remember},
                headers={"origin": FRONTEND_ORIGIN, "content-type": "application/json"},
            )
    except httpx.RequestError:
        raise HTTPException(503, "Serviço de autenticação temporariamente indisponível")
    if result.status_code != 200:
        raise HTTPException(401, "Credenciais inválidas ou conta ainda não habilitada")
    # O cookie de identidade permanece exclusivamente em HttpOnly; não enviamos token no JSON.
    session_token = None
    session_cookie_name = None
    for header in result.headers.get_list("set-cookie"):
        parsed = SimpleCookie()
        try:
            parsed.load(header)
        except Exception:
            continue
        for name, morsel in parsed.items():
            if name.endswith("session_token"):
                session_token = morsel.value
                session_cookie_name = name
                break
    if not session_token:
        raise HTTPException(502, "O provedor não retornou um cookie de sessão")
    response.set_cookie(
        "meucamp_session", session_token, httponly=True, secure=True,
        samesite="lax", path="/", max_age=60 * 60 * 24 * (30 if payload.remember else 1),
    )
    response.set_cookie("meucamp_session_name", session_cookie_name, httponly=True, secure=True, samesite="lax", path="/", max_age=60 * 60 * 24 * (30 if payload.remember else 1))
    # É apenas autenticação; permissões permanecem verificadas pelas rotas administrativas.
    return {"ok": True}


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    trusted_request(request)
    token = request.cookies.get("meucamp_session")
    cookie_name = request.cookies.get("meucamp_session_name", "better-auth.session_token")
    if token and cookie_name in ("better-auth.session_token", "__Secure-better-auth.session_token"):
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
                await client.post(
                    f"{NEON_AUTH_URL}/sign-out",
                    headers={"cookie": f"{cookie_name}={token}", "origin": FRONTEND_ORIGIN},
                )
        except httpx.RequestError:
            pass
    response.delete_cookie("meucamp_session", path="/", secure=True, httponly=True, samesite="lax")
    response.delete_cookie("meucamp_session_name", path="/", secure=True, httponly=True, samesite="lax")
    return {"ok": True}
