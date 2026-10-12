#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_metafix.py —— B+ 修法：秒传分支撞名收尾

问题：
    WeiyunClient.upload() 命中 file_exist（秒传）时提前 return，
    绕过了 _do_upload 的「先删后传」。而微云遇同名文件会静默改名为 xxx(1)，
    _check_name 只打告警、不补救 ⇒ (1) 条目永久留在云端并污染两端。

修法：
    抽出 _finish_named()：上传返回后校验 filename。
    被改名 ⇒ ① 用返回的 file_id 回删撞名产物 ② 按名清掉目录内同名旧版
    ③ 重走一次 upload（此时目录无同名，可正常落地）。递归深度限 1 层。
    秒传分支与正常完成分支（upload_state==2）都改走这个收尾。

特性：幂等（已打则跳过）、自动备份、语法校验、失败回滚。
"""

import ast
import pathlib
import shutil
import sys
import time

TARGET = pathlib.Path.home() / ".junqi-sync" / "junqi_sync.py"

MARKER = "_finish_named"

REPLACEMENTS = [
    (
        # 1) 秒传分支：不再提前 return
        '            if r.get("file_exist"):\n'
        '                _check_name(r, p["filename"])\n'
        '                return r.get("file_id", ""), True',
        '            if r.get("file_exist"):\n'
        '                return self._finish_named(r, p["filename"], dir_key,\n'
        '                                          path, max_rounds, retry, True)',
    ),
    (
        # 2) 正常分片完成分支：同样收尾
        '            if int(up.get("upload_state", 0)) == 2:\n'
        '                _check_name(up, p["filename"])\n'
        '                return up.get("file_id", ""), False',
        '            if int(up.get("upload_state", 0)) == 2:\n'
        '                return self._finish_named(up, p["filename"], dir_key,\n'
        '                                          path, max_rounds, retry, False)',
    ),
    (
        # 3) upload 增加 retry 参数
        "    def upload(self, path, dir_key, max_rounds=400):",
        "    def upload(self, path, dir_key, max_rounds=400, retry=0):",
    ),
    (
        # 4) 注入两个新方法（插在 delete_file 之前）
        "    def delete_file(self, file_id, dir_key):",
        '    def _finish_named(self, resp, expect, dir_key, path,\n'
        '                      max_rounds, retry, fast):\n'
        '        """上传返回后校验文件名。微云撞名会静默改名为 xxx(1)。\n'
        '\n'
        '        被改名 ⇒ 回删撞名产物 + 清目录内同名旧版 + 重传一次。\n'
        '        """\n'
        '        got, fid = resp.get("filename"), resp.get("file_id", "")\n'
        '        if not got or got == expect:\n'
        '            return fid, fast\n'
        '        log("⚠ 微云把文件名改成了 %s（期望 %s）→ 回删并重试"\n'
        '            % (got, expect), "WARN")\n'
        '        try:\n'
        '            if fid:\n'
        '                self.delete_file(fid, dir_key)\n'
        '        except WeiyunError as e:\n'
        '            log("回删撞名条目失败: %s" % e, "WARN")\n'
        '        if retry < 1:\n'
        '            self.delete_by_name(expect, dir_key)\n'
        '            return self.upload(path, dir_key, max_rounds,\n'
        '                               retry=retry + 1)\n'
        '        raise WeiyunError("撞名重试后仍失败: %s" % got)\n'
        '\n'
        '    def delete_by_name(self, filename, dir_key):\n'
        '        """按名删除远端同名文件（清同名旧版用）。返回删除个数。"""\n'
        '        rmap = self.list_dir(dir_key)\n'
        '        it = rmap.get(filename)\n'
        '        if not it:\n'
        '            return 0\n'
        '        self.delete_file(it["file_id"], dir_key)\n'
        '        return 1\n'
        '\n'
        '    def delete_file(self, file_id, dir_key):',
    ),
]


def main():
    if not TARGET.exists():
        print("❌ 找不到 %s" % TARGET)
        return 1

    src = TARGET.read_text(encoding="utf-8", newline="")

    # 幂等：已打则跳过
    if MARKER in src:
        print("ℹ️  补丁已存在（检测到 %s），跳过。" % MARKER)
        return 0

    # 预检：所有锚点都在
    missing = [old.strip().splitlines()[0] for old, _ in REPLACEMENTS
               if old not in src]
    if missing:
        print("❌ 锚点缺失，脚本可能已被改动：")
        for m in missing:
            print("     %s" % m)
        return 1

    # 备份
    bak = TARGET.with_name(
        TARGET.name + ".bak_pre_metafix_" + time.strftime("%Y%m%d"))
    shutil.copy2(str(TARGET), str(bak))
    print("已备份 → %s" % bak.name)

    # 替换
    out = src
    for old, new in REPLACEMENTS:
        out = out.replace(old, new, 1)

    # 语法校验（WorkBuddy 环境会拦 __pycache__ 写入，故用 ast.parse 纯内存校验）
    try:
        ast.parse(out)
    except SyntaxError as e:
        print("❌ 替换后语法错误，已回滚：%s" % e)
        return 1

    TARGET.write_text(out, encoding="utf-8", newline="\n")
    print("✅ 打补丁成功，语法校验通过。")
    print("   文件：%d B → %d B" % (len(src.encode("utf-8")),
                                   len(out.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
