#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""I 补丁（collidefix）：撞名时**不盲删** —— 加一道 CAS 校验，杜绝「静默回滚」。

背景（2026-09-26 23:33 MEMORY.md 事故的**真正机理**）
====================================================
B+（metafix）为消灭 `(1)` 撞名产物，在撞名分支做了「先删后传」：

    self.delete_by_name(expect, dir_key)      # 删掉远端同名文件
    return self.upload(...)                   # 再传一次

**这条路在并发写下是破坏性的** —— 它删掉的可能是对端刚传上来的新版：

    23:33:04  Mac  上传 MEMORY.md = 9811          云端 = 9811（真实数据上传，非秒传）
    23:33:05  对端 上传 → 返回 MEMORY(1).md ⇒ 撞名（说明它这一刻的列表里没有该条目）
    23:33:06  对端 「先删后传」⇒ **删掉了 Mac 的 9811**
    23:33:08  对端 上传 MEMORY.md (9 KB) [秒传]   ← 9 KB = 9038，即**它的本地旧版**
    23:33:21  Mac  list 到 9038 ⇒ F 补丁判冲突 ✅（判定正确，保住了 9811 副本）
    23:33:22  Mac  **真下载到 9038 字节实体** ⇒ 云端内容确实被换过，不是元数据幻觉

⇒ 「秒传」在这里是**帮凶**：它按内容哈希从对象池复活旧内容，
  于是「先删后传」不再是「可见的 (1) 垃圾」，而升级成**静默回滚**。

对端曾把这个 9038 归因为「秒传返回的目录项元数据残留」。**不成立**：
① 它自己的日志写的是 `上传 MEMORY.md (9 KB)` —— 本地 size 由 `lp.stat()` 得出，
   9811 会打成 `10 KB`，**9 KB 只能是 9038**（`%.0f` 四舍五入）；
② Mac 侧 23:33:22 的 `↓ 下载 MEMORY.md (9 KB)` 是**真字节**，且 `expect_size` 校验通过。

修法
====
删之前做一次 **CAS（compare-and-swap）校验**：只有在「远端该名字下的条目
仍是本轮取列表时看到的**同一个** `file_id`」时，才允许删。

    cur = list_dir()[expect]["file_id"]
    if cur != expected_id:          # expected_id = 本轮列表里的 file_id（可能为 None）
        raise WeiyunError("撞名冲突(并发写)…")   # 不删、让位

- `expected_id is None`（本轮列表里**本来没有**这个名字）+ 现在有了 ⇒ 判为并发写 ⇒ 让位
  —— 23:33 那次正是这个形状。
- `expected_id == cur` ⇒ 名字下还是我本来就要替换的那份旧版 ⇒ 照旧「先删后传」。

让位后的走向：上传抛 `WeiyunError` ⇒ `_do_upload` 记 ERROR、**不写基线** ⇒
下一轮 `l_changed and r_changed` ⇒ 走**冲突分支**：先存本地副本再按 mtime 定赢家。
⇒ 把「静默回滚」换成「可见 + 有副本」的冲突，和 F 补丁同一套语义。

