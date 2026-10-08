from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import ValidationError

from .engine import InjectedCrash, SafetyEngine
from .models import AppointmentArgs, PROTOCOL_VERSION, TOOL_NAME
from .store import LocalStore

ROOT=Path(__file__).resolve().parents[1]
DB_PATH=os.getenv("SAFE_ACTION_DB",str(ROOT/"artifacts"/"runtime"/"safe_action.db"))
ALLOWED={x.strip() for x in os.getenv("SAFE_ACTION_ALLOWED_ORIGINS","http://127.0.0.1:8765,http://localhost:8765").split(",") if x.strip()}
for public_origin in (os.getenv("SAFE_ACTION_PUBLIC_ORIGIN"),os.getenv("RENDER_EXTERNAL_URL")):
    if public_origin: ALLOWED.add(public_origin.rstrip("/"))
store=LocalStore(DB_PATH); engine=SafetyEngine(store); app=FastAPI(title="Safe Action MCP",version="1.0.0")
sessions:dict[str,bool]={}; pending:dict[str,dict[str,Any]]={}

TOOL_SCHEMA={"type":"object","additionalProperties":False,"required":["provider","service","date","time","quoted_price","currency","service_location_label"],"properties":{
 "provider":{"type":"string","minLength":2},"service":{"type":"string","minLength":2},"date":{"type":"string","pattern":"^\\d{4}-\\d{2}-\\d{2}$"},
 "time":{"type":"string","pattern":"^([01]\\d|2[0-3]):[0-5]\\d$"},"quoted_price":{"type":"number","exclusiveMinimum":0},"currency":{"type":"string","pattern":"^[A-Z]{3}$"},
 "service_location_label":{"type":"string","minLength":2},"note":{"type":"string","maxLength":300}}}

def rpc_error(rid,code,message,data=None,status=200):
    body={"jsonrpc":"2.0","id":rid,"error":{"code":code,"message":message}}
    if data is not None: body["error"]["data"]=data
    return JSONResponse(body,status_code=status)

@app.get("/")
def index(): return FileResponse(ROOT/"client"/"index.html")

@app.get("/app.js")
def javascript(): return FileResponse(ROOT/"client"/"app.js",media_type="application/javascript")

@app.get("/styles.css")
def styles(): return FileResponse(ROOT/"client"/"styles.css",media_type="text/css")

@app.get("/health")
def health(): return {"status":"ok","protocol":PROTOCOL_VERSION,"external_side_effects":0}

@app.get("/mcp")
def mcp_get(): return JSONResponse({"error":"SSE_NOT_ENABLED_USE_POST"},status_code=405)

