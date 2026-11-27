# -*- coding: utf-8 -*-
"""v8 立即派发 + 追踪（国债期货 / cn 数据链）"""
import io, json, sys, time, urllib.request, urllib.error

TOK = io.open(r"C:/Users/Administrator/.workbuddy/v8_gh_token.txt", encoding="utf-8").read().strip()
REPO = "ah-quant999/quant-scanner-v8"
API = "https://api.github.com"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOK)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "v8-hotfix")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, {"message": e.read()[:200].decode("utf-8", "replace")}


def dispatch(wf, inputs=None):
    body = {"ref": "main"}
    if inputs:
        body["inputs"] = inputs
    st, r = call("POST", "/repos/%s/actions/workflows/%s/dispatches" % (REPO, wf), body)
    print("派发 %-42s HTTP %s %s" % (wf, st, r.get("message", "")))
    return st in (204, 201, 200)


def latest(wf):
    st, d = call("GET", "/repos/%s/actions/workflows/%s/runs?per_page=3" % (REPO, wf))
    if st != 200 or not d.get("workflow_runs"):
        return None
    return d["workflow_runs"][0]


if __name__ == "__main__":
    wf = sys.argv[1]
    inputs = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    want = sys.argv[3] if len(sys.argv) > 3 else "track"
    if want == "dispatch":
        dispatch(wf, inputs)
        sys.exit(0)
    r = latest(wf)
    if not r:
        print("查不到 run"); sys.exit(1)
    print("%s | %s/%s | %s UTC | id=%s" % (r["name"][:40], r["status"], r["conclusion"], r["created_at"], r["id"]))
