#!/usr/bin/env python3
"""nautilus-folder-yaml —— 让文件夹用 .folder.yaml 描述自己。

desc       文件夹的描述
file-desc  文件夹内文件的描述（键是文件名）
两者在界面里都叫「描述」，英文界面叫 desc：图标视图显示在名称下方，
列表视图显示在「描述」列。纯 nautilus-python 插件，不改 nautilus 源码。
"""

import io
import json
import os
import stat
import tempfile
import traceback

import gi
gi.require_version('Gdk', '4.0')
gi.require_version('Gtk', '4.0')
gi.require_version('Nautilus', '4.1')
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Nautilus
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import PlainScalarString

CONFIG = os.path.expanduser('~/.config/nautilus-folder-yaml')
STATE = os.path.join(CONFIG, 'state.json')
YAML_NAME = '.folder.yaml'
DESC, FILES = 'desc', 'file-desc'
ATTR = 'desc'                       # 扩展属性名 = yaml 键 = 界面上的名字
XATTR = 'user.nautilus-folder-yaml.desc'
COLUMN = 'NautilusFolderYaml::Desc'
MAX_YAML = 1 << 20
NAME_SHARE = 0.5                    # 名称列最多占视图宽度的比例
DESC_FONT_SCALE = '0.85em'
CAPTIONS_SCHEMA = 'org.gnome.nautilus.icon-view'
VIEW_MODE_SCHEMA = 'org.gnome.nautilus.preferences'
VIEW_MODE_KEY = 'default-folder-viewer'

def _is_zh(locale):
    """界面语言是否为中文：看 locale 的完整写法，`zh_CN.UTF-8` 等。"""
    return locale.lower().startswith('zh')


_ZH = _is_zh(os.environ.get('LC_ALL') or os.environ.get('LC_MESSAGES')
             or os.environ.get('LANG') or '')


def _t(zh, en):
    """界面文案：中文环境用中文，其余用英文（英文里统一叫 desc）。"""
    return zh if _ZH else en


_yaml = YAML()                      # round-trip：保留注释、键序、引号、flow 风格
_yaml.preserve_quotes = True
_settings = Gio.Settings.new(CAPTIONS_SCHEMA)
_cache = {}                         # folder -> ((yaml_mtime, dir_mtime), (desc, files))
_shown = set()                      # 曾显示过描述的路径，用于置空清理
_state_cache = [None, {}]           # [mtime, state]


# --- 状态 -----------------------------------------------------------------

