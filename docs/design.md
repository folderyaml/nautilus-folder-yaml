# 设计

## 需求

让文件管理器按**文件夹内的元数据**增强显示:

- 文件夹显示一段自定义描述,磁盘上的真名和路径不变
- 文件夹内的文件也能各有一行描述
- 全局开关即时切换显示

## `.folder.yaml`

文件夹内的 dotfile,随文件夹移动而存活,任何工具都能读写:

```yaml
desc: 我的项目
file-desc:
  notes.txt: 会议记录
```

两个键都可选、都是顶层键。`file-desc` 的键是**文件名**,不是路径。
写入用 ruamel.yaml round-trip 模式,保留注释、键序、引号与 flow 风格。

## 界面

| 位置 | 内容 |
|---|---|
| 图标视图 | 名称下方的第二行(caption 属性 `desc`) |
| 列表视图 | 「描述」列,紧贴名称列,字号 0.85em |
| 右键条目 | 修改描述(文件夹与文件同一个菜单项) |
| 右键空白 | 隐藏描述 / 显示描述 |

中文界面叫「描述」,其他语言叫 `desc`。

## 已验证的机制

全部经 nautilus 50 / nautilus-python 4.1 源码或实测确认。

1. **第二行 caption**:`add_string_attribute('desc', …)` + gsettings `org.gnome.nautilus.icon-view` 的 `captions`;改 captions 立即生效
2. **扩展属性没有 remove**:`add_string_attribute(attr, '')` 置空清显示;`invalidate_extension_info()` 会先清空再重跑所有 InfoProvider
3. **菜单重建**:nautilus 只在视图加载时构建扩展菜单;对当前文件夹重加一次扩展属性 → `nautilus_file_changed` → 约 0.5s 后重建
4. **列表视图自定义列**:`Nautilus.ColumnProvider.get_columns()` 返回的列,右键列头可勾选
5. **进程内改列宽**:扩展与 nautilus 同进程同 GTK,可遍历 `Gtk.Window.get_toplevels()` 拿 `Gtk.ColumnView`,对列调 `set_expand()`/`set_fixed_width()`;`Nautilus.Column` 本身没有这两个属性
6. **从 model 读全部文件名**:`view.get_model()` 每行 → `GtkTreeListRow.get_item()` → `get_property('file')` → `get_name()`,滚动区外的行也能拿到
7. **量文字宽度**:任一 `Gtk.Label` 的 `create_pango_layout(text).get_pixel_size()`,与 nautilus 自己的排版一致
8. **按列位置改样式**:GTK 4.24 支持 `:nth-child()`;行里只有可见列的单元格,所以「描述列在可见列中的序号」= 它的 cell 的 nth-child
9. **视图模式切换信号**:gsettings `org.gnome.nautilus.preferences` 的 `default-folder-viewer` 每次切换都会写;控件侧没有可用信号

## 死路(不要重试)

| 尝试 | 结论 | 依据 |
|---|---|---|
| `add_string_attribute("name", …)` 覆盖显示名 | ❌ `"name"` 被特判为真实显示名 | `nautilus-file.c:6437` |
| 写 `standard::sort-order` 让文件夹排后 | ❌ gvfs 只存 `metadata::` 命名空间 | `gdaemonvfs.c:1202`、`1054` |
| 图标视图分组 | ❌ GtkGridView 没有 header factory API | `gtkgridview.h` |
| C 扩展获得更多权限 | ❌ 同一扩展 ABI,内部符号隐藏 | `nm -D /usr/bin/nautilus` |
| 分组/分区(纯扩展) | ❌ 普通文件视图无 section 渲染 | `nautilus-view-model.c:105` |

## 决策

1. **纯 nautilus-python 插件,不改 C 代码**(2026-10-23):只用 InfoProvider / MenuProvider / ColumnProvider / PropertyPageProvider;够不到就不做
2. **描述而非改名**(2026-08-17):caption 第二行,真名在上、描述在下
3. **`.folder.yaml` 而非 `.project.yaml`**(2026-09-24):通用文件夹元数据,避免与 MuleSoft PDK 重名
4. **文件描述用 xattr 令牌跟随**(2026-09):`user.nautilus-folder-yaml.desc` 记录写入时的 folder/name/desc,重命名或移动后认领进新文件夹的 yaml;yaml 始终是真源
5. **ruamel.yaml 替代手写 YAML 编辑**(2026-10-24):round-trip 模式保留注释,代码从 400 行降到 60 行;代价是多一个依赖
6. **界面双语**(2026-10-24):按 `LC_ALL`/`LC_MESSAGES`/`LANG` 判断,中文环境用中文,其余用英文;英文里统一叫 `desc`
7. **分发走自建 pacman 源**(2026-10-24):GitHub Pages 托管 `x86_64/folderyaml.db`,用户配三行即可 `pkexec pacman -Syu nautilus-folder-yaml`;不做 AUR,不做 GPG 签名(`SigLevel = Optional TrustAll`)
8. **skill 独立分发**(2026-10-24):`folderyaml/skills` 仓库,`npx skills add folderyaml/skills --skill folder-yaml -g`
