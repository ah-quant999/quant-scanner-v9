# -*- coding: utf-8 -*-
"""v8 盘中数据链抢修（净室：以远端 blob 为底打补丁）
   A. 调度器补国债期货盘中 9 档（今日该链盘中零投递 → 罗盘卡停在昨日 15:15）
   B. ws-guard 加「内容级兜底」：blob 不等但内容一致 ⇒ 行尾差异，放行
      （否则 update_v8 整批被中止 → 行业树图/平均股价/板块资金全不重建）
"""
import io

T = "_tmp/"

# ═══════════ A. 调度器：国债期货盘中 9 档 ═══════════
p = T + "sched_remote.py"
s = io.open(p, encoding="utf-8", newline="").read()
old = '''    "v8_bond_futures.yml": {
        "slots": [f"{h:02d}:{m}" for h in range(16, 20) for m in ("02", "32")],
        "fresh_window": ("16:02", "19:35"), "fresh_thresh": 35},'''
new = '''    # 🔴 2026-11-27 主人令「盘中高频开始了，实时这两个还是旧数据 = 最高优先级」（当日实证）：
    #   本链自身 cron '0,30 1-8 UTC'（北京 09:00-16:30 每 30 分）今天盘中**零投递**（schedule
    #   注册丢失老毛病），而调度器原只配盘后 16:02-19:32 ⇒ 国债期货罗盘卡盘中一直显示「昨日 15:15」。
    #   治法：把交易时段 9 档（对齐 cn_fetch 档位）收进调度器 —— 它是唯一实测可靠投递源；
    #   盘后 8 档保持原样，不动他人的减负决策。
    "v8_bond_futures.yml": {
        "slots": ["09:32", "10:02", "10:32", "11:02", "13:02", "13:32", "14:02", "14:32", "15:02"]
                 + [f"{h:02d}:{m}" for h in range(16, 20) for m in ("02", "32")],
        "fresh_window": ("09:32", "19:35"), "fresh_thresh": 35},'''
assert s.count(old) == 1, "调度器 bond 段未唯一命中"
s = s.replace(old, new)
assert s.count('"09:32", "10:02"') == 2, "盘中档位应出现 2 处（cn_fetch + bond），实际 %d" % s.count('"09:32", "10:02"')
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("A ✅ 调度器已补国债期货盘中 9 档")

# ═══════════ B. ws-guard：内容级兜底 ═══════════
p = T + "guard_remote.py"
g = io.open(p, encoding="utf-8", newline="").read()

# B1. 新增 helper（放在 __main__ 之前）
anchor = 'if __name__ == "__main__":'
assert g.count(anchor) == 1, "__main__ 锚点未唯一命中"
helper = '''def _content_equal(ref, rel, repo):
    """内容级兜底比对：工作区 vs 目标 ref 的**内容**（归一化行尾与行尾空白后逐字节比）。

    🔴 2026-11-27 主人令「盘中数据不能停」根因修复（当日实证）：
      `.github/scripts/v8_stage_gate.py` 在 `git checkout` / `-f` / `reset --hard` 三连之后
      仍被判 blob 不一致 ⇒ 守卫 exit 1 ⇒ update_v8 整批中止 ⇒ data/*.js 全部不重建
      （现场：行业树图停在昨日 15:16、平均股价停在 11-19、板块资金整链冻结，而 raw_data
      其实已抓到 09:37 的新数据 —— 抓到了却发不出去）。
      blob 不等 **不等于代码落后**：Windows 上 core.autocrlf / 文件锁 / stat-cache 都能让
      归一化后的内容一致而原始字节不同。故加此兜底：内容一致即放行；内容真不同照旧 exit 1。
    """
    rc, out, _ = _run(["git", "-C", repo, "show", f"{ref}:{rel}"])
    if rc != 0:
        return False
    wp = os.path.join(repo, rel.replace("/", os.sep))
    try:
        with open(wp, "rb") as f:
            wb = f.read()
    except OSError:
        return False

    def _norm(b):
        b = b.replace(b"\\r\\n", b"\\n").replace(b"\\r", b"\\n")
        return b"\\n".join(ln.rstrip() for ln in b.split(b"\\n")).strip()

    return _norm(wb) == _norm(out)


'''
g = g.replace(anchor, helper + anchor)

# B2. 终救段：打印 reset 结果 + 内容级兜底
old2 = '''    print(f"  🔴 逐项拉齐仍有 {len(still)} 个不齐：{still} → 整仓 git reset --hard {ref}")
    _run(["git", "-C", repo, "reset", "--hard", ref])
    still2 = [r for r in mism
              if _blob_of(ref, r, repo) != _worktree_blob(r, repo)]
    if still2:
        print(f"  🔴 硬重置后仍不一致 {still2} → exit 1")
        return 1
    print(f"[ws-guard] ✅ 硬重置后整仓一致；原不一致文件备份在 {bak}")
    return 0'''
new2 = '''    print(f"  🔴 逐项拉齐仍有 {len(still)} 个不齐：{still} → 整仓 git reset --hard {ref}")
    _rc, _out, _err = _run(["git", "-C", repo, "reset", "--hard", ref])
    if _rc != 0:
        # 🔴 2026-11-27：原代码忽略 rc/stderr ⇒ reset 失败时只报「硬重置后仍不一致」，
        #   看不出是 reset 本身失败（文件锁/索引锁）还是内容真落后。现显式留痕。
        print(f"    ⚠️ git reset --hard 返回 {_rc}："
              f"{_err.decode('utf-8', 'replace').strip()[:300]}")
    still2 = [r for r in mism
              if _blob_of(ref, r, repo) != _worktree_blob(r, repo)]
    if still2:
        # 🔴 2026-11-27 一劳永逸：blob 不等 ≠ 代码落后。走内容级兜底，一致即放行（见 _content_equal）。
        still3 = []
        for rel in still2:
            if _content_equal(ref, rel, repo):
                print(f"    ✅ 内容级一致（仅行尾/编码差异）→ 放行 {rel}")
            else:
                still3.append(rel)
        if still3:
            print(f"  🔴 硬重置后**内容**仍不一致 {still3} → exit 1（真·代码落后，不放过）")
            return 1
        print(f"[ws-guard] ✅ 硬重置后内容全部一致（个别文件仅行尾差异，已放行）；"
              f"原不一致文件备份在 {bak}")
        return 0
    print(f"[ws-guard] ✅ 硬重置后整仓一致；原不一致文件备份在 {bak}")
    return 0'''
assert g.count(old2) == 1, "guard 终救段未唯一命中"
g = g.replace(old2, new2)
assert g.count("_content_equal") == 3, "helper 调用数异常 %d" % g.count("_content_equal")
io.open(p, "w", encoding="utf-8", newline="").write(g)
print("B ✅ ws-guard 已加内容级兜底")

# ═══════════ 语法自检 ═══════════
import py_compile
for f in (T + "sched_remote.py", T + "guard_remote.py"):
    py_compile.compile(f, doraise=True)
print("✅ 两个补丁文件语法通过")
