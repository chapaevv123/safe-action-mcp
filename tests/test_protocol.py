def rpc(client,method,rid=1,params=None,headers=None): return client.post("/mcp",json={"jsonrpc":"2.0","id":rid,"method":method,"params":params or {}},headers=headers or {})
def test_initialize(client):
    r=rpc(client,"initialize",params={"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"1"}}); assert r.status_code==200 and r.json()["result"]["protocolVersion"]=="2025-11-25" and r.headers["mcp-session-id"]
def test_initialized_notification(client,headers): assert client.post("/mcp",json={"jsonrpc":"2.0","method":"notifications/initialized"},headers=headers).status_code==202
def test_tools_list(client,headers): assert rpc(client,"tools/list",headers=headers).json()["result"]["tools"][0]["name"]=="hold_service_appointment"
def test_wrong_method(client,headers): assert rpc(client,"nope",headers=headers).json()["error"]["code"]==-32601
def test_missing_id(client,headers): assert client.post("/mcp",json={"jsonrpc":"2.0","method":"tools/list"},headers=headers).json()["error"]["code"]==-32600
def test_missing_protocol_header(client): assert rpc(client,"tools/list").json()["error"]["code"]==-32600
def test_bad_origin(client,headers): assert rpc(client,"tools/list",headers={**headers,"Origin":"https://evil.example"}).status_code==403
def test_malformed_json(client): assert client.post("/mcp",content="{",headers={"content-type":"application/json"}).json()["error"]["code"]==-32700
def test_wrong_tool(client,headers): assert rpc(client,"tools/call",params={"name":"danger","arguments":{}},headers=headers).json()["error"]["code"]==-32602
def test_malformed_tool_schema(client,headers): assert rpc(client,"tools/call",params={"name":"hold_service_appointment","arguments":{"provider":"x"}},headers=headers).json()["error"]["code"]==-32602
def test_get_mcp_is_405(client): assert client.get("/mcp").status_code==405
def test_ui_smoke(client): assert "SIMULATED ALEXA+ MCP EXPERIENCE" in client.get("/").text and client.get("/app.js").status_code==200
