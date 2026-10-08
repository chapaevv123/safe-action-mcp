def rpc(client,method,rid=1,params=None,headers=None,notification=False):
    body={"jsonrpc":"2.0","method":method,"params":params or {}}
    if not notification: body["id"]=rid
    return client.post("/mcp",json=body,headers=headers or {})

def initialize(client):
    r=rpc(client,"initialize",params={"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"1"}})
    sid=r.headers["mcp-session-id"]
    headers={"Origin":"http://127.0.0.1:8765","MCP-Protocol-Version":"2025-11-25","Mcp-Session-Id":sid}
    assert rpc(client,"notifications/initialized",headers=headers,notification=True).status_code==202
    return r,headers

def test_initialize(client):
    r,h=initialize(client); assert r.json()["result"]["protocolVersion"]=="2025-11-25" and len(r.headers["mcp-session-id"])>32
def test_session_ids_non_predictable(client):
    a,_=initialize(client); b,_=initialize(client); assert a.headers["mcp-session-id"]!=b.headers["mcp-session-id"]
def test_tools_list_valid_initialized_session(client):
    _,h=initialize(client); assert rpc(client,"tools/list",headers=h).json()["result"]["tools"][0]["name"]=="hold_service_appointment"
def test_tools_list_before_initialize_rejected(client,headers): assert rpc(client,"tools/list",headers=headers).json()["error"]["code"]==-32001
def test_tools_call_before_initialize_rejected(client,headers): assert rpc(client,"tools/call",params={"name":"hold_service_appointment","arguments":{}},headers=headers).json()["error"]["code"]==-32001
def test_invalid_session_rejected(client,headers): assert rpc(client,"tools/list",headers={**headers,"Mcp-Session-Id":"invalid"}).json()["error"]["code"]==-32001
def test_not_initialized_session_rejected(client):
    r=rpc(client,"initialize",params={"protocolVersion":"2025-11-25"}); h={"MCP-Protocol-Version":"2025-11-25","Mcp-Session-Id":r.headers["mcp-session-id"]}; assert rpc(client,"tools/list",headers=h).json()["error"]["code"]==-32002
def test_wrong_method(client):
    _,h=initialize(client); assert rpc(client,"nope",headers=h).json()["error"]["code"]==-32601
def test_missing_id(client):
    _,h=initialize(client); assert rpc(client,"tools/list",headers=h,notification=True).json()["error"]["code"]==-32600
def test_missing_protocol_header(client): assert rpc(client,"tools/list").json()["error"]["code"]==-32600
def test_bad_origin(client,headers): assert rpc(client,"tools/list",headers={**headers,"Origin":"https://evil.example"}).status_code==403
def test_malformed_json(client): assert client.post("/mcp",content="{",headers={"content-type":"application/json"}).json()["error"]["code"]==-32700
def test_wrong_tool(client):
    _,h=initialize(client); assert rpc(client,"tools/call",params={"name":"danger","arguments":{}},headers=h).json()["error"]["code"]==-32602
def test_malformed_tool_schema(client):
    _,h=initialize(client); assert rpc(client,"tools/call",params={"name":"hold_service_appointment","arguments":{"provider":"x"}},headers=h).json()["error"]["code"]==-32602
def test_get_mcp_is_405(client): assert client.get("/mcp").status_code==405
def test_ui_smoke(client): assert "SIMULATED ALEXA+ MCP EXPERIENCE" in client.get("/").text and "Mcp-Session-Id" in client.get("/app.js").text
