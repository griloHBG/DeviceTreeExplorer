import argparse
import re
from functools import partial
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty, ListProperty, NumericProperty, AliasProperty
from kivy.uix.accordion import AccordionItem
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from TextInputLineNumber.textinputlinenumber import TextInputLineNumber
from find_in_devicetree.find_in_dt import find_in_dt, MyRepository, SearchHit, get_repository, get_architecture
from pastel_colors_dark import SearchHitPastelColor
from kivy.utils import get_color_from_hex


class DeletionDropdownItem(BoxLayout):

    text = StringProperty("")
    color = ListProperty([])
    #delete_callback = None
    undeletable = False
    child_list = None

    def __init__(self, text, color, **kwargs):
        if 'undeletable' in kwargs:
            self.undeletable = kwargs['undeletable']
            kwargs.pop('undeletable')
        super(DeletionDropdownItem, self).__init__(**kwargs)

        self.text = text
        if isinstance(color, list):
            self.color = color
        elif isinstance(color, str):
            self.color = get_color_from_hex(color)
        else:
            raise TypeError(f"Color ({color}) should be a list ([.7,.8,1]) or a string (#789ABC)")
        self.register_event_type('on_delete')

    def on_delete(self, *args):
        print(self.text, self.color, 'on_delete event')

    def delete_me(self):
        self.dispatch('on_delete')
        if not self.child_list == None:
            for child in self.child_list:
                child.parent.remove_widget(child)
        if not self.undeletable:
            self.parent.remove_widget(self)

    def set_child_list(self, child_list):
        self.child_list = child_list

class DeletionChooser(Button):

    item_height = 44

    def __init__(self, **kwargs):
        super(DeletionChooser, self).__init__(**kwargs)
        self.dropdown:DropDown = DropDown()
        self.all_button = DeletionDropdownItem('All',
                                               '#777777',
                                               undeletable=True,
                                               size_hint_y=None,
                                               height=self.item_height)
        self.all_button.bind(on_delete = self.clear_list)
        self.dropdown.add_widget(self.all_button)
        self.register_event_type('on_delete')
        self.deletion_pack_callback = lambda obj: None

    def set_deletion_pack_callback(self, deletion_pack_callback):
        self.deletion_pack_callback = deletion_pack_callback
        self.all_button.bind(on_delete=self.deletion_pack_callback)

    def update(self, search_history:dict):
        import pprint
        pprint.pprint(search_history, width=10)

        self.clear_list()

        for big_search_index, data in search_history.items():
            ddi = DeletionDropdownItem(data['search_string'],
                                       data['color'],
                                       size_hint_y=None,
                                       height=self.item_height)
            ddi.set_child_list(data['hits'])
            ddi.bind(on_delete=self.deletion_pack_callback)
            self.dropdown.add_widget(ddi)

    def on_delete(self, drop_down_item:DeletionDropdownItem):
        pass

    def clear_list(self,ins:DeletionDropdownItem=None):
        self.dropdown.clear_widgets()
        self.dropdown.add_widget(self.all_button)
        print("all deleted")

class PathProperty(AliasProperty):

    path:Path

    def __init__(self, path=None):
        super(PathProperty, self).__init__(PathProperty.getter, PathProperty.setter)
        if isinstance(path, Path):
            self.path = path
        elif isinstance(path, str):
            self.path = Path(path)
        elif path == None:
            self.path = Path()
        else:
            raise TypeError(f'path ({path}) is instance of {type(path)}, but should by None or of type Path or type str')

    def getter(self):
        return self.path

    def setter(self, path:Path):
        self.path = path

    def __eq__(self, other):
        if isinstance(other, Path):
            return self.path == other
        elif isinstance(other, str):
            return str(self.path) == other
        else:
            raise TypeError(f'comparing self to {other}, which is instance of {type(other)}, but should of type Path or type str')

class InFileResult(BoxLayout):
    load_search_hit = ObjectProperty(None)
    dts_file = PathProperty()
    line_number = NumericProperty(0)
    search_string = StringProperty('')
    selection_start = NumericProperty(0)
    selection_end = NumericProperty(0)

    def __init__(self):
        super(InFileResult, self).__init__()

