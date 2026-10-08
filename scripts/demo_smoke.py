"""End-to-end MCP transcript against a live local server."""
from __future__ import annotations
import json, os, sys
import httpx

BASE=os.getenv("SAFE_ACTION_BASE_URL","http://127.0.0.1:8765"); rid=0
def rpc(method,params=None,initialized=True):
    global rid; rid+=1
    h={"Origin":BASE,"Accept":"application/json, text/event-stream"}
    if initialized:h["MCP-Protocol-Version"]="2025-11-25"
    r=httpx.post(BASE+"/mcp",headers=h,json={"jsonrpc":"2.0","id":rid,"method":method,"params":params or {}},timeout=5); r.raise_for_status(); return r.json()
def main():
    a={"provider":"Northstar Home Care","service":"Heating inspection","date":"2026-10-20","time":"14:30","quoted_price":89.0,"currency":"USD","service_location_label":"Home"}
    init=rpc("initialize",{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}},False)
    tools=rpc("tools/list"); prepared=rpc("tools/call",{"name":"hold_service_appointment","arguments":a,"_demo":{"mode":"prepare"}}); w=prepared["result"]["structuredContent"]["workflow_id"]
    rpc("tools/call",{"name":"hold_service_appointment","arguments":a,"_demo":{"mode":"approve","workflow_id":w}})
    changed={**a,"quoted_price":129.0}; rejected=rpc("tools/call",{"name":"hold_service_appointment","arguments":changed,"_demo":{"mode":"execute","workflow_id":w}})
    crashed=rpc("tools/call",{"name":"hold_service_appointment","arguments":a,"_demo":{"mode":"crash","workflow_id":w}})
    replayed=rpc("tools/call",{"name":"hold_service_appointment","arguments":a,"_demo":{"mode":"replay","workflow_id":w}})
    assert init["result"]["protocolVersion"]=="2025-11-25" and tools["result"]["tools"][0]["name"]=="hold_service_appointment"
    assert rejected["result"]["structuredContent"]["status"]=="REJECTED" and crashed["result"]["structuredContent"]["status"]=="CRASH_INJECTED"
    assert replayed["result"]["structuredContent"]["workflow"]["terminal"] is True
    print(json.dumps({"status":"PASS","workflow_id":w,"receipt":replayed["result"]["structuredContent"]["receipt"]["receipt_id"],"external_side_effects":0},indent=2))
if __name__=="__main__": main()
