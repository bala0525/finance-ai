"""In-memory stand-in for the Supabase Storage REST API (test use only).

It mimics the endpoints the backend calls: object upload/download/delete, signed
URL creation + retrieval, and bucket get/create, including the service-role
authorisation check and Supabase-style error codes. It is NOT Supabase; results
from tests against it prove the backend's behaviour, not live connectivity.
"""

import secrets
from urllib.parse import unquote

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

SERVICE_KEY = "test-service-role-key"

app = FastAPI()
STATE = {"objects": {}, "buckets": {"test-bucket": {"public": False}}, "tokens": {}, "fail": None, "calls": []}


def _auth(authorization: str | None, apikey: str | None):
    if authorization != f"Bearer {SERVICE_KEY}" or apikey != SERVICE_KEY:
        raise HTTPException(status_code=401, detail="Invalid JWT")


def _maybe_fail():
    if STATE["fail"]:
        return JSONResponse({"message": "injected failure"}, status_code=STATE["fail"])
    return None


@app.post("/storage/v1/object/sign/{bucket}/{path:path}")
async def sign(bucket: str, path: str, authorization: str | None = Header(None), apikey: str | None = Header(None)):
    _auth(authorization, apikey)
    if (bucket, path) not in STATE["objects"]:
        return JSONResponse({"error": "not_found", "message": "Object not found"}, status_code=400)
    token = secrets.token_urlsafe(16)
    STATE["tokens"][token] = (bucket, path)
    return {"signedURL": f"/object/sign/{bucket}/{path}?token={token}"}


@app.get("/storage/v1/object/sign/{bucket}/{path:path}")
async def signed_get(bucket: str, path: str, token: str):
    if STATE["tokens"].get(token) != (bucket, unquote(path)):
        return JSONResponse({"message": "bad token"}, status_code=400)
    return Response(STATE["objects"][(bucket, path)]["data"])


@app.post("/storage/v1/object/{bucket}/{path:path}")
async def upload(bucket: str, path: str, request: Request, authorization: str | None = Header(None), apikey: str | None = Header(None)):
    _auth(authorization, apikey)
    failed = _maybe_fail()
    if failed:
        return failed
    if bucket not in STATE["buckets"]:
        return JSONResponse({"message": "Bucket not found"}, status_code=404)
    if (bucket, path) in STATE["objects"] and request.headers.get("x-upsert") != "true":
        return JSONResponse({"message": "The resource already exists"}, status_code=409)
    STATE["objects"][(bucket, path)] = {"data": await request.body(), "type": request.headers.get("content-type")}
    STATE["calls"].append(("upload", path))
    return {"Key": f"{bucket}/{path}"}


@app.get("/storage/v1/object/{bucket}/{path:path}")
async def download(bucket: str, path: str, authorization: str | None = Header(None), apikey: str | None = Header(None)):
    _auth(authorization, apikey)
    failed = _maybe_fail()
    if failed:
        return failed
    obj = STATE["objects"].get((bucket, path))
    if obj is None:
        return JSONResponse({"statusCode": "404", "error": "not_found", "message": "Object not found"}, status_code=400)
    return Response(obj["data"], media_type=obj["type"])


@app.delete("/storage/v1/object/{bucket}")
async def delete(bucket: str, request: Request, authorization: str | None = Header(None), apikey: str | None = Header(None)):
    _auth(authorization, apikey)
    failed = _maybe_fail()
    if failed:
        return failed
    body = await request.json()
    for prefix in body["prefixes"]:
        STATE["objects"].pop((bucket, prefix), None)
        STATE["calls"].append(("delete", prefix))
    return []


@app.get("/storage/v1/bucket/{bucket}")
async def get_bucket(bucket: str, authorization: str | None = Header(None), apikey: str | None = Header(None)):
    _auth(authorization, apikey)
    if bucket not in STATE["buckets"]:
        return JSONResponse({"message": "Bucket not found"}, status_code=404)
    return {"id": bucket, **STATE["buckets"][bucket]}


@app.post("/storage/v1/bucket")
async def create_bucket(request: Request, authorization: str | None = Header(None), apikey: str | None = Header(None)):
    _auth(authorization, apikey)
    body = await request.json()
    STATE["buckets"][body["id"]] = {"public": body.get("public", False)}
    return {"name": body["id"]}
