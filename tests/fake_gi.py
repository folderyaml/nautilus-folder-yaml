"""GI / nautilus 的最小假实现，让插件能在没有 nautilus 的环境里被导入和测试。"""

import importlib.util
import os
import tempfile
import types
from pathlib import Path
from urllib.parse import unquote, urlparse

PLUGIN = Path(__file__).resolve().parent.parent / 'nautilus-folder-yaml.py'


class Settings:
    instances = []

    def __init__(self):
        self.values = {'captions': []}
        self.handlers = {}

    @classmethod
    def new(cls, schema):
        instance = cls()
        instance.schema = schema
        cls.instances.append(instance)
        return instance

    @classmethod
    def for_schema(cls, schema):
        for instance in reversed(cls.instances):
            if instance.schema == schema:
                return instance
        return None

    @classmethod
    def forget(cls):
        cls.instances = []

    def connect(self, signal, callback):
        self.handlers[signal] = callback
        return len(self.handlers)

    def emit(self, signal):
        callback = self.handlers.get(signal)
        if callback is not None:
            callback(self, signal.split('::')[-1])

    def get_strv(self, key):
        return list(self.values.get(key, []))

    def set_strv(self, key, value):
        self.values[key] = list(value)


class MenuItem:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.callback = None
        self.args = ()

    def connect(self, _signal, callback, *args):
        self.callback = callback
        self.args = args


class Column:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FileInfo:
    def __init__(self, uri, directory=True):
        self.uri = uri
        self.directory = directory
        self.attributes = {}

    def is_directory(self):
        return self.directory

    def get_uri(self):
        return self.uri

    def add_string_attribute(self, name, value):
        self.attributes[name] = value

    def get_string_attribute(self, name):
        return self.attributes.get(name, '')

    def invalidate_extension_info(self):
        pass


class Nautilus:
    class InfoProvider:
        pass

    class MenuProvider:
        pass

    class ColumnProvider:
        pass

    MenuItem = MenuItem
    Column = Column
    FileInfo = FileInfo


class Gio:
    Settings = Settings
    FileQueryInfoFlags = types.SimpleNamespace(NONE=0)

    class Application:
        @staticmethod
        def get_default():
            return None


class GLib:
    class Error(Exception):
        pass

    idle_queue = []
    timeout_queue = []

    @classmethod
    def timeout_add(cls, delay, func, *args):
        cls.timeout_queue.append((delay, func, args))
        return len(cls.timeout_queue)

    @classmethod
    def run_timeouts(cls):
        while cls.timeout_queue:
            _delay, func, args = cls.timeout_queue.pop(0)
            func(*args)

    @classmethod
    def idle_add(cls, func, *args):
        cls.idle_queue.append((func, args))
        return len(cls.idle_queue)

    @classmethod
    def run_idle(cls):
        while cls.idle_queue:
            func, args = cls.idle_queue.pop(0)
            func(*args)

    @staticmethod
    def filename_from_uri(uri):
        return unquote(urlparse(uri).path), None


class ColumnViewColumn:
    def __init__(self, column_id, visible=True):
        self._id = column_id
        self._visible = visible
        self._expand = False
        self._fixed_width = -1

    def get_id(self):
        return self._id

    def get_visible(self):
        return self._visible

    def set_visible(self, visible):
        self._visible = visible

    def get_expand(self):
        return self._expand

    def set_expand(self, expand):
        self._expand = expand

    def get_fixed_width(self):
        return self._fixed_width

    def set_fixed_width(self, width):
        self._fixed_width = width


class PangoLayout:
    """每字符 10px，宽度便于断言。"""

    def __init__(self, text):
        self._text = text

    def get_pixel_size(self):
        return (len(self._text) * 10, 18)


class Widget:
    natural = 0

    def __init__(self, children=()):
        self._children = list(children)
        for index, child in enumerate(self._children):
            child._next_sibling = (self._children[index + 1]
                                   if index + 1 < len(self._children) else None)

    def get_first_child(self):
        return self._children[0] if self._children else None

    def get_next_sibling(self):
        return getattr(self, '_next_sibling', None)

    def measure(self, orientation, size):
        return (self.natural,) * 4

    def connect(self, signal, callback):
        self.handlers = getattr(self, 'handlers', {})
        self.handlers[signal] = callback
        return len(self.handlers)

    def click(self):
        self.handlers['clicked'](self)


class Label(Widget):
    def __init__(self, text='', label=None):
        super().__init__()
        self._text = text if label is None else label
        self.natural = len(self._text) * 10

    def get_text(self):
        return self._text

    def set_xalign(self, align):
        pass

    def create_pango_layout(self, text=None):
        return PangoLayout(self._text if text is None else text)


# 生产代码按类名识别这些 nautilus / GTK 的 C 类型。
class NautilusNameCell(Widget):
    def __init__(self, file_name='', overhead=88):
        label = Label(file_name)
        super().__init__([Widget(), label])
        self.natural = overhead + label.natural


class NautilusLabelCell(Widget):
    def __init__(self, text=''):
        super().__init__([Label(text)])
        self.natural = 12 + len(text) * 10


class GtkColumnViewTitle(Widget):
    def __init__(self, text='', natural=0):
        super().__init__([Label(text)])
        self.natural = natural or len(text) * 10


class File:
    def __init__(self, name, folder='file:///tmp/demo'):
        self._name = name
        self._uri = '%s/%s' % (folder, name)

    def get_name(self):
        return self._name

    def get_uri(self):
        return self._uri


class ViewItem:
    def __init__(self, file):
        self._file = file

    def get_property(self, name):
        if name != 'file':
            raise TypeError('no such property: %s' % name)
        return self._file


