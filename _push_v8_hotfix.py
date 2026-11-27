# -*- coding: utf-8 -*-
"""v8 净室推送：以远端 tip 为 base，仅提交 2 个抢修文件（force=false，非快进即失败）"""
import base64, io, json, os, sys, urllib.request, urllib.error

TOK = io.open(r"C:/Users/Administrator/.workbuddy/v8_gh_token.txt", encoding="utf-8").read().strip()
REPO = "ah-quant999/quant-scanner-v8"
API = "https://api.github.com"
FILES = {
    "v8_ws_sync_guard.py": "_tmp/guard_remote.py",
    ".github/scripts/v8_intraday_precise_sched.py": "_tmp/sched_remote.py",
}


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


# 1. 远端 tip
st, ref = call("GET", "/repos/%s/git/ref/heads/main" % REPO)
assert st == 200, (st, ref)
tip = ref["object"]["sha"]
st, cm = call("GET", "/repos/%s/git/commits/%s" % (REPO, tip))
assert st == 200, (st, cm)
base_tree = cm["tree"]["sha"]
print("远端 tip = %s  tree = %s" % (tip[:10], base_tree[:10]))

# 2. blob
entries = []
for path, local in FILES.items():
    raw = io.open(local, "rb").read()
    assert b"\r\n" not in raw, "%s 含 CRLF（应为纯 LF）" % path
    st, b = call("POST", "/repos/%s/git/blobs" % REPO,
                 {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
    assert st == 201, (st, b)
    # 本地自证
    import hashlib
    h = hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()
    assert h == b["sha"], "blob sha 不自洽 %s" % path
    entries.append({"path": path, "mode": "100644", "type": "blob", "sha": b["sha"]})
    print("  blob %-46s %6dB sha=%s" % (path, len(raw), b["sha"][:10]))

# 3. tree
st, t = call("POST", "/repos/%s/git/trees" % REPO, {"base_tree": base_tree, "tree": entries})
assert st == 201, (st, t)

# 4. commit
msg = ("fix(v8-盘中): 国债期货盘中零投递 + ws-guard 误中止整批重建 两处抢修\n\n"
       "主人令「盘中高频开始了，实时这两个还是旧数据 = 最高优先级」。\n\n"
       "根因1 国债期货：自身 cron '0,30 1-8 UTC' 今日盘中零投递（schedule 注册丢失），\n"
       "  调度器只配盘后 16:02-19:32 ⇒ 罗盘卡停在昨日 15:15。\n"
       "  ⇒ 调度器补交易时段 9 档（09:32..15:02，对齐 cn_fetch），盘后 8 档不动。\n\n"
       "根因2 行业树图/平均股价等整批不重建：cn_fetch 跑批里 ws-guard 判\n"
       "  .github/scripts/v8_stage_gate.py 不一致 → exit 1 → update_v8 中止，\n"
       "  而 raw_data 其实已抓到 09:37 新数据（抓到却发不出去）。\n"
       "  ⇒ 终救段加「内容级兜底」：归一化行尾后内容一致即放行；内容真不同照旧 exit 1。\n"
       "  ⇒ 同时把 git reset --hard 的 rc/stderr 显式打出（原忽略 ⇒ 看不出是否 reset 失败）。")
st, c = call("POST", "/repos/%s/git/commits" % REPO,
             {"message": msg, "tree": t["sha"], "parents": [tip]})
assert st == 201, (st, c)
print("新 commit = %s" % c["sha"])

# 5. 非快进拒绝
st, r = call("PATCH", "/repos/%s/git/refs/heads/main" % REPO,
             {"sha": c["sha"], "force": False})
assert st == 200, (st, r)
print("✅ 已更新 main → %s" % r["object"]["sha"][:10])

# 6. 回读自证
for path in FILES:
    st, d = call("GET", "/repos/%s/contents/%s?ref=main" % (REPO, path))
    assert st == 200, (st, d)
    remote = base64.b64decode(d["content"])
    local = io.open(FILES[path], "rb").read()
    print("  %-46s 远端==本地 %s" % (path, remote == local))
    assert remote == local
print("ALL OK")
