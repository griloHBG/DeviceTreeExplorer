from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button

class DeviceTreeExplorerRoot(BoxLayout):
    pass

class DeviceTreeExplorerApp(App):
    def build(self):
        return DeviceTreeExplorerRoot()

DeviceTreeExplorerApp().run()