class SearchResult(AccordionItem):
    container = ObjectProperty(None)
    dts_path = PathProperty()
    title_background_hex_color = StringProperty("#EEEEEE")

    def __init__(self, deletion_callback, search_string, hex_color, big_search_index):
        super(SearchResult, self).__init__(title_args={"background_color":self.title_background_hex_color})
        self.search_string = search_string
        self.color = hex_color
        self.title_args["background_color"] = self.color
        self.big_search_index = big_search_index
        if callable(deletion_callback):
            self.deletion_callback = deletion_callback
        else:
            raise TypeError("deletion_callback should be callable!")

    def add_result(self, widget):
        self.container.add_widget(widget)

    def set_title_background_color(self, hex_color):
        self.color = hex_color
        self.title_args["background_color"] = self.color

    def delete_me(self):
        self.deletion_callback(self)

class DTSChooser(Popup):

    selected_file = ObjectProperty(None)
    set_dts_file = ObjectProperty(None)
    filter = ObjectProperty(None)
    file_search_string = StringProperty('')
    file_chooser = ObjectProperty(None)

    def select(self, selection_list):
        if selection_list == []:
            self.selected_file.color = 'FF3333'
        else:
            self.set_dts_file(selection_list[0])
            self.dismiss()

    def cancel(self):
        self.dismiss()

    def my_filter(self, search_string, folder, file_name):
        if search_string == '':
            search_string = '.+'
        try:
            result = re.search(search_string, file_name)
            return result != None
        except re.error as e:
            return False

    def do_filter(self):
        try:
            re_search = re.compile(self.filter.text)
        except re.error as e:
            error_text = str(e).capitalize()
            error_popup = Popup(title="Filter Error", content=Label(text=f'Regular Expression error:\n\n{error_text}'), size_hint=(.5,.5))
            error_popup.open()
            print(e)
            return
        self.file_search_string=self.filter.text
        self.file_chooser.filters=[partial(self.my_filter, self.file_search_string)];

