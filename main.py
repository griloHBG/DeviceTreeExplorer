import argparse
import pathlib

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from TextInputLineNumber.textinputlinenumber import TextInputLineNumber


class DeviceTreeExplorerRoot(BoxLayout):
    dts_file = StringProperty('')
    file_content = StringProperty('')

    source_branch = StringProperty('toradex_5.4.y')
    architecture = StringProperty('arm')

    textinputlinenumber = ObjectProperty(None)

    def __init__(self, dts, **kwargs):
        super(DeviceTreeExplorerRoot, self).__init__(**kwargs)
        self.dts_file = str(dts)
        with open(self.dts_file) as d:
            self.file_content = d.read()
        Clock.schedule_once(self.scroll_up)

    def scroll_up(self, dt):
        self.textinputlinenumber.do_cursor_movement('cursor_home', control=True)


class DeviceTreeExplorerApp(App):
    dts_file = StringProperty('')

    def __init__(self, dts, **kwargs):
        super(DeviceTreeExplorerApp, self).__init__(**kwargs)
        self.dts_file = str(dts)

    def build(self):
        return DeviceTreeExplorerRoot(self.dts_file)


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description="Device Tree Explorer to make your life easier :)")
    arg_parser.add_argument('device_tree_source_file', type=pathlib.Path, help="Relative or absolute path to a device "
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
