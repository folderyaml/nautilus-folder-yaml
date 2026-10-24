"""nautilus-folder-yaml 的单测。运行：python3 -m unittest discover -s tests"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import fake_gi                                            # noqa: E402

plugin = fake_gi.load()
_GLib = fake_gi.GLib
_ColumnViewColumn = fake_gi.ColumnViewColumn
_Settings = fake_gi.Settings
_StyleContext = fake_gi.StyleContext
_Toplevel = fake_gi.Window
_ViewRowModel = fake_gi.ViewRowModel
_Widget = fake_gi.Widget
_ColumnView = fake_gi.ColumnView
_FileInfo = fake_gi.FileInfo
_NautilusNameCell = fake_gi.NautilusNameCell
_NautilusLabelCell = fake_gi.NautilusLabelCell
_GtkColumnViewTitle = fake_gi.GtkColumnViewTitle
_Entry = fake_gi.Entry


class Folder:
    """一个临时文件夹 + 其中的 .folder.yaml。"""

    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.yaml = self.path / plugin.YAML_NAME

    def cleanup(self):
        self.temp.cleanup()

    def write(self, text):
        self.yaml.write_text(text, encoding='utf-8')
        plugin._cache.clear()

    def read(self):
        return self.yaml.read_text(encoding='utf-8') if self.yaml.exists() else None


class FolderTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = Folder()
        self.addCleanup(self.folder.cleanup)
        plugin._cache.clear()
        plugin._shown.clear()


class DescTests(FolderTestCase):
    def test_creates_yaml(self):
        plugin._set_desc(self.folder.temp.name, '新项目')
        self.assertEqual(self.folder.read(), 'desc: 新项目\n')

    def test_replaces_value_and_preserves_comments_and_fields(self):
        self.folder.write('# header\ndesc: old  # keep this\nother: y\n')
        plugin._set_desc(self.folder.temp.name, '新项目')
        self.assertEqual(self.folder.read(),
                         '# header\ndesc: 新项目  # keep this\nother: y\n')

    def test_appends_missing_key(self):
        self.folder.write('other: y\n')
        plugin._set_desc(self.folder.temp.name, '新项目')
        self.assertEqual(self.folder.read(), 'other: y\ndesc: 新项目\n')

    def test_replaces_block_scalar_with_single_line_value(self):
        self.folder.write('desc: >\n  old\nother: y\n')
        plugin._set_desc(self.folder.temp.name, '新项目')
        self.assertEqual(self.folder.read(), 'desc: 新项目\nother: y\n')

    def test_quotes_values_yaml_would_misread(self):
        plugin._set_desc(self.folder.temp.name, 'true')
        self.assertEqual(self.folder.read(), "desc: 'true'\n")
        self.assertEqual(plugin._read(self.folder.temp.name)[0], 'true')

    def test_updates_flow_mapping(self):
        self.folder.write('{other: y}\n')
        plugin._set_desc(self.folder.temp.name, '新项目')
        self.assertEqual(self.folder.read(), '{other: y, desc: 新项目}\n')

    def test_rejects_duplicate_keys_without_overwriting(self):
        original = 'desc: one\ndesc: two\n'
        self.folder.write(original)
        with self.assertRaises(ValueError):
            plugin._set_desc(self.folder.temp.name, '新项目')
        self.assertEqual(self.folder.read(), original)

    def test_rejects_invalid_yaml_without_overwriting(self):
        original = 'other: [\n'
        self.folder.write(original)
        with self.assertRaises(ValueError):
            plugin._set_desc(self.folder.temp.name, '新项目')
        self.assertEqual(self.folder.read(), original)

    def test_rejects_non_mapping_without_overwriting(self):
        original = '- one\n- two\n'
        self.folder.write(original)
        with self.assertRaises(ValueError):
            plugin._set_desc(self.folder.temp.name, '新项目')
        self.assertEqual(self.folder.read(), original)

    def test_empty_value_removes_key_and_file(self):
        self.folder.write('desc: 旧名\n')
        plugin._del_desc(self.folder.temp.name)
        self.assertIsNone(self.folder.read())

    def test_empty_value_keeps_other_fields(self):
        self.folder.write('# header\ndesc: old  # keep\nother: y\n')
        plugin._del_desc(self.folder.temp.name)
        self.assertEqual(self.folder.read(), '# header\nother: y\n')

    def test_remove_without_key_leaves_file_alone(self):
        original = 'other: y\n'
        self.folder.write(original)
        plugin._del_desc(self.folder.temp.name)
        self.assertEqual(self.folder.read(), original)

    def test_remove_missing_file_is_noop(self):
        plugin._del_desc(self.folder.temp.name)
        self.assertIsNone(self.folder.read())

    def test_rejects_blank_and_multiline_values(self):
        for value in ('   ', 'one\ntwo'):
            with self.assertRaises(ValueError):
                plugin._set_desc(self.folder.temp.name, value)
        self.assertIsNone(self.folder.read())


class FileDescTests(FolderTestCase):
    def test_creates_block_mapping(self):
        plugin._set_file_desc(self.folder.temp.name, 'notes.txt', '会议记录')
        self.assertEqual(self.folder.read(), 'file-desc:\n  notes.txt: 会议记录\n')

    def test_appends_to_existing_block_mapping(self):
        self.folder.write('desc: 项目\nfile-desc:\n  a.txt: 甲\n')
        plugin._set_file_desc(self.folder.temp.name, 'b.txt', '乙')
        self.assertEqual(self.folder.read(),
                         'desc: 项目\nfile-desc:\n  a.txt: 甲\n  b.txt: 乙\n')

    def test_replaces_one_entry_and_keeps_its_comment(self):
        self.folder.write('file-desc:\n  a.txt: 旧  # keep\n  b.txt: 乙\n')
        plugin._set_file_desc(self.folder.temp.name, 'a.txt', '新')
        self.assertEqual(self.folder.read(),
                         'file-desc:\n  a.txt: 新  # keep\n  b.txt: 乙\n')

    def test_extends_flow_mapping(self):
        self.folder.write('file-desc: {a.txt: 甲}\n')
        plugin._set_file_desc(self.folder.temp.name, 'b.txt', '乙')
        self.assertEqual(self.folder.read(),
                         'file-desc: {a.txt: 甲, b.txt: 乙}\n')

    def test_quotes_awkward_file_names(self):
        plugin._set_file_desc(self.folder.temp.name, 'a: b.txt', '含冒号')
        self.assertEqual(self.folder.read(), "file-desc:\n  'a: b.txt': 含冒号\n")

    def test_rejects_duplicate_entries_without_overwriting(self):
        original = 'file-desc:\n  a.txt: 甲\n  a.txt: 乙\n'
        self.folder.write(original)
        with self.assertRaises(ValueError):
            plugin._set_file_desc(self.folder.temp.name, 'a.txt', '新')
        self.assertEqual(self.folder.read(), original)

    def test_rejects_non_mapping_file_desc(self):
        original = 'file-desc:\n  - a.txt\n'
        self.folder.write(original)
        with self.assertRaises(ValueError):
            plugin._set_file_desc(self.folder.temp.name, 'a.txt', '甲')
        self.assertEqual(self.folder.read(), original)

    def test_rejects_blank_value(self):
        self.folder.write('file-desc:\n  a.txt: 甲\n')
        with self.assertRaises(ValueError):
            plugin._set_file_desc(self.folder.temp.name, 'a.txt', '   ')

    def test_removing_an_entry_keeps_the_others(self):
        self.folder.write('desc: 项目\nfile-desc:\n  a.txt: 甲\n  b.txt: 乙\n')
        plugin._del_file_desc(self.folder.temp.name, 'a.txt')
        self.assertEqual(self.folder.read(), 'desc: 项目\nfile-desc:\n  b.txt: 乙\n')

    def test_removing_the_last_entry_drops_the_key(self):
        self.folder.write('desc: 项目\nfile-desc:\n  a.txt: 甲\n')
        plugin._del_file_desc(self.folder.temp.name, 'a.txt')
        self.assertEqual(self.folder.read(), 'desc: 项目\n')

    def test_removing_the_last_entry_drops_an_empty_file(self):
        self.folder.write('file-desc:\n  a.txt: 甲\n')
        plugin._del_file_desc(self.folder.temp.name, 'a.txt')
        self.assertIsNone(self.folder.read())

    def test_removing_an_unknown_entry_keeps_the_file(self):
        original = 'file-desc:\n  a.txt: 甲\n'
        self.folder.write(original)
        plugin._del_file_desc(self.folder.temp.name, 'zzz.txt')
        self.assertEqual(self.folder.read(), original)

    def test_removal_without_a_yaml_file_does_nothing(self):
        plugin._del_file_desc(self.folder.temp.name, 'a.txt')
        self.assertIsNone(self.folder.read())

    def test_lookup_skips_blank_values(self):
        for name in ('a.txt', '空.txt', 'b.txt'):
            (self.folder.path / name).write_text('', encoding='utf-8')
        self.folder.write('file-desc:\n  a.txt: 甲\n  空.txt: "  "\n  b.txt: 乙\n')
        self.assertEqual(plugin._read(self.folder.temp.name)[1],
                         {'a.txt': '甲', 'b.txt': '乙'})


class CaptionsTests(unittest.TestCase):
    def setUp(self):
        self._saved = list(plugin._settings.get_strv('captions'))
        plugin._save_state(captions=None, enabled=True)
        self.addCleanup(plugin._set_captions, self._saved)
        self.addCleanup(plugin._save_state, captions=None, enabled=True)

    def test_enabling_puts_desc_first_and_backs_up(self):
        plugin._set_captions(['size', 'date'])
        plugin._sync_captions(True)
        self.assertEqual(plugin._settings.get_strv('captions'),
                         ['desc', 'size', 'date'])
        self.assertEqual(plugin._state_data()['captions'], ['size', 'date'])

    def test_disabling_restores_the_backup(self):
        plugin._set_captions(['size'])
        plugin._sync_captions(True)
        plugin._sync_captions(False)
        self.assertEqual(plugin._settings.get_strv('captions'), ['size'])
        self.assertIsNone(plugin._state_data()['captions'])

    def test_disabling_without_a_backup_only_drops_desc(self):
        plugin._set_captions(['desc', 'size'])
        plugin._sync_captions(False)
        self.assertEqual(plugin._settings.get_strv('captions'), ['size'])

    def test_enabling_twice_keeps_the_original_backup(self):
        plugin._set_captions(['size'])
        plugin._sync_captions(True)
        plugin._sync_captions(True)
        self.assertEqual(plugin._state_data()['captions'], ['size'])

    def test_switch_state_defaults_to_on(self):
        self.assertTrue(plugin._enabled())
        plugin._save_state(enabled=False)
        self.assertFalse(plugin._enabled())


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.folder = Folder()
        self.addCleanup(self.folder.cleanup)

    def menu(self):
        return plugin.NautilusFolderYamlMenu()

    def test_single_local_folder_gets_one_item(self):
        items = self.menu().get_file_items(
            [_FileInfo('file://' + self.folder.temp.name)])
        self.assertEqual([i.kwargs['label'] for i in items], ['修改描述'])
        self.assertEqual(items[0].kwargs['name'], 'NautilusFolderYaml::Edit')

    def test_single_local_file_gets_the_same_item(self):
        path = self.folder.path / 'notes.txt'
        path.write_text('', encoding='utf-8')
        items = self.menu().get_file_items([_FileInfo('file://' + str(path),
                                                     directory=False)])
        self.assertEqual([i.kwargs['label'] for i in items], ['修改描述'])

    def test_multi_select_shows_nothing(self):
        self.assertEqual(self.menu().get_file_items(
            [_FileInfo('file:///tmp/a'), _FileInfo('file:///tmp/b')]), [])

    def test_remote_items_get_nothing(self):
        self.assertEqual(self.menu().get_file_items(
            [_FileInfo('sftp://host/project')]), [])
        self.assertEqual(self.menu().get_file_items(
            [_FileInfo('sftp://host/notes.txt', directory=False)]), [])

    def test_toggle_label_follows_the_switch(self):
        folder = _FileInfo('file://' + self.folder.temp.name)
        menu = self.menu()
        self.addCleanup(plugin._save_state, enabled=True)
        plugin._save_state(enabled=True)
        self.assertEqual(menu.get_background_items(folder)[0].kwargs['label'],
                         '隐藏描述')
        plugin._save_state(enabled=False)
        self.assertEqual(menu.get_background_items(folder)[0].kwargs['label'],
                         '显示描述')

    def open_editor(self, menu, file):
        items = menu.get_file_items([file])
        items[0].callback(items[0], *items[0].args)
        window = next(iter(menu._dialogs.values()))
        entry = window.child._children[1]
        buttons = window.child._children[2]
        return window, entry, buttons

    def test_saving_a_folder_desc_through_the_dialog(self):
        folder = _FileInfo('file://' + self.folder.temp.name)
        menu = self.menu()
        window, entry, buttons = self.open_editor(menu, folder)
        entry.set_text('我的项目')
        buttons._children[1].click()            # 保存
        self.assertTrue(window.closed)
        self.assertEqual(self.folder.read(), 'desc: 我的项目\n')
        self.assertEqual(folder.attributes.get('desc'), '我的项目')

    def test_clearing_a_file_desc_through_the_dialog(self):
        path = self.folder.path / 'notes.txt'
        path.write_text('', encoding='utf-8')
        self.folder.write('file-desc:\n  notes.txt: 旧\n')
        file = _FileInfo('file://' + str(path), directory=False)
        menu = self.menu()
        window, entry, buttons = self.open_editor(menu, file)
        entry.set_text('   ')
        buttons._children[1].click()
        self.assertTrue(window.closed)
        self.assertIsNone(self.folder.read())
        self.assertIsNone(plugin._token(str(path)))

    def test_editor_prefills_the_current_value(self):
        self.folder.write('desc: 已有\n')
        folder = _FileInfo('file://' + self.folder.temp.name)
        menu = self.menu()
        _window, entry, _buttons = self.open_editor(menu, folder)
        self.assertEqual(entry.get_text(), '已有')


class LanguageTests(unittest.TestCase):
    def tearDown(self):
        plugin._ZH = True

    def test_chinese_labels(self):
        plugin._ZH = True
        self.assertEqual(plugin._t('修改描述', 'Edit desc'), '修改描述')

    def test_english_labels_say_desc(self):
        plugin._ZH = False
        self.assertEqual(plugin._t('修改描述', 'Edit desc'), 'Edit desc')
        menu = plugin.NautilusFolderYamlMenu()
        folder = _FileInfo('file:///tmp/project')
        self.assertEqual(menu.get_file_items([folder])[0].kwargs['label'],
                         'Edit desc')
        columns = plugin.NautilusFolderYamlColumns().get_columns()
        self.assertEqual(columns[0].kwargs['label'], 'desc')

    def test_locale_detection(self):
        import importlib
        for value, expected in (('zh_CN.UTF-8', True), ('en_US.UTF-8', False),
                                ('C', False)):
            self.assertEqual(plugin._is_zh(value), expected)


class ColumnTests(unittest.TestCase):
    def test_one_column_fed_by_the_desc_attribute(self):
        columns = plugin.NautilusFolderYamlColumns().get_columns()
        self.assertEqual(len(columns), 1)
        self.assertEqual(columns[0].kwargs['attribute'], plugin.ATTR)
        self.assertEqual(columns[0].kwargs['label'], '描述')
        self.assertEqual(columns[0].kwargs['name'], plugin.COLUMN)


class FitTests(unittest.TestCase):
    def setUp(self):
        _Toplevel.toplevels = []
        _StyleContext.added = []
        plugin._view_states.clear()
        plugin._css_done = False
        self.addCleanup(setattr, plugin, '_view_states', {})

    def tearDown(self):
        _Toplevel.toplevels = []

    def view(self, desc_visible=True, names=('agent-home', 'AGENTS.md'),
             overhead=88, width=1000, title='名称'):
        name = _ColumnViewColumn('name')
        name.set_expand(True)
        desc = _ColumnViewColumn(plugin.COLUMN, visible=desc_visible)
        size = _ColumnViewColumn('size')
        rows = [_Widget([_NautilusNameCell(n, overhead), _NautilusLabelCell('一段描述')])
                for n in names]
        view = _ColumnView([name, desc, size],
                           children=[_GtkColumnViewTitle(title), _Widget(rows)],
                           model=_ViewRowModel(names), width=width)
        _Toplevel.toplevels = [_Toplevel([view])]
        return name, desc, size, view

    def test_desc_visible_sizes_name_to_the_longest_file_name(self):
        name, desc, size, _view = self.view()
        plugin._fit_columns()
        self.assertFalse(name.get_expand())
        self.assertTrue(desc.get_expand())
        self.assertFalse(size.get_expand())
        self.assertEqual(name.get_fixed_width(), 188)   # 88 + 10 字符 × 10px

    def test_names_outside_the_rendered_rows_count(self):
        _name, _desc, _size, view = self.view(names=('a', 'bb'))
        view.get_model().set_names(['a', 'bb', 'a-very-long-file-name'])
        plugin._fit_columns()
        self.assertEqual(_name.get_fixed_width(), 88 + 210)

    def test_long_names_are_capped_to_a_share_of_the_view(self):
        _name, _desc, _size, _view = self.view(names=('x' * 100,), width=1000)
        plugin._fit_columns()
        self.assertEqual(_name.get_fixed_width(),
                         int(1000 * plugin.NAME_SHARE))

    def test_name_width_never_below_the_header(self):
        name, _desc, _size, _view = self.view(names=('a',), title='名称' * 20)
        plugin._fit_columns()
        self.assertEqual(name.get_fixed_width(), 400)

    def test_no_laid_out_row_means_no_width_yet(self):
        name, desc, _size, _view = self.view()
        _Toplevel.toplevels[0]._children[0]._children[1]._children = []
        plugin._fit_columns()
        self.assertFalse(name.get_expand())
        self.assertTrue(desc.get_expand())
        self.assertEqual(name.get_fixed_width(), -1)

    def test_desc_hidden_restores_nautilus_layout(self):
        name, desc, _size, _view = self.view(desc_visible=False)
        plugin._fit_columns()
        self.assertTrue(name.get_expand())
        self.assertFalse(desc.get_expand())
        self.assertEqual(name.get_fixed_width(), -1)

    def test_hiding_the_desc_column_later_restores_name_expand(self):
        name, desc, _size, _view = self.view()
        plugin._fit_columns()
        self.assertFalse(name.get_expand())
        desc.set_visible(False)
        plugin._fit_columns()
        self.assertTrue(name.get_expand())
        self.assertEqual(name.get_fixed_width(), -1)

    def test_dragged_width_survives_within_the_folder(self):
        name, _desc, _size, _view = self.view()
        plugin._fit_columns()
        name.set_fixed_width(500)       # 用户拖动分隔条
        plugin._fit_columns()
        self.assertEqual(name.get_fixed_width(), 500)

    def test_dragged_width_is_dropped_when_the_folder_changes(self):
        name, _desc, _size, view = self.view()
        plugin._fit_columns()
        name.set_fixed_width(500)
        plugin._fit_columns()
        view.get_model().set_names(['another-folder'], 'file:///tmp/other')
        plugin._fit_columns()
        self.assertEqual(name.get_fixed_width(), 88 + 140)

    def test_entering_a_folder_reschedules_a_fit(self):
        _GLib.idle_queue.clear()
        _name, _desc, _size, view = self.view()
        plugin._fit_scheduled = False
        plugin._fit_columns()
        _GLib.idle_queue.clear()
        view.get_model().set_names(['x'], 'file:///tmp/other')
        self.assertEqual(len(_GLib.idle_queue), 1)

    def test_view_without_our_column_is_untouched(self):
        name = _ColumnViewColumn('name')
        name.set_expand(True)
        _Toplevel.toplevels = [_Toplevel([_ColumnView([name, _ColumnViewColumn('size')])])]
        plugin._fit_columns()
        self.assertTrue(name.get_expand())
        self.assertEqual(name.get_fixed_width(), -1)

    def test_nested_view_is_found(self):
        name = _ColumnViewColumn('name')
        name.set_expand(True)
        desc = _ColumnViewColumn(plugin.COLUMN)
        body = _Widget([_Widget([_NautilusNameCell('abc')])])
        view = _ColumnView([name, desc], children=[body],
                           model=_ViewRowModel(['abc']))
        _Toplevel.toplevels = [_Toplevel([_Widget([view])])]
        plugin._fit_columns()
        self.assertFalse(name.get_expand())
        self.assertTrue(desc.get_expand())
        self.assertEqual(name.get_fixed_width(), 88 + 30)

    def test_missing_columns_never_raises(self):
        class Boom:
            def get_columns(self):
                raise RuntimeError('internals changed')

        _Toplevel.toplevels = [_Toplevel([Boom()])]
        plugin._fit_columns()

    def test_schedule_fits_once_per_idle_pass(self):
        _GLib.idle_queue.clear()
        name, desc, _size, _view = self.view()
        plugin._fit_scheduled = False
        for _ in range(3):
            plugin._schedule_fit()
        self.assertEqual(len(_GLib.idle_queue), 1)
        _GLib.run_idle()
        self.assertFalse(name.get_expand())
        self.assertTrue(desc.get_expand())
        plugin._schedule_fit()
        self.assertEqual(len(_GLib.idle_queue), 1)

    def test_view_mode_switch_schedules_two_passes(self):
        _GLib.idle_queue.clear()
        _GLib.timeout_queue.clear()
        plugin._view_mode_watched = False
        plugin._fit_scheduled = False
        _Settings.forget()
        self.view()
        plugin._fit_columns()
        settings = _Settings.for_schema(plugin.VIEW_MODE_SCHEMA)
        self.assertIn('changed::' + plugin.VIEW_MODE_KEY, settings.handlers)

        _GLib.idle_queue.clear()
        plugin._on_view_mode_changed(settings, plugin.VIEW_MODE_KEY)
        self.assertEqual(len(_GLib.idle_queue), 1)
        self.assertEqual(len(_GLib.timeout_queue), 1)
        _GLib.run_idle()
        _GLib.run_timeouts()
        self.assertEqual(len(_GLib.idle_queue), 1)
        _GLib.run_idle()

    def test_view_mode_watcher_is_installed_once(self):
        _Settings.forget()
        plugin._view_mode_watched = False
        self.view()
        plugin._fit_columns()
        plugin._fit_columns()
        settings = _Settings.for_schema(plugin.VIEW_MODE_SCHEMA)
        self.assertEqual(len(settings.handlers), 1)

    def test_bookkeeping_outlives_the_local_view_reference(self):
        name, _desc, _size, view = self.view()
        plugin._fit_columns()
        name.set_fixed_width(420)
        del view
        again = plugin._column_views(_Toplevel.toplevels[0])[0]
        self.assertIn(again, plugin._view_states)
        plugin._fit_columns()
        self.assertEqual(name.get_fixed_width(), 420)

    def test_closed_window_forgets_its_view(self):
        self.view()
        plugin._fit_columns()
        self.assertEqual(len(plugin._view_states), 1)
        _Toplevel.toplevels = []
        plugin._fit_columns()
        self.assertEqual(plugin._view_states, {})


class DescFontTests(unittest.TestCase):
    def setUp(self):
        _Toplevel.toplevels = []
        _StyleContext.added = []
        plugin._view_states.clear()
        plugin._css_done = False

    def view(self, desc_visible=True):
        columns = [_ColumnViewColumn('name'),
                   _ColumnViewColumn(plugin.COLUMN, visible=desc_visible),
                   _ColumnViewColumn('size')]
        rows = [_Widget([_NautilusNameCell('abc'), _NautilusLabelCell('desc')])]
        view = _ColumnView(columns, children=[_Widget(rows)],
                           model=_ViewRowModel(['abc']))
        _Toplevel.toplevels = [_Toplevel([view])]
        return view

    def test_css_rules_target_each_visible_position(self):
        self.view()
        plugin._fit_columns()
        self.assertEqual(len(_StyleContext.added), 1)
        text = _StyleContext.added[0].text
        self.assertIn('nth-child(2)', text)
        self.assertIn(plugin.DESC_FONT_SCALE, text)
        self.assertIn('row > cell', text)

    def test_css_is_installed_once(self):
        self.view()
        plugin._fit_columns()
        plugin._fit_columns()
        self.assertEqual(len(_StyleContext.added), 1)

    def test_view_gets_the_class_for_the_desc_position(self):
        view = self.view()
        plugin._fit_columns()
        self.assertTrue(view.has_css_class('nautilus-folder-yaml-2'))

    def test_class_follows_a_reordered_column(self):
        view = self.view()
        plugin._fit_columns()
        columns = view.get_columns()
        columns.insert(0, columns.pop(1))
        plugin._fit_columns()
        self.assertTrue(view.has_css_class('nautilus-folder-yaml-1'))
        self.assertFalse(view.has_css_class('nautilus-folder-yaml-2'))

    def test_hidden_desc_column_removes_the_class(self):
        view = self.view(desc_visible=False)
        plugin._fit_columns()
        self.assertFalse(view.has_css_class('nautilus-folder-yaml-1'))
        self.assertFalse(view.has_css_class('nautilus-folder-yaml-2'))


class ApplyTests(FolderTestCase):
    def item(self, name='notes.txt'):
        return _FileInfo('file://' + os.path.join(self.folder.temp.name, name),
                         directory=False)

    def touch(self, name):
        (self.folder.path / name).write_text('', encoding='utf-8')
        plugin._cache.clear()

    def test_desc_becomes_the_attribute(self):
        self.folder.write('desc: 项目\n')
        folder = _FileInfo('file://' + self.folder.temp.name)
        plugin._apply(folder)
        self.assertEqual(folder.attributes.get('desc'), '项目')

    def test_file_value_becomes_the_attribute(self):
        self.touch('notes.txt')
        self.folder.write('file-desc:\n  notes.txt: 会议记录\n')
        item = self.item()
        plugin._apply(item)
        self.assertEqual(item.attributes.get('desc'), '会议记录')

    def test_file_without_value_gets_none(self):
        self.folder.write('desc: 项目\n')
        item = self.item()
        plugin._apply(item)
        self.assertNotIn('desc', item.attributes)

    def test_switch_off_hides_everything(self):
        self.touch('notes.txt')
        self.folder.write('desc: 项目\nfile-desc:\n  notes.txt: 会议记录\n')
        plugin._save_state(enabled=False)
        self.addCleanup(plugin._save_state, enabled=True)
        item = self.item()
        plugin._apply(item)
        self.assertNotIn('desc', item.attributes)

    def test_removed_value_clears_a_shown_one(self):
        self.touch('notes.txt')
        self.folder.write('file-desc:\n  notes.txt: 会议记录\n')
        item = self.item()
        plugin._apply(item)
        self.folder.write('desc: 项目\n')
        plugin._apply(item)
        self.assertEqual(item.attributes.get('desc'), '')

    def test_entry_whose_file_is_gone_is_dropped(self):
        self.touch('here.txt')
        self.folder.write('desc: 项目\nfile-desc:\n  gone.txt: 会议记录\n  here.txt: 备注\n')
        plugin._apply(self.item('here.txt'))
        self.assertEqual(self.folder.read(),
                         'desc: 项目\nfile-desc:\n  here.txt: 备注\n')


def _xattrs_supported(directory):
    probe = Path(directory) / 'xattr-probe'
    probe.write_text('', encoding='utf-8')
    try:
        os.setxattr(str(probe), 'user.nautilus-folder-yaml.probe', b'x')
        os.removexattr(str(probe), 'user.nautilus-folder-yaml.probe')
    except OSError:
        return False
    return True


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.here = tempfile.TemporaryDirectory()
        self.addCleanup(self.here.cleanup)
        if not _xattrs_supported(self.here.name):
            self.skipTest('filesystem does not support user xattrs')
        self.there = tempfile.TemporaryDirectory()
        self.addCleanup(self.there.cleanup)
        plugin._cache.clear()
        plugin._shown.clear()
        self.addCleanup(plugin._cache.clear)
        self.addCleanup(plugin._shown.clear)

    def yaml_text(self, folder):
        path = Path(folder) / plugin.YAML_NAME
        return path.read_text(encoding='utf-8') if path.exists() else ''

    def touch(self, folder, name):
        path = Path(folder) / name
        path.write_text('', encoding='utf-8')
        plugin._cache.clear()
        return str(path)

    def item(self, path):
        return _FileInfo('file://' + path, directory=False)

    def annotate(self, folder, name, text):
        path = self.touch(folder, name)
        plugin._set_file_desc(folder, name, text)
        plugin._apply(self.item(path))
        return path

    def test_value_leaves_a_token_on_the_file(self):
        path = self.annotate(self.here.name, 'notes.txt', '会议记录')
        self.assertEqual(plugin._token(path), {
            'folder': self.here.name, 'name': 'notes.txt', 'desc': '会议记录',
        })

    def test_value_follows_a_rename_in_place(self):
        path = self.annotate(self.here.name, 'notes.txt', '会议记录')
        renamed = os.path.join(self.here.name, 'renamed.txt')
        os.rename(path, renamed)
        plugin._cache.clear()

        item = self.item(renamed)
        plugin._apply(item)

        self.assertEqual(item.attributes.get('desc'), '会议记录')
        self.assertEqual(self.yaml_text(self.here.name),
                         'file-desc:\n  renamed.txt: 会议记录\n')
        self.assertEqual(plugin._token(renamed), {
            'folder': self.here.name, 'name': 'renamed.txt', 'desc': '会议记录',
        })

    def test_value_follows_a_move_to_another_folder(self):
        path = self.annotate(self.here.name, 'notes.txt', '会议记录')
        moved = os.path.join(self.there.name, 'notes.txt')
        os.rename(path, moved)
        plugin._cache.clear()

        item = self.item(moved)
        plugin._apply(item)

        self.assertEqual(item.attributes.get('desc'), '会议记录')
        self.assertEqual(self.yaml_text(self.there.name),
                         'file-desc:\n  notes.txt: 会议记录\n')

        # 原文件夹下次读元数据时清掉失效条目
        plugin._read(self.here.name)
        self.assertEqual(self.yaml_text(self.here.name), '')

    def test_hand_deleted_entry_is_not_resurrected(self):
        path = self.annotate(self.here.name, 'notes.txt', '会议记录')
        plugin._del_file_desc(self.here.name, 'notes.txt')
        plugin._cache.clear()

        item = self.item(path)
        plugin._apply(item)

        self.assertEqual(item.attributes.get('desc', ''), '')
        self.assertIsNone(plugin._token(path))
        self.assertNotIn('notes.txt', self.yaml_text(self.here.name))

    def test_yaml_wins_over_a_stale_token(self):
        path = self.annotate(self.here.name, 'notes.txt', '会议记录')
        plugin._set_token(path, self.here.name, 'notes.txt', '旧文本')
        plugin._apply(self.item(path))
        self.assertEqual(plugin._token(path)['desc'], '会议记录')


if __name__ == '__main__':
    unittest.main()
