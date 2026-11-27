# -*- coding: utf-8 -*-
"""v8 净室推送 #2：部署白名单补国债期货链。以**实时** tip 为 base，force=false。"""
import base64, hashlib, io, json, urllib.request, urllib.error

TOK = io.open(r"C:/Users/Administrator/.workbuddy/v8_gh_token.txt", encoding="utf-8").read().strip()
REPO = "ah-quant999/quant-scanner-v8"
API = "https://api.github.com"
PATH = ".github/workflows/v8_build_deploy.yml"
LOCAL = "_tmp/deploy_remote.yml"


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
        return e.code, {"message": e.read()[:300].decode("utf-8", "replace")}


st, ref = call("GET", "/repos/%s/git/ref/heads/main" % REPO)
assert st == 200, (st, ref)
tip = ref["object"]["sha"]
st, cm = call("GET", "/repos/%s/git/commits/%s" % (REPO, tip))
base_tree = cm["tree"]["sha"]
print("实时 tip = %s" % tip[:10])

raw = io.open(LOCAL, "rb").read()
assert b"\r\n" not in raw, "含 CRLF"
st, b = call("POST", "/repos/%s/git/blobs" % REPO,
             {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
assert st == 201, (st, b)
h = hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()
assert h == b["sha"], "blob 不自洽"
print("blob %s %dB" % (b["sha"][:10], len(raw)))

st, t = call("POST", "/repos/%s/git/trees" % REPO,
             {"base_tree": base_tree, "tree": [{"path": PATH, "mode": "100644", "type": "blob", "sha": b["sha"]}]})
assert st == 201, (st, t)

msg = ("fix(v8-Pages): 部署白名单补「🏦 v8 国债期货利率罗盘 refresh (cn)」\n\n"
       "主人令「盘中高频开始了，实时这两个还是旧数据 = 最高优先级」根因之二。\n"
       "实测：仓库内 data/BOND_FUTURES.js 已是 2026-11-27 09:52 的新数据（run 45925009277 已推），\n"
       "但 Pages 仍显示昨日 15:15 —— 因为本链不在 workflow_run 白名单 ⇒ 推送后不触发构建部署，\n"
       "只能等别的白名单链顺带把 data/ 带上去（与 11-16 期指卡断更同型）。\n"
       "补名后本链一结束即自动构建部署，闭环。")
st, c = call("POST", "/repos/%s/git/commits" % REPO, {"message": msg, "tree": t["sha"], "parents": [tip]})
assert st == 201, (st, c)
st, r = call("PATCH", "/repos/%s/git/refs/heads/main" % REPO, {"sha": c["sha"], "force": False})
assert st == 200, (st, r)
print("✅ main → %s" % r["object"]["sha"][:10])

st, d = call("GET", "/repos/%s/contents/%s?ref=main" % (REPO, PATH))
remote = base64.b64decode(d["content"])
print("  远端==本地 %s" % (remote == raw))
assert remote == raw
