# nautilus-folder-yaml 项目指南

nautilus(GNOME Files)的 Python 插件:让文件夹用 `.folder.yaml` 描述自己。**纯插件,不改 nautilus C 代码。**

本文件是项目规则的唯一权威。Claude Code 读 `.claude/CLAUDE.md`,Codex 读 `.codex/AGENTS.md`,两者均为指向本文件的引用。

## 开工前必读(按顺序)

1. `docs/design.md` — 需求、`.folder.yaml` 格式、已验证机制、死路、决策
2. `docs/pitfalls.md` — 踩坑记录(避免重复踩)
3. `docs/CHANGELOG.md` — 版本日志与当前进度

## 操作 `.folder.yaml` 之前(必做)

给文件夹或文件加描述 —— **动手前先加载 `folder-yaml` skill**。格式与操作规则都在那里;本文只留指针。

skill 独立分发在 `folderyaml/skills` 仓库:

```bash
npx skills add folderyaml/skills --skill folder-yaml -g
```

## 当前状态

纯 nautilus-python 插件,装进系统自带 nautilus 即可用,不需要构建、不需要 fork 二进制。

- **描述**:`.folder.yaml` 的 `desc`(文件夹)与 `file-desc`(文件夹内文件)显示在图标视图副标题与列表视图「描述」列;右键「修改描述」编辑
- **跟随**:文件描述靠 xattr 令牌在重命名/移动后自动跟随
- **显示开关**:空白处右键「隐藏描述 / 显示描述」,即时生效
- **双语**:中文环境用中文,其余用英文,英文里统一叫 `desc`
- **分发**:pacman 私有源(GitHub Pages),`pkexec pacman -Syu nautilus-folder-yaml`

版本与逐条进度以 `docs/CHANGELOG.md` 为准。

## 已定决策(除非用户明确改变,不要推翻)

1. **显示名覆盖钩子已否决**(2026-08-17)——描述用 caption 第二行:真名在上、描述在下
2. **纯插件,不改 nautilus C 代码**(2026-10-23):只在现有扩展点(InfoProvider / MenuProvider / ColumnProvider / PropertyPageProvider)内实现;够不到就放弃
3. `.folder.yaml` 是文件夹元数据文件:文件夹内 dotfile(随文件夹移动、工具无关),顶层键 `desc`(字符串)、`file-desc`(映射:文件名 → 描述)
4. **归档 / 分组视图 / history-paths 已删除**(2026-10-23):残留键不读也不写,写入时原样保留
5. **名称统一为 nautilus-folder-yaml**(2026-10-24):文件名、菜单 ID(`NautilusFolderYaml::*`)、配置目录 `~/.config/nautilus-folder-yaml/`、xattr `user.nautilus-folder-yaml.desc`、类名。旧的 `nautilus-meta` 字样一律不出现
6. **文件夹和文件都叫「描述」**(2026-10-24):英文界面叫 `desc`;不再有「注释」这个说法
7. **YAML 用 ruamel.yaml round-trip**(2026-10-24):保留注释/键序/引号/flow 风格;依赖 `python-ruamel-yaml`
8. **列表视图列宽/字号靠运行时改 GTK 控件**(2026-10-24):`Nautilus.Column` 没有宽度属性;依赖 nautilus 内部结构,上游改动时静默退化为原样
9. **分发走自建 pacman 源**(2026-10-24):GitHub Pages + `repo-add`,不做 AUR、不做 GPG 签名

## 开发约定

- **开工铁律:开发任何功能前,必须先读完「开工前必读」的全部文档**,确认已验证的机制与死路后再动手
- 改 `nautilus-folder-yaml.py`;`./install.sh` 装到 `~/.local/share/nautilus-python/extensions/` 后 `nautilus -q` 生效;错误输出在 nautilus stderr
- **提权**:一律用 `pkexec`;**禁用 sudo/su/doas**;pkexec 失败就停下问用户
- **提交前必跑**:`python3 -m unittest discover -s tests`、`git diff --check`
- 新功能先改 `docs/design.md` 再动代码
- 环境:nautilus 51.x + nautilus-python 4.x,GI 版本号 `4.1`,依赖 `python-ruamel-yaml`

## 每个开发任务的验收环节(必做)

1. **单测**:`python3 -m unittest discover -s tests`
2. **安装**:`./install.sh`(复制插件到用户扩展目录并重启 nautilus)
3. **打开**:`nautilus dev-demo`
4. **验收**:`dev-demo/` 含 `alpha-project`(有 desc)、`beta-project`(desc + file-desc)、`gamma-project`(仅 file-desc)、`plain-dir`(无 yaml)、`notes.txt`(普通文件);图标视图看描述副标题,列表视图右键列头勾「描述」列看文件描述;右键「修改描述」可用;空白处「隐藏/显示描述」可切换;没有归档相关菜单项
5. **英文界面**:`LANG=en_US.UTF-8 nautilus -q && LANG=en_US.UTF-8 nautilus dev-demo`,菜单与列标题应为 `desc` / `Edit desc`

## 安装与分发

- 开发:`./install.sh` — 复制到用户扩展目录并重启 nautilus;不需要构建、不需要 pkexec
- 正式:`PKGBUILD` 装到 `/usr/share/nautilus-python/extensions/`,依赖 `nautilus-python python-ruamel-yaml`
- 两份同存会双菜单(`docs/pitfalls.md` #3);包脚本会把用户副本改名成 `*.disabled`
- 发版:改 `PKGBUILD` 的 `pkgver` 与 CHANGELOG → 提交 → `git tag v0.5.0 && git push --tags`,CI 打包并发布到 Pages
