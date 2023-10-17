import threading

import flet as ft

from switchpokepilot.camera import Camera
from switchpokepilot.state import AppState, AppStateObserver

DISABLED_IMAGE = "/images/disabled.png"


class GameScreen(ft.UserControl, AppStateObserver):
    def __init__(self, app_state: AppState):
        super().__init__()
        self.screen: ft.Image | None = None
        self.app_state = app_state

        # for camera
        self.camera = self.app_state.camera

        # for loop
        self.__thread: threading.Thread | None = None

    @property
    def camera(self) -> Camera | None:
        return self._get_attr("camera")

    @camera.setter
    def camera(self, new_value: Camera, dirty=True):
        self._set_attr("camera", new_value, dirty)

    def did_mount(self):
        self.app_state.add_observer(self)
        self.__prepare_camera()

    def will_unmount(self):
        self.app_state.delete_observer(self)
        self.__release_camera()

    def __prepare_camera(self):
        self.camera.open()
        self.__thread = threading.Thread(target=self.__loop_update_screen,
                                         name=f"{GameScreen.__name__}:{self.__loop_update_screen.__name__}",
                                         daemon=True)
        self.__thread.start()

    def __release_camera(self):
        self.camera.destroy()
        self.__thread.join()
        self.__thread = None

    def __loop_update_screen(self):
        while self.camera.is_opened():
            self.camera.read_frame()
            encoded = self.camera.encoded_current_frame_base64()
            if encoded == "":
                self.screen.src = DISABLED_IMAGE
                self.screen.src_base64 = None
            else:
                self.screen.src = None
                self.screen.src_base64 = encoded
            self.update()

    def build(self):
        self.screen = ft.Image(
            src=DISABLED_IMAGE,
            fit=ft.ImageFit.COVER,
            width=self.camera.capture_size[0],
            height=self.camera.capture_size[1],
        )
        return self.screen

    def on_app_state_update(self, subject: AppState) -> None:
        if self.camera != subject.camera:
            self.camera = subject.camera
            self.__release_camera()
            self.__prepare_camera()
        self.update()
