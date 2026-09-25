---
name: hermes-workspace-layout
description: 搞清楚 Hermes / Hermes One 里「工作区」到底指什么——三层结构（上下文文件夹 Context Folder / Profile 配置档 / Project 项目）、各自的存储位置与 GUI 入口、hermes project 全套命令、以及同名「Projects」的混淆陷阱。当任务是「Hermes 工作区怎么用」「Hermes One 项目/文件夹怎么配」「hermes project 命令」「会话怎么分组」「工作目录不生效」时使用。
agent_created: true
---

# Hermes 工作区：三层结构

**一句话**：Hermes 里「工作区」不是一个东西，是三层。绝大多数困惑都源于把层与层搞混。

排查前先定位用户问的是哪一层，别默认是某一层就开干。

## 三层速查

| 层 | 名字 | GUI 入口 | 存储 | 隔离范围 |
|---|---|---|---|---|
| ① | **上下文文件夹** Context Folder | 聊天框 `Choose Folder` 芯片 | `state.db` → 表 `desktop_session_context_folders` | 单个会话的工作目录 |
| ② | **Profile 配置档** | 侧边栏 Profiles 页 | `~/.hermes/`（default）／`~/.hermes/profiles/<名>/` | 整套：config / 记忆 / 技能 / 会话 / 插件 |
| ③ | **Project 项目** | ⚠️ 无 GUI 界面，仅 CLI | `~/.hermes/projects.db` | 命名式多文件夹工作区，给看板 / worktree 用 |

## ⚠️ 最大的陷阱：两个「Projects」

**GUI 侧边栏那个叫 `Projects` 的分区，读的是 ①（会话的 contextFolder 分组），不是 ③。**
用 `hermes project create` 建的东西**不会**出现在侧边栏 —— Hermes One 这个版本没有消费
`projects.db` 的界面（`projects.*` RPC 挂在 tui_gateway 上，给 TUI / 远程客户端用）。

实测证据（v26.908.40834）：前端有 `groupSessionsByWorkspace(sessions)`，
按 `session.contextFolder` 把会话分成 `projectGroups`（有文件夹，组名取 basename）
和 `chats`（没有）两组。全程不碰 `projects.db`。

判断数据源的方法见 skill `electron-asar-inspect` 的「第 2.6 步」。

## ① 上下文文件夹（GUI 主力）

**操作**：聊天输入框上方芯片栏 → `Choose Folder` → 选目录。
芯片变成 `Context folder: <路径>`。取消选 `Remove context folder`。

**右键菜单**（侧边栏任意会话）：

| 菜单项 | 作用 |
|---|---|
| `Move to project` | 二级面板列出已有文件夹，点一个即移动，**立即写库** |
| `New folder…` | 弹系统目录选择器 |
| `Remove from project` | 清绑定，回 Chats 组（仅当前有文件夹时出现） |

**实现内幕 —— 它只是一句 system message**（源码原文）：

```
The working folder for this conversation is <路径>. When the user asks you
to read, create, modify, or run project files, use the file, terminal,
and code-execution tools with absolute paths under this folder.
```

⚠️ **是提示级引导，不是沙箱** —— 工具能访问的范围没有被真正收窄。
用户问「设了工作区是不是就限制在目录里了」→ 答案是否。

**相关**：聊天页还有文件浏览器面板（`Show file explorer`），根目录跟着 contextFolder 走。

## ② Profile 配置档

- 目录规则：`default` → `~/.hermes/` 本身；其他名 → `~/.hermes/profiles/<名>/`
- 定义原文：*"Each profile is an isolated Hermes workspace with its own config, memory, and skills"*
- **CLI 顶层没有 profile 子命令**，管理入口只在 GUI 的 Profiles 页
- 查当前 profile：
  ```python
  from hermes_cli.profiles import list_profiles, get_active_profile_name
  print(get_active_profile_name())        # default
  ```

## ③ Project 项目（CLI）

定义原文：*"human-named workspaces that can span multiple folders / repos. They anchor
desktop session grouping and, when bound to a kanban board, give tasks a deterministic
worktree + branch convention. State is per-profile."*

```bash
hermes project create "名字" /path/a /path/b   # 第一个路径 = primary
hermes project list [--all]                    # --all 含归档
hermes project show <id|slug>
hermes project add-folder <id> /path/c
hermes project remove-folder <id> /path/c
hermes project set-primary <id> /path/c        # 路径须已在项目内
hermes project rename <id> "新名"
hermes project use <id>                        # ⚠️ 不带参数 = 清除，不是查看
hermes project archive <id> / restore <id>
hermes project bind-board <id> <看板slug>
```

**数据模型**（`~/.hermes/projects.db`）：

```
projects          id / slug / name / board_slug / primary_path / created_at / archived
project_folders   project_id / path / label / is_primary / added_at
project_meta      key / value
discovered_repos  root / label / last_seen
```

**侧边栏三级树**（GUI + TUI 网关的 build_tree）：

| 层级 | 来源 | 特点 |
|---|---|---|
| Tier 1 显式项目 | `hermes project create` | 永远显示，即使 0 会话 |
| Tier 2 自动项目 | 从剩余会话的 cwd 推断 | 标 `isAuto` |
| Tier 3 发现仓库 | 自动扫描到的 git repo | 无会话也展示 |

节点下再分 repo → lane（分支 / 看板工作树）→ 会话。

**仓库自动发现配置**（`desktop.*`）：

| 键（短 / 长） | 默认 |
|---|---|
| `enabled` / `repo_scan_enabled` | `true` |
| `roots` / `repo_scan_roots` | `[]` |
| `exclude_paths` / `repo_scan_exclude_paths` | `[]` |

永不成为工作区的目录：`/`、家目录本身、家目录的上级、`~/.hermes` 下任何路径。

## 坑位清单（均实测）

1. **`hermes project use` 不带参数 = 清除活动项目**，不是查看。想看当前用 `list` / `show`。
   实测输出：`Cleared active project`。
2. **纯中文项目名 → slug 变成 `project` / `project-2`**。slug 取名字里的 ASCII，
   纯中文没有就回退。不冲突但难认，建议名字带英文或显式 `--slug junqi`。
3. **别把上下级目录同时加进一个项目**（如 `/a` 和 `/a/b`），树里会出现嵌套 repo，语义混乱。
   多文件夹是给**平级**的多个 repo 用的。
4. **上下文文件夹不是沙箱**（见 ①）。
5. **两个 Projects 同名**（见上）。

## 快速侦察（不用翻源码）

```bash
hermes project list --all                    # 项目
hermes config get desktop.repo_scan_enabled  # 发现开关

# 会话 → 文件夹绑定
python3 -c "
import sqlite3; c=sqlite3.connect('$HOME/.hermes/state.db')
print(c.execute('select count(*) from desktop_session_context_folders').fetchone())"

# 直接读 projects.db
python3 -c "
import sqlite3; c=sqlite3.connect('$HOME/.hermes/projects.db')
for r in c.execute('select id,slug,name,primary_path,archived from projects'): print(r)"
```

**注意**：项目状态是 **per-profile** 的。`~/.hermes/projects.db` 是 default profile 的；
换了 profile 要看 `~/.hermes/profiles/<名>/projects.db`。
