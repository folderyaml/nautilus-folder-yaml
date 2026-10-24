# nautilus-folder-yaml

让 GNOME Files(nautilus)读 `.folder.yaml`:文件夹可以给自己写描述,文件可以有注释,原文件名和路径完全不变。

纯 nautilus-python 插件 —— 不修改 nautilus 源码,不需要构建,装一个 `.py` 文件即可。

## 效果

- **图标视图**:描述显示在文件夹名下方的第二行
- **列表视图**:右键列头勾选「描述」列,描述紧贴名称列,字号比正文略小
- **文件注释**:`.folder.yaml` 的 `file-desc` 给文件夹内的文件加注释,位置同描述;重命名/移动后自动跟随
- **右键编辑**:「修改描述」/「修改注释」;空白处右键「显示描述 / 隐藏描述」总开关

## 安装

```bash
./install.sh
```

复制插件到 `~/.local/share/nautilus-python/extensions/` 并重启 nautilus。需要 `nautilus-python` 和 `python-yaml`:

```bash
pkexec pacman -S nautilus-python python-yaml    # Arch
# Debian/Ubuntu: sudo apt install nautilus-python python3-yaml
```

## `.folder.yaml` 格式

放在文件夹里,跟着文件夹走:

```yaml
desc: 我的项目
file-desc:
  notes.txt: 会议记录
```

两个键都可选。完整规则见 `skills/folder-yaml/SKILL.md`。

## 开发

```bash
python3 -m unittest discover -s extensions/python/nautilus-meta -p 'test_*.py'
./install.sh
nautilus dev-demo
```

项目规则与验收流程见 `AGENTS.md`;技术调研、踩坑、设计文档在 `docs/`。

## 结构

```
├── AGENTS.md                  # 项目规则(唯一权威)
├── install.sh                 # 安装到用户扩展目录
├── extensions/python/nautilus-meta/
│   ├── nautilus-meta.py       # 插件本体
│   └── test_nautilus_meta.py  # 单测
├── skills/folder-yaml/        # 给 agent 的技能包
├── docs/                      # 需求、调研、踩坑、设计、版本日志
└── dev-demo/                  # 手工验收夹具
```
