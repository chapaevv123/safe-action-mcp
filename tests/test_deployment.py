from pathlib import Path

ROOT=Path(__file__).parents[1]
ARGS={"provider":"Northstar Home Care","service":"Heating inspection","date":"2026-10-20","time":"14:30","quoted_price":89.0,"currency":"USD","service_location_label":"Home"}

def initialized(client):
    r=client.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"deployment-test","version":"1"}}})
    sid=r.headers["mcp-session-id"]; h={"Origin":"http://127.0.0.1:8765","MCP-Protocol-Version":"2025-11-25","Mcp-Session-Id":sid}
    client.post("/mcp",headers=h,json={"jsonrpc":"2.0","method":"notifications/initialized","params":{}})
    return sid,h

def call(client,h,rid,mode,workflow=None):
    demo={"mode":mode}
    if workflow: demo["workflow_id"]=workflow
    return client.post("/mcp",headers=h,json={"jsonrpc":"2.0","id":rid,"method":"tools/call","params":{"name":"hold_service_appointment","arguments":ARGS,"_demo":demo}}).json()["result"]["structuredContent"]

def test_health_is_safe(client): assert client.get("/health").json()=={"status":"ok","protocol":"2025-11-25","external_side_effects":0}

def test_session_owned_reset(client):
    sid,h=initialized(client); prepared=call(client,h,2,"prepare"); workflow=prepared["workflow_id"]; call(client,h,3,"approve",workflow); call(client,h,4,"execute",workflow)
    r=client.post(f"/demo/reset/{workflow}",headers={"Origin":"http://127.0.0.1:8765","Mcp-Session-Id":sid})
    assert r.status_code==200 and r.json()["removed"]["holds"]==1 and r.json()["status"]=="RESET"

def test_cross_session_reset_rejected(client):
    sid,h=initialized(client); workflow=call(client,h,2,"prepare")["workflow_id"]; other,_=initialized(client)
    assert client.post(f"/demo/reset/{workflow}",headers={"Origin":"http://127.0.0.1:8765","Mcp-Session-Id":other}).status_code==403

def test_cancel_is_session_owned(client):
    sid,h=initialized(client); workflow=call(client,h,2,"prepare")["workflow_id"]; call(client,h,3,"approve",workflow); result=call(client,h,4,"execute",workflow); hold=result["result"]["hold_id"]
    other,_=initialized(client)
    assert client.post(f"/demo/cancel/{hold}",headers={"Origin":"http://127.0.0.1:8765","Mcp-Session-Id":other}).status_code==403
    assert client.post(f"/demo/cancel/{hold}",headers={"Origin":"http://127.0.0.1:8765","Mcp-Session-Id":sid}).json()["status"]=="CANCELLED"

def test_deployment_assets_and_no_invented_url():
    assert (ROOT/"Dockerfile").is_file() and (ROOT/"render.yaml").is_file()
    assert "plan: free" in (ROOT/"render.yaml").read_text(encoding="utf-8")
    assert "PUBLIC_DEMO_URL_PENDING" not in (ROOT/"client/index.html").read_text(encoding="utf-8")
