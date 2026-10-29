import json, sys
name, n = sys.argv[1], int(sys.argv[2])
item = {"name": "Dana Cohen", "phone": "052-123-4567", "email": "dana@example.com", "note": "call me tomorrow"}
body = json.dumps({"leads": [item] * n})
open(f"post_{name}.lua", "w").write(
    'wrk.method = "POST"\n'
    'wrk.headers["Content-Type"] = "application/json"\n'
    'wrk.body = [==[' + body + ']==]\n')
print(f"Generated post_{name}.lua ({len(body)} bytes)")
