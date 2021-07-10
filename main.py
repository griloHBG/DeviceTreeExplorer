import argparse
import re
from functools import partial
from pathlib import Path

from colorit import color, Colors
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty, ListProperty, NumericProperty, AliasProperty
from kivy.uix.accordion import AccordionItem
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.stacklayout import StackLayout

from TextInputLineNumber.textinputlinenumber import TextInputLineNumber
from find_in_devicetree.find_in_dt import find_in_dt, MyRepository, SearchHit, get_repository, get_architecture

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

    def add_result(self, widget):
        self.container.add_widget(widget)

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
        print(file_name)
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
        print(self.file_chooser.filters)

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

    def __init__(self, dts, **kwargs):
        super(DeviceTreeExplorerRoot, self).__init__(**kwargs)
        self.set_dts_file(dts)
        self.select_dts_popup = DTSChooser()
        Clock.schedule_once(self.scroll_up)

    def scroll_up(self, dt):
        self.textinputlinenumber.do_cursor_movement('cursor_home', control=True)

    def big_search(self):
        print(self.dts_file, self.txt_big_search.text)
        try:
            findings, searched_files = find_in_dt(Path(self.dts_file), [self.txt_big_search.text])
        except LookupError as e:
            print(str(e))
            return

        # print('findings:')

        for f in findings:
            r = SearchResult()
            r.title=f'{self.txt_big_search.text} : {f.file_name.name} [{len(f.to_dict()["hits"].items())} hits]'
            r.dts_path = f.file_name
            # print(color(f.file_name,Colors.purple))
            for line, [before, hit, after, hit_start, hit_end] in f.to_dict()['hits'].items():
                ifresult = InFileResult()
                ifresult.text=str(before+'[color=33dd33]'+hit+'[/color]'+after).strip()
#                ifresult.text=str(before+hit+after).strip()
                ifresult.line_number=line
                ifresult.dts_file = f.file_name
                ifresult.load_search_hit = self.load_search_hit
                ifresult.selection_start = hit_start
                ifresult.selection_end = hit_end
                r.add_result(ifresult)
                # print('\t',color(line, Colors.red),' : ', before, color(hit,Colors.green), after, sep='')

            # print()
            self.accordion_result.add_widget(r)

    def load_search_hit(self, dts_file, line_number, selection_start, selection_end):
        print(f'dts_file {dts_file}\nline_number {line_number}\nselection_start {selection_start}\nselection_end {selection_end}')
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
                    # print(result)
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

    print(dts_file)

    if dts_file.exists():
        print(f'{dts_file} existe!')
    else:
        print(f'{dts_file} não existe!')

    dts_explorer = DeviceTreeExplorerApp(dts_file)
    dts_explorer.run()
