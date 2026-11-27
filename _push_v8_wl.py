# -*- coding: utf-8 -*-
"""v8 白名单补链（CRLF 保全版）：该 yml blob 本身是 CRLF 主导，插入行必须随原行尾。
   从远端取**原始字节**为底，按原行 EOL 插入，计数守恒断言，再净室推送。"""
import base64, hashlib, io, json, re, urllib.request, urllib.error

TOK = io.open(r"C:/Users/Administrator/.workbuddy/v8_gh_token.txt", encoding="utf-8").read().strip()
REPO = "ah-quant999/quant-scanner-v8"
API = "https://api.github.com"
PATH = ".github/workflows/v8_build_deploy.yml"


def call(method, path, body=None, raw_accept=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOK)
    req.add_header("Accept", "application/vnd.github.raw" if raw_accept else "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "v8-hotfix")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return r.status, (b if raw_accept else (json.loads(b) if b else {}))
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]


st, raw = call("GET", "/repos/%s/contents/%s?ref=main" % (REPO, PATH), raw_accept=True)
assert st == 200, (st, raw[:200])
print("远端原文件 %d B  CRLF=%d LF=%d" % (len(raw), raw.count(b"\r\n"), raw.count(b"\n")))

marker = '      - "📈 v8 期指实时 refresh (cn)"'.encode("utf-8")
i = raw.find(marker)
assert i >= 0, "期指白名单行未找到"
j = i + len(marker)
eol = b"\r\n" if raw[j:j + 2] == b"\r\n" else b"\n"
print("该行 EOL = %r" % eol)

add_lines = [
    "      # 🛡 2026-11-27 主人令「盘中高频开始了，实时这两个还是旧数据」根因之二：",
    "      #   国债期货产物推送后**不在白名单** ⇒ workflow_run 不触发 ⇒ Pages 的 BOND_FUTURES.js 恒旧",
    "      #   （实测：仓库内已是 2026-11-27 09:52 的新数据，Pages 仍显示昨日 15:15）。",
    "      #   补名后本链一跑完即自动构建部署，不再等别的链顺带把 data/ 带上去。",
    '      - "🏦 v8 国债期货利率罗盘 refresh (cn)"',
]
add = b"".join(l.encode("utf-8") + eol for l in add_lines)

crlf0, lf0 = raw.count(b"\r\n"), raw.count(b"\n")
patched = raw[:j] + eol + add + raw[j + len(eol):]
assert patched.count(b"\r\n") == crlf0 + (5 if eol == b"\r\n" else 0), "CRLF 计数不守恒"
assert patched.count(b"\n") == lf0 + 5, "LF 计数不守恒"
assert patched.count('国债期货利率罗盘 refresh'.encode()) == 1
# 原内容必须完整保留（除插入点外逐字节等同）
assert patched.replace(add, b"") == raw, "除插入外有其它字节变动"
print("插入 5 行后 %d B（CRLF=%d LF=%d）" % (len(patched), patched.count(b"\r\n"), patched.count(b"\n")))

st, ref = call("GET", "/repos/%s/git/ref/heads/main" % REPO)
tip = ref["object"]["sha"]
st, cm = call("GET", "/repos/%s/git/commits/%s" % (REPO, tip))
base_tree = cm["tree"]["sha"]
print("实时 tip = %s" % tip[:10])

st, b = call("POST", "/repos/%s/git/blobs" % REPO,
             {"content": base64.b64encode(patched).decode(), "encoding": "base64"})
assert st == 201, (st, b)
h = hashlib.sha1(b"blob %d\0" % len(patched) + patched).hexdigest()
assert h == b["sha"], "blob 不自洽"
st, t = call("POST", "/repos/%s/git/trees" % REPO,
             {"base_tree": base_tree, "tree": [{"path": PATH, "mode": "100644", "type": "blob", "sha": b["sha"]}]})
assert st == 201, (st, t)

msg = ("fix(v8-Pages): 部署白名单补「🏦 v8 国债期货利率罗盘 refresh (cn)」\n\n"
       "主人令「盘中高频开始了，实时这两个还是旧数据 = 最高优先级」根因之二。\n"
       "实测：仓库内 data/BOND_FUTURES.js 已是 2026-11-27 09:52 新数据（run 45925009277 已推），\n"
       "但 Pages 仍显示昨日 15:15 —— 本链不在 workflow_run 白名单 ⇒ 推送后不触发构建部署，\n"
       "只能等别的白名单链顺带把 data/ 带上去（与 11-16 期指卡断更同型）。补名即闭环。\n"
       "行尾保全：该 yml blob 为 CRLF 主导，插入行随原行尾，计数守恒断言通过。")
st, c = call("POST", "/repos/%s/git/commits" % REPO, {"message": msg, "tree": t["sha"], "parents": [tip]})
assert st == 201, (st, c)
st, r = call("PATCH", "/repos/%s/git/refs/heads/main" % REPO, {"sha": c["sha"], "force": False})
assert st == 200, (st, r)
print("✅ main → %s" % r["object"]["sha"][:10])

st, back = call("GET", "/repos/%s/contents/%s?ref=main" % (REPO, PATH), raw_accept=True)
print("  回读==本地 %s" % (back == patched))
assert back == patched
