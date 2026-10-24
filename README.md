# nautilus-folder-yaml

让 GNOME Files(nautilus)读 `.folder.yaml`:文件夹和文件都能给自己写一行描述,磁盘上的真名和路径完全不变。

纯 nautilus-python 插件,不改 nautilus 源码,不需要构建。

## 安装(Arch)

```
# /etc/pacman.conf 末尾
[folderyaml]
SigLevel = Optional TrustAll
Server = https://folderyaml.github.io/nautilus-folder-yaml/$arch
```

```bash
pkexec pacman -Syu nautilus-folder-yaml
nautilus -q          # 或重新登录
```

## 效果

- **图标视图**:描述显示在名称下方的第二行
- **列表视图**:右键列头勾选「描述」列,描述紧贴名称列,字号比正文略小
- **右键编辑**:文件夹与文件都是「修改描述」;空白处右键「隐藏描述 / 显示描述」总开关
- **文件描述跟随**:在 nautilus 里重命名或移动文件,描述跟着走

## `.folder.yaml`

放在文件夹里,跟着文件夹走:

```yaml
desc: 我的项目
file-desc:
  notes.txt: 会议记录
```

两个键都可选。中文界面叫「描述」,其他语言叫 `desc`。
写入保留注释、键序与引号。

## 开发

```bash
pkexec pacman -S python-ruamel-yaml
python3 -m unittest discover -s tests
./install.sh            # 复制到 ~/.local/share/nautilus-python/extensions/
nautilus dev-demo
```

打包:`makepkg -f`。发版:推 `v*` tag,CI 打包并发布到 GitHub Pages。

项目规则见 `AGENTS.md`;设计、踩坑、版本日志在 `docs/`。

## 结构

```
├── nautilus-folder-yaml.py       # 插件本体
├── tests/                        # 单测(fake_gi.py 提供 GI 假对象)
├── PKGBUILD                      # pacman 包
├── install.sh                    # 开发用安装
├── dev-demo/                     # 手工验收夹具
└── docs/                         # design / pitfalls / CHANGELOG
```