def _state_data():
    try:
        mtime = os.path.getmtime(STATE)
    except OSError:
        return {}
    if _state_cache[0] == mtime:
        return _state_cache[1]
    try:
        with open(STATE, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    _state_cache[:] = [mtime, data]
    return data


def _save_state(**values):
    data = {**_state_data(), **values}
    os.makedirs(CONFIG, exist_ok=True)
    _atomic_write(STATE, json.dumps(data))
    _state_cache[:] = [None, {}]


def _enabled():
    return _state_data().get('enabled', True)


def _atomic_write(path, text, mode=0o644):
    """写临时文件再替换：读者要么看到旧内容，要么看到新内容。"""
    parent = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', dir=parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --- .folder.yaml ---------------------------------------------------------

def _read(folder):
    """(desc, {文件名: 描述})，按 yaml 与目录 mtime 缓存。

    顺手清掉文件已不在的条目：那是移动/删除后留下的失效记录。
    """
    path = os.path.join(folder, YAML_NAME)
    try:
        stamp = (os.path.getmtime(path), os.path.getmtime(folder))
    except OSError:
        _cache.pop(folder, None)
        return (None, {})
    hit = _cache.get(folder)
    if hit is not None and hit[0] == stamp:
        return hit[1]

    try:
        if os.path.getsize(path) > MAX_YAML:
            raise ValueError
        with open(path, encoding='utf-8') as f:
            data = _yaml.load(f)
    except (OSError, ValueError, YAMLError):
        data = None
    data = data if isinstance(data, dict) else {}
    desc, files = data.get(DESC), data.get(FILES)
    files = files if isinstance(files, dict) else {}
    result = (
        desc.strip() if isinstance(desc, str) and desc.strip() else None,
        {k: v.strip() for k, v in files.items()
         if isinstance(k, str) and isinstance(v, str) and v.strip()},
    )
    _cache[folder] = (stamp, result)
    if len(_cache) > 1024:
        _cache.pop(next(iter(_cache)))

    stale = [n for n in result[1] if not os.path.lexists(os.path.join(folder, n))]
    if stale:
        try:
            _update(folder, lambda d: _drop_entries(d, stale))
        except (OSError, ValueError):
            traceback.print_exc()
        else:
            return _read(folder)
    return result


def _drop_entries(data, names):
    files = data.get(FILES)
    if not isinstance(files, dict):
        return False
    for name in names:
        files.pop(name, None)
    if not files:
        data.pop(FILES, None)
    return True


def _update(folder, mutate, create=False):
    """就地修改 .folder.yaml；mutate(data) 返回真值表示有改动。

    保留注释、键序、引号、flow 风格；改完为空则删除文件。
    create=False 时文件不存在直接返回（删除没有可删的东西）。
    """
    path = os.path.join(folder, YAML_NAME)
    try:
        file_stat = os.stat(path)
        if file_stat.st_size > MAX_YAML:
            raise ValueError(_t('.folder.yaml 文件过大', '.folder.yaml is too large'))
        with open(path, encoding='utf-8') as f:
            data = _yaml.load(f)
    except FileNotFoundError:
        if not create:
            return
        data, mode = None, 0o644
    except (OSError, YAMLError) as error:
        raise ValueError(_t('现有 .folder.yaml 格式无效',
                            'existing .folder.yaml is not valid')) from error
    else:
        mode = stat.S_IMODE(file_stat.st_mode)

    data = data if data is not None else {}
    if not isinstance(data, dict):
        raise ValueError(_t('.folder.yaml 顶层必须是对象',
                            '.folder.yaml must be a mapping'))
    if not mutate(data):
        return
    _cache.pop(folder, None)
    if not data:
        os.unlink(path)
        return
    buffer = io.StringIO()
    _yaml.dump(data, buffer)
    _atomic_write(path, buffer.getvalue(), mode)


def _check(value):
    """校验输入，并让 ruamel 按需决定加不加引号（`true`、`a: b` 会加）。"""
    value = value.strip()
    if not value:
        raise ValueError(_t('描述不能为空', 'desc cannot be empty'))
    if '\n' in value or '\r' in value:
        raise ValueError(_t('描述不能包含换行', 'desc cannot contain a newline'))
    return PlainScalarString(value)


def _set_desc(folder, value):
    value = _check(value)

    def mutate(data):
        data[DESC] = value
        return True

    _update(folder, mutate, create=True)


def _del_desc(folder):
    def mutate(data):
        if DESC not in data:
            return False
        del data[DESC]
        return True

    _update(folder, mutate)


def _set_file_desc(folder, name, value):
    value = _check(value)

    def mutate(data):
        files = data.get(FILES)
        if files is None:
            files = data[FILES] = {}
        elif not isinstance(files, dict):
            raise ValueError(_t('file-desc 必须是对象',
                                'file-desc must be a mapping'))
        files[name] = value
        return True

    _update(folder, mutate, create=True)


def _del_file_desc(folder, name):
    def mutate(data):
        files = data.get(FILES)
        if not isinstance(files, dict) or name not in files:
            return False
        del files[name]
        if not files:
            del data[FILES]
        return True

    _update(folder, mutate)


# --- 跟随令牌（文件自己的扩展属性） ---------------------------------------

def _token(path):
    try:
        return json.loads(os.getxattr(path, XATTR))
    except (OSError, ValueError):
        return None


def _set_token(path, folder, name, value):
    try:
        payload = json.dumps({'folder': folder, 'name': name, 'desc': value})
        os.setxattr(path, XATTR, payload.encode('utf-8'))
    except (OSError, TypeError, ValueError):
        pass                        # exFAT / 网盘：描述不跟随，退化为懒清理


def _drop_token(path):
    try:
        os.removexattr(path, XATTR)
    except OSError:
        pass


# --- 取值与应用 -----------------------------------------------------------

def _local_path(file):
    """本地路径，或 None（远程、搜索视图等没有本地路径的条目）。"""
    uri = file.get_uri()
    if not uri.startswith('file:'):
        return None
    try:
        return GLib.filename_from_uri(uri)[0]
    except GLib.Error:
        return None


def _annotation(path, folder, name):
    """一个文件要显示的描述，同时让令牌与 yaml 保持一致。"""
    annotation = _read(folder)[1].get(name)
    token = _token(path)

    if annotation is not None:
        if token != {'folder': folder, 'name': name, 'desc': annotation}:
            _set_token(path, folder, name, annotation)
        return annotation
    if token is None:
        return None
    if (token.get('folder'), token.get('name')) != (folder, name):
        # 文件被改名/移动到这里：认领进本文件夹的 yaml
        value = token.get('desc')
        if not isinstance(value, str) or not value.strip():
            _drop_token(path)
            return None
        try:
            _set_file_desc(folder, name, value)
        except (OSError, ValueError):
            traceback.print_exc()
        _set_token(path, folder, name, value)
        return value
    _drop_token(path)               # 在本文件夹被手动删掉：令牌不得复活它
    return None


def _apply(file):
    """给一个条目设置/清空 desc 扩展属性。"""
    path = _local_path(file)
    if path is None:
        return
    if file.is_directory():
        value = _read(path)[0]
    else:
        value = _annotation(path, os.path.dirname(path), os.path.basename(path))
    if _enabled() and value:
        file.add_string_attribute(ATTR, value)
        _shown.add(path)
    elif path in _shown:
        file.add_string_attribute(ATTR, '')     # 扩展属性没有 remove，置空清显示


def _refresh_folder(folder):
    """对当前文件夹的每个子项重新应用扩展信息，让开关立即生效。"""
    gfile = folder.get_location()
    try:
        children = gfile.enumerate_children('standard::name',
                                            Gio.FileQueryInfoFlags.NONE, None)
    except GLib.Error:
        return
    try:
        for info in children:
            file_info = Nautilus.FileInfo.lookup_for_uri(
                gfile.get_child(info.get_name()).get_uri())
            if file_info is not None:
                _apply(file_info)
                file_info.invalidate_extension_info()
    finally:
        try:
            children.close(None)
        except GLib.Error:
            pass


# --- 图标视图 captions ----------------------------------------------------

def _sync_captions(enabled):
    """开：把 desc 放到 captions 首位。关：恢复用户原来的设置。"""
    captions = list(_settings.get_strv('captions'))
    if enabled:
        if ATTR not in captions:
            _save_state(captions=captions)
            _set_captions([ATTR] + [c for c in captions if c not in ('none', ATTR)])
    elif ATTR in captions:
        backup = _state_data().get('captions')
        _save_state(captions=None)
        _set_captions(backup if isinstance(backup, list)
                      else [c for c in captions if c != ATTR])


def _set_captions(captions):
    _settings.set_strv('captions', captions)


# --- 列表视图列宽与字号 ---------------------------------------------------
# nautilus 只给名称列 expand=TRUE，描述列会被推到最右且拖不回来；
# Nautilus.Column 又没有宽度属性，只能在进程内改 GTK 控件：
# 名称列按当前目录最长文件名定宽，描述列吃掉剩余宽度，字号小一号。

_view_states = {}                   # Gtk.ColumnView -> dict（强引用，见 pitfalls #11）
_css_done = False
_view_mode_watched = False
_view_mode_settings = None
_fit_scheduled = False


def _state(view):
    state = _view_states.get(view)
    if state is None:
        state = _view_states[view] = {'key': None, 'css': None,
                                      'model': None, 'handler': None}
    return state


def _walk(widget):
    """深度优先遍历，保持兄弟顺序。"""
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from _walk(child)
        child = child.get_next_sibling()


def _column_views(widget):
    return [w for w in _walk(widget) if isinstance(w, Gtk.ColumnView)]


def _first_label(widget):
    return next((w for w in _walk(widget)
                 if isinstance(w, Gtk.Label) and w.get_text()), None)


def _of_type(root, name):
    """按类名找控件：这些是 nautilus 的 C 类型，导入不到。"""
    return [w for w in _walk(root) if type(w).__name__ == name]


def _file_of(model, index):
    """model 第 index 行背后的文件对象，或 None。"""
    try:
        row = model.get_item(index)
        item = row.get_item() if hasattr(row, 'get_item') else row
        return item.get_property('file')
    except Exception:
        return None


def _folder_key(model):
    """第一行的父 URI；空 model 返回 None。"""
    try:
        if model.get_n_items() == 0:
            return None
        uri = _file_of(model, 0).get_uri()
    except Exception:
        return None
    return uri.rsplit('/', 1)[0] if '/' in uri else uri


def _name_width(view, model):
    """名称列需要多宽，或 None（一行都还没渲染，量了会把名字截断）。"""
    for cell in _of_type(view, 'NautilusNameCell'):
        label = _first_label(cell)
        if label is None:
            continue
        cell_width = cell.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
        if cell_width <= 0:
            continue
        # 单元格减去文字 = 图标、间距、内边距（未完全布局时可能为负）
        overhead = max(0, cell_width
                       - label.measure(Gtk.Orientation.HORIZONTAL, -1)[1])
        widths = []
        if model is not None:
            for index in range(model.get_n_items()):
                file = _file_of(model, index)
                if file is not None and file.get_name():
                    widths.append(label.create_pango_layout(
                        file.get_name()).get_pixel_size()[0])
        titles = _of_type(view, 'GtkColumnViewTitle')
        title = _first_label(titles[0]) if titles else None
        header = (title.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
                  if title is not None else 0)
        needed = max(overhead + max(widths or [0]), header)
        if view.get_width() > 0:
            needed = min(needed, max(120, int(view.get_width() * NAME_SHARE)))
        return needed
    return None


def _visible_index(columns, column):
    """column 在可见列中的 1 基序号；找不到返回 0。"""
    position = 0
    for candidate in columns:
        if not candidate.get_visible():
            continue
        position += 1
        if candidate is column:
            return position
    return 0


def _desc_css():
    """描述列字号小一号：行里只有可见列，nth-child 就是它在可见列中的序号。"""
    global _css_done
    if _css_done:
        return
    _css_done = True
    rules = '\n'.join(
        'columnview.nautilus-folder-yaml-%d row > cell:nth-child(%d) label'
        ' { font-size: %s; }' % (i, i, DESC_FONT_SCALE) for i in range(1, 17))
    try:
        provider = Gtk.CssProvider()
        provider.load_from_string(rules)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    except Exception:
        pass                        # 老 GTK / 无 display：字号保持默认


def _set_css_class(view, index):
    state = _state(view)
    wanted = 'nautilus-folder-yaml-%d' % index if index else None
    if state['css'] == wanted:
        return
    if state['css'] is not None:
        try:
            view.remove_css_class(state['css'])
        except Exception:
            pass
    if wanted is not None:
        try:
            view.add_css_class(wanted)
        except Exception:
            pass
    state['css'] = wanted


def _hook(view):
    """跟着 model 走：进目录、换目录都会触发重算。"""
    state = _state(view)
    try:
        model = view.get_model()
    except Exception:
        return
    if model is None or state['model'] is model:
        return
    if state['model'] is not None and state['handler'] is not None:
        try:
            state['model'].disconnect(state['handler'])
        except Exception:
            pass
    state['model'] = model
    try:
        state['handler'] = model.connect('items-changed', _on_items_changed)
    except Exception:
        state['handler'] = None


def _on_items_changed(*_args):
    _schedule_fit()


def _fit(view):
    """把描述列放到名称列后面并撑满。永不抛异常。"""
    columns = list(view.get_columns())
    by_id = {c.get_id(): c for c in columns}
    name_column, desc_column = by_id.get('name'), by_id.get(COLUMN)
    if name_column is None or desc_column is None:
        return
    state = _state(view)

    if not desc_column.get_visible():
        # 描述列隐藏：还原 nautilus 自己的布局
        if not name_column.get_expand():
            name_column.set_fixed_width(-1)
            name_column.set_expand(True)
        state['key'] = None
        _set_css_class(view, 0)
        return

    model = view.get_model()
    try:
        count = model.get_n_items() if model is not None else 0
    except Exception:
        count = 0
    key = (_folder_key(model), count)
    if key != state['key']:
        needed = _name_width(view, model)
        if needed is not None:
            name_column.set_fixed_width(needed)
            state['key'] = key      # 量到了才记，没量到下一轮再试

    desc_column.set_expand(True)
    name_column.set_expand(False)
    _set_css_class(view, _visible_index(columns, desc_column))


def _fit_columns():
    """重排所有窗口里的列表视图。永不抛异常。"""
    _desc_css()
    _watch_view_mode()
    seen = set()
    try:
        toplevels = Gtk.Window.get_toplevels()
        for index in range(toplevels.get_n_items()):
            window = toplevels.get_item(index)
            if window is None:
                continue
            for view in _column_views(window):
                seen.add(view)
                try:
                    _hook(view)
                    _fit(view)
                except Exception:
                    pass                # 一个怪视图不能拖垮其他
    except Exception:
        pass                            # nautilus 内部结构变了：保持原样
    for view in [v for v in _view_states if v not in seen]:
        state = _view_states.pop(view)
        if state['model'] is not None and state['handler'] is not None:
            try:
                state['model'].disconnect(state['handler'])
            except Exception:
                pass


def _schedule_fit():
    """合并列宽重算：每个主循环最多一次。"""
    global _fit_scheduled
    if _fit_scheduled:
        return
    _fit_scheduled = True

    def run():
        global _fit_scheduled
        _fit_scheduled = False
        _fit_columns()
        return False

    GLib.idle_add(run)


def _on_view_mode_changed(_settings, _key):
    """图标 ↔ 列表切换会新建视图，且不重跑 provider：补两次重算。"""
    _schedule_fit()

    def again():
        _schedule_fit()
        return False

    try:
        GLib.timeout_add(250, again)
    except Exception:
        pass


def _watch_view_mode():
    """监听视图模式切换（模块级强引用，PyGObject 会回收临时包装）。"""
    global _view_mode_watched, _view_mode_settings
    if _view_mode_watched:
        return
    _view_mode_watched = True
    try:
        _view_mode_settings = Gio.Settings.new(VIEW_MODE_SCHEMA)
        _view_mode_settings.connect('changed::' + VIEW_MODE_KEY,
                                    _on_view_mode_changed)
    except Exception:
        _view_mode_settings = None


def _active_window():
    application = Gio.Application.get_default()
    if application is not None:
        try:
            window = application.get_active_window()
        except AttributeError:
            window = None
        if window is not None:
            return window
    for window in Gtk.Window.list_toplevels():
        if window.is_active():
            return window
    return None


# --- nautilus 扩展点 ------------------------------------------------------

class NautilusFolderYamlInfoProvider(GObject.GObject, Nautilus.InfoProvider):
    def update_file_info(self, file):
        _apply(file)
        _schedule_fit()             # 幂等，保证新建的列表视图也能排好列


class NautilusFolderYamlMenu(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        super().__init__()
        self._dialogs = {}
        self._alerts = set()

    def get_file_items(self, files):
        if len(files) != 1:
            return []
        file = files[0]
        path = _local_path(file)
        if path is None:
            return []
        if file.is_directory():
            folder, name = path, None
        else:
            folder, name = os.path.dirname(path), os.path.basename(path)
        item = Nautilus.MenuItem(
            name='NautilusFolderYaml::Edit',
            label=_t('修改描述', 'Edit desc'),
            tip=_t('编辑 .folder.yaml 中的 desc', 'Edit desc in .folder.yaml'),
            icon=None)
        item.connect('activate', self._on_edit, file, folder, name)
        return [item]

    def _on_edit(self, _item, file, folder, name):
        if name is None:
            initial = _read(folder)[0]
        else:
            initial = _read(folder)[1].get(name)

        def save(window, entry):
            value = entry.get_text()
            try:
                if name is None:
                    if value.strip():
                        _set_desc(folder, value)
                    else:
                        _del_desc(folder)
                elif value.strip():
                    _set_file_desc(folder, name, value)
                else:
                    _del_file_desc(folder, name)
                    _drop_token(os.path.join(folder, name))
            except Exception as error:
                traceback.print_exc()
                self._error(_t('无法修改描述', 'Cannot edit desc'),
                            str(error) or _t('写入 .folder.yaml 失败',
                                             'writing .folder.yaml failed'),
                            parent=window)
                return
            _apply(file)
            file.invalidate_extension_info()
            window.close()

        self._editor(file, initial, save)

    def _editor(self, file, initial, on_save):
        """单行编辑窗口；保存失败时保留窗口和输入。"""
        uri = file.get_uri()
        existing = self._dialogs.get(uri)
        if existing is not None:
            existing.present()
            return

        window = Gtk.Window(title=_t('修改描述', 'Edit desc'))
        window.set_default_size(420, 120)
        window.set_modal(True)
        window.set_destroy_with_parent(True)
        parent = _active_window()
        if parent is not None and parent is not window:
            window.set_transient_for(parent)

        entry = Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_activates_default(True)
        entry.set_text(initial or '')
        entry.set_position(-1)
        cancel = Gtk.Button(label=_t('取消', 'Cancel'))
        save = Gtk.Button(label=_t('保存', 'Save'))
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(cancel)
        buttons.append(save)
        label = Gtk.Label(label=_t('描述', 'desc'))
        label.set_xalign(0)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for margin in ('top', 'bottom', 'start', 'end'):
            getattr(box, 'set_margin_' + margin)(18)
        for widget in (label, entry, buttons):
            box.append(widget)
        window.set_child(box)
        window.set_default_widget(save)

        cancel.connect('clicked', lambda _button: window.close())
        save.connect('clicked', lambda _button: on_save(window, entry))
        window.connect('close-request', self._on_editor_close, uri)

        def on_key(_controller, keyval, _keycode, _state):
            if keyval == Gdk.KEY_Escape:
                window.close()
                return True
            return False

        keys = Gtk.EventControllerKey()
        keys.connect('key-pressed', on_key)
        window.add_controller(keys)

        self._dialogs[uri] = window
        window.present()
        entry.grab_focus()

    def _on_editor_close(self, _window, uri):
        self._dialogs.pop(uri, None)
        return False

    def _error(self, message, detail, parent=None):
        alert = Gtk.AlertDialog()
        alert.set_message(message)
        alert.set_detail(detail)
        alert.set_buttons([_t('确定', 'OK')])
        self._alerts.add(alert)

        def done(_alert, result, _data):
            try:
                alert.choose_finish(result)
            except GLib.Error:
                pass
            self._alerts.discard(alert)

        alert.choose(parent or _active_window(), None, done, None)

    def get_background_items(self, current_folder):
        item = Nautilus.MenuItem(
            name='NautilusFolderYaml::Toggle',
            label=_t('隐藏描述', 'Hide desc') if _enabled()
            else _t('显示描述', 'Show desc'),
            tip=_t('在名称下方显示 .folder.yaml 中的描述',
                   'Show the .folder.yaml desc under the name'),
            icon=None)
        item.connect('activate', self._on_toggle, current_folder)
        return [item]

    def _on_toggle(self, _item, current_folder):
        try:
            enabled = not _enabled()
            _save_state(enabled=enabled)
            _sync_captions(enabled)
            _refresh_folder(current_folder)
            # nautilus 只在视图加载时构建扩展菜单；对当前文件夹重加一次扩展
            # 属性会触发 nautilus_file_changed，约 0.5s 后菜单标签跟着翻转。
            current_folder.add_string_attribute(
                ATTR, current_folder.get_string_attribute(ATTR) or '')
        except Exception:
            traceback.print_exc()


class NautilusFolderYamlColumns(GObject.GObject, Nautilus.ColumnProvider):
    def get_columns(self):
        return [Nautilus.Column(
            name=COLUMN, attribute=ATTR,
            label=_t('描述', 'desc'),
            description=_t('文件夹或文件的描述(.folder.yaml)',
                           'Folder or file desc (.folder.yaml)'))]


_sync_captions(_enabled())