class TreeListRow:
    def __init__(self, file):
        self._file = file

    def get_item(self):
        return ViewItem(self._file)


class ViewRowModel:
    def __init__(self, names=(), folder='file:///tmp/demo'):
        self.folder = folder
        self.names = list(names)
        self.handlers = {}

    def get_n_items(self):
        return len(self.names)

    def get_item(self, index):
        return TreeListRow(File(self.names[index], self.folder))

    def connect(self, signal, callback):
        self.handlers[signal] = callback
        return len(self.handlers)

    def set_names(self, names, folder=None):
        self.names = list(names)
        if folder is not None:
            self.folder = folder
        callback = self.handlers.get('items-changed')
        if callback is not None:
            callback(self, 0, 0, len(self.names))


class ListModel:
    def __init__(self, items):
        self._items = list(items)

    def get_n_items(self):
        return len(self._items)

    def get_item(self, index):
        return self._items[index]


class ColumnView(Widget):
    def __init__(self, columns, children=(), model=None, width=1000):
        super().__init__(children)
        self._columns = list(columns)
        self._model = model
        self._width = width
        self._css = set()
        self.handlers = {}

    def get_columns(self):
        return self._columns

    def get_model(self):
        return self._model

    def set_model(self, model):
        self._model = model
        callback = self.handlers.get('notify::model')
        if callback is not None:
            callback(self, None)

    def get_width(self):
        return self._width

    def connect(self, signal, callback):
        self.handlers[signal] = callback
        return len(self.handlers)

    def add_css_class(self, name):
        self._css.add(name)

    def remove_css_class(self, name):
        self._css.discard(name)

    def has_css_class(self, name):
        return name in self._css


class Window(Widget):
    """顶层窗口；也充当编辑对话框（插件里两处都用 Gtk.Window）。"""

    toplevels = []

    def __init__(self, children=(), title=''):
        super().__init__(children)
        self.title = title
        self.closed = False
        self.handlers = {}
        self.controllers = []
        self.child = None
        self.default_widget = None

    @classmethod
    def get_toplevels(cls):
        return ListModel(cls.toplevels)

    @classmethod
    def list_toplevels(cls):
        return list(cls.toplevels)

    def is_active(self):
        return True

    def set_default_size(self, width, height):
        pass

    def set_modal(self, modal):
        pass

    def set_destroy_with_parent(self, flag):
        pass

    def set_transient_for(self, parent):
        pass

    def set_child(self, child):
        self.child = child

    def set_default_widget(self, widget):
        self.default_widget = widget

    def add_controller(self, controller):
        self.controllers.append(controller)

    def present(self):
        pass

    def close(self):
        self.closed = True
        callback = self.handlers.get('close-request')
        if callback is not None:
            callback(self)

    def connect(self, signal, callback, *args):
        self.handlers[signal] = (lambda *a: callback(*a, *args))
        return len(self.handlers)


class Entry:
    def __init__(self):
        self._text = ''

    def set_hexpand(self, value):
        pass

    def set_activates_default(self, value):
        pass

    def set_text(self, text):
        self._text = text

    def get_text(self):
        return self._text

    def set_position(self, position):
        pass

    def grab_focus(self):
        pass


class Button(Label):
    def __init__(self, label=''):
        super().__init__(label)


class Box(Widget):
    def __init__(self, orientation=0, spacing=0):
        super().__init__()
        self.spacing = spacing

    def set_halign(self, align):
        pass

    def set_margin_top(self, value):
        pass

    set_margin_bottom = set_margin_start = set_margin_end = set_margin_top

    def append(self, widget):
        self._children.append(widget)


class EventControllerKey:
    def __init__(self):
        self.handler = None

    def connect(self, _signal, callback):
        self.handler = callback


class AlertDialog:
    def __init__(self):
        self.buttons = []

    def set_message(self, message):
        self.message = message

    def set_detail(self, detail):
        self.detail = detail

    def set_buttons(self, buttons):
        self.buttons = buttons

    def choose(self, parent, cancellable, callback, data):
        pass

    def choose_finish(self, result):
        pass


class CssProvider:
    def __init__(self):
        self.text = ''

    def load_from_string(self, text):
        self.text = text


class StyleContext:
    added = []

    @classmethod
    def add_provider_for_display(cls, display, provider, priority):
        cls.added.append(provider)


class Gtk:
    Orientation = types.SimpleNamespace(VERTICAL=1, HORIZONTAL=2)
    Align = types.SimpleNamespace(END=1)
    ColumnView = ColumnView
    Window = Window
    Label = Label
    Entry = Entry
    Button = Button
    Box = Box
    EventControllerKey = EventControllerKey
    AlertDialog = AlertDialog
    CssProvider = CssProvider
    StyleContext = StyleContext
    STYLE_PROVIDER_PRIORITY_APPLICATION = 600


class Gdk:
    KEY_Escape = 65307

    class Display:
        @classmethod
        def get_default(cls):
            return cls()


class GObject:
    class GObject:
        def __init__(self):
            pass


def load():
    """导入插件模块（HOME 指向临时目录，配置不落到真实用户目录）。"""
    temp_home = tempfile.TemporaryDirectory()
    os.environ['HOME'] = temp_home.name
    repository = types.ModuleType('gi.repository')
    repository.Gdk = Gdk
    repository.Gio = Gio
    repository.GLib = GLib
    repository.GObject = GObject
    repository.Gtk = Gtk
    repository.Nautilus = Nautilus
    gi = types.ModuleType('gi')
    gi.repository = repository
    gi.require_version = lambda name, version: None
    import sys
    sys.modules['gi'] = gi
    sys.modules['gi.repository'] = repository

    spec = importlib.util.spec_from_file_location('nautilus_folder_yaml', PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._test_home = temp_home
    return module