class DeviceTreeExplorerRoot(BoxLayout):
    dts_file = PathProperty()
    file_content = StringProperty('')

    source_branch = StringProperty('')
    architecture = StringProperty('')

    textinputlinenumber = ObjectProperty(None)
    txt_big_search = ObjectProperty(None)

    git = None

    little_search_result = ListProperty([])
    little_search_result_amount = NumericProperty(0)
    little_search_result_idx = NumericProperty(0)

    previous_search_string = StringProperty('')

    deletion_chooser = ObjectProperty(None)

    big_search_counter = 0

    search_history = {}
    # ├─ {0:
    # |   ├─ {search_string1: 'asd',
    # |   ├─ color:'#FFFFFF',
    # |   └─ hits:[hit1, hit2, hit3, ...]},
    # ├─ {1:
    # |   ├─ {search_string1: 'asd',
    # |   ├─ color:'#FFFFFF',
    # |   └─ hits:[hit1, hit2, hit3, ...]},
    # ...}

    def __init__(self, dts, **kwargs):
        super(DeviceTreeExplorerRoot, self).__init__(**kwargs)
        self.set_dts_file(dts)
        self.select_dts_popup = DTSChooser()
        self.deletion_chooser.set_deletion_pack_callback(self.deletion_pack_callback)
        Clock.schedule_once(self.scroll_up)

    def scroll_up(self, dt):
        self.textinputlinenumber.do_cursor_movement('cursor_home', control=True)

    def big_search(self):
        if self.txt_big_search.text == "" or self.txt_big_search.text == ".+":
            return
        try:
            findings, searched_files = find_in_dt(Path(self.dts_file), [self.txt_big_search.text])
        except LookupError as e:
            print(str(e))
            return

        if len(findings) > 0:

            color = SearchHitPastelColor.get_hex_color()

            self.search_history[self.big_search_counter] = {'search_string':self.txt_big_search.text,
                                                            'color':color,
                                                            'hits':[]}

            for f in findings:
                r = SearchResult(partial(self.deletion_callback), self.txt_big_search.text, color, self.big_search_counter)
                r.title=f'{self.txt_big_search.text} : {f.file_name.name} [{len(f.to_dict()["hits"].items())} hits]'
                r.dts_path = f.file_name

                self.search_history[self.big_search_counter]['hits'].append(r)

                for line, [before, hit, after, hit_start, hit_end] in f.to_dict()['hits'].items():
                    ifresult = InFileResult()
                    ifresult.text=str(before+'[color=33dd33]'+hit+'[/color]'+after).strip()
                    ifresult.line_number=line
                    ifresult.dts_file = f.file_name
                    ifresult.load_search_hit = self.load_search_hit
                    ifresult.selection_start = hit_start
                    ifresult.selection_end = hit_end
                    r.add_result(ifresult)

                self.accordion_result.add_widget(r)

            self.deletion_chooser.update(self.search_history)

            self.big_search_counter+=1

    def deletion_callback(self, search_result:SearchResult):
        big_search_index = search_result.big_search_index
        self.search_history[big_search_index]['hits'].remove(search_result)
        if len(self.search_history[big_search_index]['hits']) == 0:
            self.search_history.pop(big_search_index)
        search_result.parent.remove_widget(search_result)
        self.deletion_chooser.update(self.search_history)

    def deletion_pack_callback(self, drop_down_item:DeletionDropdownItem):
        if not drop_down_item.undeletable:
            search_result:SearchResult
            big_search_index = drop_down_item.child_list[0].big_search_index
            search_string = self.search_history[big_search_index]['search_string']
            color = self.search_history[big_search_index]['color']
            while len(drop_down_item.child_list) > 0:
                aux = drop_down_item.child_list[0]
                self.search_history[big_search_index]['hits'].remove(aux)
                aux.parent.remove_widget(aux)

            if len(self.search_history[big_search_index]['hits']) == 0:
                self.search_history.pop(big_search_index)
            else:
                raise RuntimeError(f'Hits list of big_search_history {big_search_index} ({search_string}, {color}) should be empty but is not!')
        else:
            current_big_search_idx = 0
            all_indexes = list(self.search_history.keys())
            for index in all_indexes:
                hits = self.search_history[index]['hits']
                while len(hits) > 0:
                    aux = hits[0]
                    hits.remove(aux)
                    aux.parent.remove_widget(aux)
                self.search_history.pop(index)



    def load_search_hit(self, dts_file, line_number, selection_start, selection_end):
        self.set_dts_file(dts_file)
        self.textinputlinenumber.go_to_line(line_number)
        self.textinputlinenumber.cursor = self.textinputlinenumber.get_cursor_from_index(selection_start)
        self.textinputlinenumber.select_text(selection_start, selection_end)

    def set_dts_file(self, dts_file):
        if isinstance(dts_file, str):
            dts_file = Path(dts_file)
        if not self.dts_file == dts_file:
            self.dts_file = dts_file
            try:
                self.git = get_repository(self.dts_file)
            except LookupError as e:
                print(str(e))
            try:
                self.source_branch = str(self.git.active_branch)
            except:
                self.source_branch = "No branch"

            try:
                self.architecture = get_architecture(self.dts_file)
            except:
                print(f'file {self.dts_file} doesn\'t define an architecture. we\'re keeping the same architecture: {self.architecture}.')
            with open(self.dts_file) as d:
                self.file_content = d.read()
        self.little_search_result = []

    def little_search(self, search_string):
        start = end = 0
        if search_string != '':
            if search_string == self.previous_search_string and not self.little_search_result == []:
                self.little_search_result_idx = (self.little_search_result_idx+1)%self.little_search_result_amount
                start, end = self.little_search_result[self.little_search_result_idx].span()
                self.textinputlinenumber.select_text(start, end)
                self.textinputlinenumber.cursor = self.textinputlinenumber.get_cursor_from_index(start)
                return
            else:
                result = list(re.finditer(search_string, self.textinputlinenumber.text))
                if result:
                    self.little_search_result = result
                    self.little_search_result_idx = 0
                    self.little_search_result_amount = len(result)

                    for result in self.little_search_result:
                        start = self.little_search_result[self.little_search_result_idx].span()[0]
                        if self.textinputlinenumber.cursor_index() > start:
                            self.little_search_result_idx += 1
                    self.little_search_result_idx %= self.little_search_result_amount

                    start, end = self.little_search_result[self.little_search_result_idx].span()

                    self.textinputlinenumber.select_text(start, end)
                    self.textinputlinenumber.cursor = self.textinputlinenumber.get_cursor_from_index(start)
                else:
                    self.little_search_result = []
                    self.little_search_result_idx = 0
                    self.little_search_result_amount = 0

                self.previous_search_string = search_string

class DeviceTreeExplorerApp(App):
    dts_file = PathProperty()

    def __init__(self, dts, **kwargs):
        super(DeviceTreeExplorerApp, self).__init__(**kwargs)
        self.dts_file = dts

    def build(self):
        return DeviceTreeExplorerRoot(self.dts_file)


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description="Device Tree Explorer to make your life easier :)")
    arg_parser.add_argument('device_tree_source_file', type=Path, help="Relative or absolute path to a device "
                                                                              "tree source file")

    args = arg_parser.parse_args()

    dts_file = args.device_tree_source_file

    if not dts_file.exists():
        print(f'{dts_file} não existe!')
        exit(1)

    dts_explorer = DeviceTreeExplorerApp(dts_file)
    dts_explorer.run()
