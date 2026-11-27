# -*- coding: utf-8 -*-
"""v8 盘中链路体检：今天(11-27)哪些 workflow 跑了/失败/没跑。不打印 token。"""
import io, json, datetime, urllib.request, urllib.error

TOK = io.open(r"C:/Users/Administrator/.workbuddy/v8_gh_token.txt", encoding="utf-8").read().strip()
REPO = "ah-quant999/quant-scanner-v8"
API = "https://api.github.com"


def call(path):
    req = urllib.request.Request(API + path)
    req.add_header("Authorization", "Bearer " + TOK)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "v8-check")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read()[:300].decode("utf-8", "replace")}


# 今天北京时间 00:00 起的 run（UTC 11-26T16:00 之后）
since = datetime.datetime(2026, 11, 26, 16, 0, 0)
rows = []
for page in (1, 2, 3):
    d = call("/repos/%s/actions/runs?per_page=100&page=%d" % (REPO, page))
    if "workflow_runs" not in d:
        print("ERR", d); break
    hit_old = False
    for r in d["workflow_runs"]:
        t = datetime.datetime.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        if t < since:
            hit_old = True
            break
        rows.append((t, r))
    if hit_old:
        break

print("今日(北京时间 11-27 00:00 起) v8 运行数：%d\n" % len(rows))
print("%-46s %-9s %-9s %s" % ("workflow", "状态", "结论", "北京时间"))
for t, r in sorted(rows, key=lambda x: x[0], reverse=True)[:45]:
    bj = t + datetime.timedelta(hours=8)
    print("%-46s %-9s %-9s %s" % (r["name"][:44], r["status"], str(r["conclusion"])[:9], bj.strftime("%H:%M:%S")))

# 关注的 workflow 最后一次运行
print("\n=== 关键链路最后运行 ===")
for key in ("bond_futures", "intraday_precise", "cn_fetch", "lemoncat", "sentinel"):
    d = call("/repos/%s/actions/workflows" % REPO)
    break
wfs = call("/repos/%s/actions/workflows?per_page=100" % REPO)
for w in (wfs.get("workflows") or []):
    p = (w.get("path") or "")
    if any(k in p for k in ("bond_futures", "precise", "cn_fetch", "lemoncat", "sentinel")):
        print("  %-58s state=%s" % (p, w.get("state")))
