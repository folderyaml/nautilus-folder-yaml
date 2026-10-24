# nautilus-folder-yaml 项目指南

nautilus(GNOME Files)的 Python 插件:让文件夹用 `.folder.yaml` 描述自己。**纯插件,不改 nautilus C 代码。**

本文件是项目规则的唯一权威。Claude Code 读 `.claude/CLAUDE.md`,Codex 读 `.codex/AGENTS.md`,两者均为指向本文件的引用。

## 开工前必读(按顺序)

1. `docs/requirements.md` — 原始需求(短而笼统)
2. `docs/research.md` — 技术调研:已验证机制 / 死路清单 / 架构决策(全部有源码依据)
3. `docs/pitfalls.md` — 踩坑记录(避免重复踩)
4. `docs/CHANGELOG.md` — 版本日志与当前进度
5. `docs/design/` — 功能设计文档(`desc` / `file-desc`)

## 操作 `.folder.yaml` 之前(必做)

给文件夹加描述、给文件加注释 —— **动手前先加载 `skills/folder-yaml/SKILL.md`**。格式与操作规则都在那里;本文只留指针,不重复其内容(避免两处规则漂移)。

该 skill 也可装给任意 agent:`npx skills add folderyaml/nautilus-folder-yaml --skill folder-yaml -g`。

## 当前状态

纯 nautilus-python 插件,装进系统自带 nautilus 即可用,不需要构建、不需要 fork 二进制。

已上线功能(实现细节见各自设计文档):

- **文件夹描述**:`.folder.yaml` 的 `desc` 显示在图标视图副标题与列表视图「描述」列;右键「修改描述」编辑
- **文件注释**:`.folder.yaml` 的 `file-desc` 给文件夹内的文件加注释,显示位置同描述;右键文件「修改注释」编辑。注释跟着文件走(重命名/移动自动跟随,见 `docs/design/file-desc.md`)
- **显示开关**:空白处右键「隐藏描述 / 显示描述」,即时生效

版本与逐条进度以 `docs/CHANGELOG.md` 为准。

## 已定决策(除非用户明确改变,不要推翻)

1. **显示名覆盖钩子已否决**(2026-08-17)——描述用 caption 第二行方案:真名在上、描述在下。不要重新提议"替换显示名"
2. **纯插件,不改 nautilus C 代码**(2026-10-23 定):新功能只在 nautilus-python 现有扩展点(InfoProvider / MenuProvider / ColumnProvider / PropertyPageProvider)内实现;够不到就放弃,不为单个功能维护 fork
3. `.folder.yaml` 是文件夹元数据文件:文件夹内 dotfile(随文件夹移动、工具无关),顶层键 `desc`(字符串)、`file-desc`(映射:文件名 → 注释)。**改名记录(2026-09-24)**:原名 `.project.yaml`,因用途是通用文件夹元数据而非项目专用、且 `.project.yaml` 与 MuleSoft PDK 的文件重名,改为 `.folder.yaml`
4. **归档 / 分组视图 / history-paths 已删除**(2026-10-23):`.folder.yaml` 里残留的 `archived`、`history-paths` 键插件不读也不写,写入时原样保留
5. 扩展文件名 `nautilus-meta.py`(2026-09-25):菜单 ID(`FolderMeta::*`)、配置目录 `~/.config/nautilus-meta/`、类名同步;同日「中文名」概念整体改称「描述」`desc`
6. **列表视图列宽/字号靠运行时改 GTK 控件**(2026-10-24):`Nautilus.Column` 没有宽度属性,插件在进程内调 `Gtk.ColumnView` 的列。依赖 nautilus 内部结构,上游改动时静默退化为原样

## 开发约定

- **开工铁律:开发任何功能前,必须先读完「开工前必读」的全部文档**,确认已验证的机制与死路后再动手
- **插件**:改 `extensions/python/nautilus-meta/`;`./install.sh` 装到 `~/.local/share/nautilus-python/extensions/` 后 `nautilus -q` 重启生效;错误输出在 nautilus stderr
- **提权**:一律用 `pkexec`;**禁用 sudo/su/doas**;pkexec 失败就停下问用户
- **提交前必跑**:`python3 -m unittest discover -s extensions/python/nautilus-meta -p 'test_*.py'`、`git diff --check`
- 新功能先写设计文档(`docs/design/`)再动代码
- 环境:nautilus 51.x + nautilus-python 4.1,GI 版本号 `4.1`,依赖 PyYAML

## 每个开发任务的验收环节(必做)

任何插件改动完成后,装到用户目录并打开 `dev-demo/` 人工验收:

1. **单测**:`python3 -m unittest discover -s extensions/python/nautilus-meta -p 'test_*.py'`
2. **安装**:`./install.sh`(复制插件到用户扩展目录并重启 nautilus)
3. **打开**:`nautilus dev-demo`
4. **验收内容**:`dev-demo/` 含 `alpha-project`(有 desc)、`beta-project`(desc + file-desc)、`gamma-project`(仅 file-desc)、`plain-dir`(无 yaml)、`notes.txt`(普通文件);图标视图检查描述副标题,列表视图右键列头勾选「描述」列检查注释;右键「修改描述 / 修改注释」可用;没有归档相关菜单项
5. 验收后如无遗留需求可退出窗口,不强制清理

## 安装

- `./install.sh` — 复制插件到 `~/.local/share/nautilus-python/extensions/` 并 `nautilus -q`;不需要构建、不需要 pkexec
- 系统级安装(可选):复制到 `/usr/share/nautilus-python/extensions/`;两份同存会双菜单(`docs/pitfalls.md` #4),装系统副本后删用户副本