幂等：已注入则跳过。
"""
import ast
import pathlib
import shutil
import sys
import time

TARGET = pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"
STAMP = time.strftime("%Y%m%d")
MARKER = "COLLIDE-CAS"

R1_OLD = '''    def upload(self, path, dir_key, max_rounds=400, retry=0):'''
R1_NEW = '''    def upload(self, path, dir_key, max_rounds=400, retry=0,
               expected_id=None):'''

R2_OLD = '''            if r.get("file_exist"):
                return self._finish_named(r, p["filename"], dir_key,
                                          path, max_rounds, retry, True)'''
R2_NEW = '''            if r.get("file_exist"):
                return self._finish_named(r, p["filename"], dir_key,
                                          path, max_rounds, retry, True,
                                          expected_id=expected_id)'''

R3_OLD = '''            if int(up.get("upload_state", 0)) == 2:
                return self._finish_named(up, p["filename"], dir_key,
                                          path, max_rounds, retry, False)'''
R3_NEW = '''            if int(up.get("upload_state", 0)) == 2:
                return self._finish_named(up, p["filename"], dir_key,
                                          path, max_rounds, retry, False,
                                          expected_id=expected_id)'''

R4_OLD = '''    def _finish_named(self, resp, expect, dir_key, path,
                      max_rounds, retry, fast):
        """上传返回后校验文件名。微云撞名会静默改名为 xxx(1)。

        被改名 ⇒ 回删撞名产物 + 清目录内同名旧版 + 重传一次。
        """'''
R4_NEW = '''    def _finish_named(self, resp, expect, dir_key, path,
                      max_rounds, retry, fast, expected_id=None):
        """上传返回后校验文件名。微云撞名会静默改名为 xxx(1)。

        被改名 ⇒ 回删撞名产物 + **CAS 校验** + 清目录内同名旧版 + 重传一次。

        --- COLLIDE-CAS (I patch 20260926) ---
        「先删后传」必须过 CAS：只有远端该名字下仍是本轮列表看到的同一个
        file_id 时才删。否则说明**对端期间写过这个名字**，盲删会删掉它的新版，
        而本机若命中秒传会从对象池把旧内容复活 ⇒ **静默回滚**（见 patch 文档）。
        """'''

R5_OLD = '''        if retry < 1:
            self.delete_by_name(expect, dir_key)
            return self.upload(path, dir_key, max_rounds,
                               retry=retry + 1)
        raise WeiyunError("撞名重试后仍失败: %s" % got)'''
R5_NEW = '''        if retry < 1:
            # --- COLLIDE-CAS (I patch 20260926) ---
            # 删之前先确认「远端该名字下还是我本轮看到的那一份」。
            # expected_id is None ⇒ 本轮列表里本来没这个名字，现在却撞名 ⇒ 并发写。
            try:
                ex = self.list_dir(dir_key).get(expect)
            except WeiyunError as e:
                log("撞名 CAS 校验时 list 失败: %s" % e, "WARN")
                ex = None
            if ex is not None:
                cur = ex.get("file_id")
                if cur != expected_id:
                    raise WeiyunError(
                        "撞名冲突(并发写)：远端 %s 已被对端改写"
                        "（本轮已知 id=%s，现在 id=%s，远端 %s B）"
                        " ⇒ 不删远端，让位给对端"
                        % (expect, expected_id, cur, ex.get("file_size")))
            self.delete_by_name(expect, dir_key)
            return self.upload(path, dir_key, max_rounds,
                               retry=retry + 1, expected_id=expected_id)
        raise WeiyunError("撞名重试后仍失败: %s" % got)'''

R6_OLD = '''        fid, fast = client.upload(str(lp), rkey)'''
R6_NEW = '''        fid, fast = client.upload(
            str(lp), rkey, expected_id=(existing or {}).get("file_id"))'''

REPLACEMENTS = [
    ("R1 upload 签名", R1_OLD, R1_NEW),
    ("R2 秒传分支", R2_OLD, R2_NEW),
    ("R3 分片完成分支", R3_OLD, R3_NEW),
    ("R4 _finish_named 签名+docstring", R4_OLD, R4_NEW),
    ("R5 撞名 CAS 校验", R5_OLD, R5_NEW),
    ("R6 _do_upload 传 expected_id", R6_OLD, R6_NEW),
]


def main():
    if not TARGET.exists():
        print("ERROR: 找不到 %s" % TARGET)
        return 1
    src = TARGET.read_text(encoding="utf-8", newline="")
    if MARKER in src:
        print("已打过 I 补丁（%s 存在），跳过。" % MARKER)
        return 0

    out = src
    for name, old, new in REPLACEMENTS:
        n = out.count(old)
        print("锚点 %-28s 命中 %d 次" % (name, n))
        if n != 1:
            print("ERROR: 锚点必须恰好 1 次，中止以免误改")
            return 1
        out = out.replace(old, new, 1)

    out += "\n\n# --- %s (I patch %s) ---\n" % (MARKER, STAMP)

    try:
        ast.parse(out)
    except SyntaxError as e:
        print("ERROR: 补丁后语法错误 %s，放弃写入" % e)
        return 1

    bak = TARGET.with_name(TARGET.name + ".bak_pre_collidefix_" + STAMP)
    if not bak.exists():
        shutil.copy2(TARGET, bak)
        print("已备份 → %s" % bak.name)

    tmp = TARGET.with_suffix(".py.tmp")
    tmp.write_text(out, encoding="utf-8", newline="\n")
    tmp.replace(TARGET)
    print("✅ I 补丁完成：%d → %d B" % (len(src.encode()), len(out.encode())))
    print("   语法校验通过；备份 %s" % bak.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