@app.post("/mcp")
async def mcp(request:Request):
    origin=request.headers.get("origin")
    if origin and origin not in ALLOWED: return JSONResponse({"error":"ORIGIN_FORBIDDEN"},status_code=403)
    try: data=await request.json()
    except Exception: return rpc_error(None,-32700,"Parse error")
    if not isinstance(data,dict) or data.get("jsonrpc")!="2.0": return rpc_error(data.get("id") if isinstance(data,dict) else None,-32600,"Invalid Request")
    method=data.get("method"); rid=data.get("id"); params=data.get("params") or {}
    if method=="initialize":
        if rid is None: return rpc_error(None,-32600,"Request ID required")
        if params.get("protocolVersion")!=PROTOCOL_VERSION: return rpc_error(rid,-32602,"Unsupported protocol version",{"supported":[PROTOCOL_VERSION]})
        sid="mcp_"+secrets.token_urlsafe(32); sessions[sid]=False
        response=JSONResponse({"jsonrpc":"2.0","id":rid,"result":{"protocolVersion":PROTOCOL_VERSION,"capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"safe-action-mcp","version":"1.0.0"},"instructions":"All actions are local simulations and require exact owner consent."}})
        response.headers["Mcp-Session-Id"]=sid; return response
    if request.headers.get("mcp-protocol-version")!=PROTOCOL_VERSION: return rpc_error(rid,-32600,"MCP-Protocol-Version header required")
    sid=request.headers.get("mcp-session-id")
    if sid not in sessions: return rpc_error(rid,-32001,"Unknown or missing MCP session")
    if rid is None and method=="notifications/initialized": sessions[sid]=True; return Response(status_code=202)
    if rid is None: return rpc_error(None,-32600,"Request ID required")
    if not sessions[sid]: return rpc_error(rid,-32002,"MCP session not initialized")
    if method=="tools/list":
        return {"jsonrpc":"2.0","id":rid,"result":{"tools":[{"name":TOOL_NAME,"title":"Hold a simulated home-service appointment","description":"Creates one reversible local-only simulated appointment hold after safety checks and owner consent.","inputSchema":TOOL_SCHEMA,"annotations":{"destructiveHint":False,"idempotentHint":True,"openWorldHint":False}}]}}
    if method=="tools/call":
        if params.get("name")!=TOOL_NAME: return rpc_error(rid,-32602,"Unknown tool")
        try: args=AppointmentArgs.model_validate(params.get("arguments",{}))
        except ValidationError as exc: return rpc_error(rid,-32602,"Invalid tool arguments",exc.errors(include_url=False))
        mode=params.get("_demo",{}).get("mode","prepare"); key=str(params.get("_demo",{}).get("workflow_id",rid))
        try:
            if mode=="prepare":
                prepared=engine.prepare(sid,args); pending[prepared["workflow_id"]]={"session_id":sid,"args":args,**prepared}
                result={k:(v.model_dump(mode="json") if hasattr(v,"model_dump") else v) for k,v in prepared.items()}
            elif mode=="approve":
                wf=pending[key]
                if wf["session_id"] != sid: raise ValueError("CROSS_SESSION_WORKFLOW_ACCESS")
                consent,bound=engine.approve(key,sid,"demo-owner",wf["args"],wf["admission"],wf["trust"]); wf.update(consent=consent,bound=bound)
                result={"workflow_id":key,"consent":consent.model_dump(mode="json"),"bound_action":bound.model_dump(mode="json")}
            elif mode in {"execute","crash"}:
                wf=pending[key]; proposed=args
                if wf["session_id"] != sid: raise ValueError("CROSS_SESSION_WORKFLOW_ACCESS")
                from .core import materiality_diff
                diff=materiality_diff(wf["args"],proposed)
                if diff.material_changed: result={"status":"REJECTED","reason":"MATERIAL_ARGUMENTS_CHANGED","materiality_diff":diff.model_dump(mode="json")}
                else: result=engine.execute(key,proposed,wf["consent"],wf["bound"],wf["admission"],wf["trust"],inject_crash=mode=="crash")
            elif mode=="replay":
                wf=pending[key]
                if wf["session_id"] != sid: raise ValueError("CROSS_SESSION_WORKFLOW_ACCESS")
                result=engine.replay(key,wf["args"],wf["consent"],wf["bound"],wf["admission"],wf["trust"])
            else: return rpc_error(rid,-32602,"Unknown demo mode")
        except InjectedCrash: result={"status":"CRASH_INJECTED","workflow_id":key,"recoverable":True}
        except (KeyError,ValueError) as exc: result={"status":"REJECTED","reason":str(exc)}
        clean=json.loads(json.dumps(result,default=lambda x:x.model_dump(mode="json") if hasattr(x,"model_dump") else str(x)))
        return {"jsonrpc":"2.0","id":rid,"result":{"content":[{"type":"text","text":json.dumps(clean,indent=2)}],"structuredContent":clean,"isError":clean.get("status")=="REJECTED"}}
    return rpc_error(rid,-32601,"Method not found")

@app.post("/demo/cancel/{hold_id}")
def cancel(hold_id:str,request:Request):
    origin=request.headers.get("origin")
    if origin and origin not in ALLOWED: return JSONResponse({"error":"ORIGIN_FORBIDDEN"},status_code=403)
    try: workflow_id=store.hold_workflow(hold_id)
    except KeyError: return JSONResponse({"error":"HOLD_NOT_FOUND"},status_code=404)
    sid=request.headers.get("mcp-session-id"); workflow=pending.get(workflow_id)
    if not workflow or sid not in sessions or workflow.get("session_id") != sid:
        return JSONResponse({"error":"HOLD_NOT_OWNED_BY_SESSION"},status_code=403)
    return store.cancel_hold(hold_id).model_dump(mode="json")

@app.post("/demo/reset/{workflow_id}")
def reset_demo(workflow_id:str,request:Request):
    origin=request.headers.get("origin")
    if origin and origin not in ALLOWED: return JSONResponse({"error":"ORIGIN_FORBIDDEN"},status_code=403)
    sid=request.headers.get("mcp-session-id")
    workflow=pending.get(workflow_id)
    if not workflow or sid not in sessions or workflow.get("session_id") != sid:
        return JSONResponse({"error":"WORKFLOW_NOT_OWNED_BY_SESSION"},status_code=403)
    counts=store.reset_workflow(workflow_id); pending.pop(workflow_id,None)
    return {"status":"RESET","workflow_id":workflow_id,"removed":counts}

def main():
    uvicorn.run("safe_action_mcp.app:app",host=os.getenv("SAFE_ACTION_HOST","127.0.0.1"),port=int(os.getenv("PORT",os.getenv("SAFE_ACTION_PORT","8765"))),reload=False)

if __name__=="__main__": main()
