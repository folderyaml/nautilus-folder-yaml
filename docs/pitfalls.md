# 踩坑记录

按严重度排列,全部为实际踩过或源码级验证的坑。

## 1. GFileEnumerator 不是上下文管理器

- **现象**:`with children:` 抛 `TypeError: object does not support the context manager protocol`
- **处理**:直接 `for info in children:` 迭代,`finally` 里 `children.close(None)`(包 `GLib.Error`)

## 2. 菜单标签冻结

- **现象**:切换开关后右键菜单标签不更新
- **原因**:扩展菜单模型只在视图加载时构建一次;`popup-menu-changed` 是死代码,`items-updated` 无人监听
- **处理**:切换后对当前文件夹重加一次扩展属性 → `nautilus_file_changed` → 视图调度菜单重建,约 0.5s 翻转

## 3. 旧安装文件残留 → 双菜单

- **现象**:插件改名/换目录后右键菜单出现两份
- **原因**:nautilus-python 同时加载用户目录和系统目录下所有扩展文件
- **处理**:`install.sh` 与包脚本都会把旧副本改名成 `*.disabled`;改名时记得同步

## 4. 扩展属性没有 remove

- **现象**:开关关闭后已显示的描述不消失
- **处理**:`add_string_attribute(attr, '')` 置空;用进程内集合 `_shown` 记录"曾显示过"的路径,避免每次列目录重复写入

## 5. `__pycache__` 残留

`python3 -m py_compile` 会在源码目录生成 `__pycache__/`;`.gitignore` 已忽略,安装目录出现时手动清理。

## 6. 无热重载

改插件后必须 `nautilus -q`;加载错误出现在 nautilus stderr。

## 7. 跟随令牌依赖 xattr

- **现象**:U 盘(exFAT)、网盘上文件改名/移动后描述不跟随
- **原因**:`user.*` 扩展属性需要文件系统支持
- **处理**:`_set_token` 吞掉 `OSError`,退化为"不跟随 + 懒清理",不报错

## 8. 名称列霸占宽度,扩展 API 改不了列宽

- **原因**:nautilus 只给 `name` 列 `set_expand(TRUE)`;`Nautilus.Column` 没有宽度属性
- **处理**:进程内把名称列 `expand=FALSE` + `fixed_width` 设为**当前目录最长文件名**的宽度,描述列 `expand=TRUE`
- **别只测已渲染的行**:要遍历视图 model 取全部文件名,否则窗口一变窄全是「…」
- **别测列头控件本身**:`GtkColumnViewTitle` 被拉伸填满,测它等于自锁;要测它内部的 Label
- **一行都没渲染时不要写宽度**,等下一次刷新

## 9. 图标↔列表切换不触发任何 provider

- **原因**:切换会销毁并新建 `Gtk.ColumnView`,但不对已加载文件重跑 InfoProvider;新视图的 model 在连接之前就设好了
- **处理**:监听 gsettings `default-folder-viewer`,并在 250ms 后补一次
- **别用**:`child-added`、`notify::visible-child` 实测都不触发

## 10. PyGObject 包装对象会被回收重建

- **现象**:`WeakKeyDictionary` / `WeakSet` 记状态永远拿不到
- **原因**:PyGObject 每次跨语言取对象都新建 Python 包装,最后一个引用消失后回收
- **处理**:状态用「强引用 view → dict」的普通字典,每轮结束清理已消失的 view(连带 `disconnect`)
- **同类**:`GObject.set_data()` 在 PyGObject 里被禁用

## 11. GTK CSS 只对真实节点生效,nth-child 依赖可见列

- **处理**:`Gtk.CssProvider` + `columnview.<class> row > cell:nth-child(N) label { font-size: 0.85em }`;列被拖动或隐藏时重算 N 并换 class
- **实测**:`0.85em` 生效,`smaller` 语义不稳定

## 12. ruamel round-trip 的边界

- CRLF 会被规范化成 LF;`...` 文档结束符会被丢掉
- 重复键在读的时候就抛 `DuplicateKeyError`(`YAMLError` 子类)——正好实现"拒绝覆盖"
- 直接把 `str` 赋给已存在的 block scalar 键,会沿用原来的 `>`/`|` 风格;必须用 `PlainScalarString` 包一层才会写成单行
- 引号不用手写:`PlainScalarString('true')` 会被正确写成 `'true'`

## 调试手法

- 无截图工具时用 `Gtk.WidgetPaintable` + `render_texture()` 把窗口存成 PNG
- 自动化导航:`slot.activate_action('slot.open-location', GLib.Variant('s', uri))`,**必须带 `slot.` 前缀**
