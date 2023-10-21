from switchpokepilot.core.command.base import Command
from switchpokepilot.core.controller.controller import (
    Controller,
    Button,
    StickDisplacementPreset as Displacement,
)


class ControllerUtils:
    def __init__(self, controller: Controller):
        self.controller = controller

    def get_recognition(self, buttons: list[Button]):
        self.controller.send_repeat(buttons=buttons,
                                    count=3,
                                    duration=0.05,
                                    interval=0.8,
                                    skip_last_interval=False)

    def time_leap(self,
                  command: Command,
                  years: int = 0,
                  months: int = 0,
                  days: int = 0,
                  hours: int = 0,
                  minutes: int = 0,
                  toggle_auto=False,
                  with_reset=False):
        # Goto Home
        self.controller.send_one_shot(buttons=[Button.HOME])
        self.controller.wait(1)

        if not command.should_keep_running:
            return

        # Goto System Settings
        self.controller.send_one_shot(l_displacement=Displacement.DOWN)
        self.controller.send_repeat(l_displacement=Displacement.RIGHT,
                                    count=5)
        self.controller.send_one_shot(buttons=[Button.A])
        self.controller.wait(1.5)

        if not command.should_keep_running:
            return

        # Goto System
        self.controller.send_one_shot(l_displacement=Displacement.DOWN,
                                      duration=2)
        self.controller.wait(0.3)
        self.controller.send_one_shot(buttons=[Button.A])
        self.controller.wait(0.2)

        if not command.should_keep_running:
            return

        # Goto Date and Time
        self.controller.send_one_shot(l_displacement=Displacement.DOWN,
                                      duration=0.7)
        self.controller.wait(0.2)
        self.controller.send_one_shot(buttons=[Button.A])
        self.controller.wait(0.2)

        if not command.should_keep_running:
            return

        if with_reset:
            self.controller.send_one_shot(buttons=[Button.A])
            self.controller.wait(0.2)
            self.controller.send_one_shot(buttons=[Button.A])
            self.controller.wait(0.2)

        if not command.should_keep_running:
            return

        # Toggle auto clock
        if toggle_auto:
            self.controller.send_one_shot(buttons=[Button.A])
            self.controller.wait(0.2)

        if not command.should_keep_running:
            return

        # Goto Current Date and Time
        self.controller.send_repeat(l_displacement=Displacement.DOWN,
                                    count=2)
        self.controller.send_one_shot(buttons=[Button.A])
        self.controller.wait(0.2)

        if not command.should_keep_running:
            return

        def change(diff: int):
            if diff < 0:
                self.controller.send_repeat(l_displacement=Displacement.DOWN,
                                            count=-diff)
            else:
                self.controller.send_repeat(l_displacement=Displacement.UP,
                                            count=diff)
            self.controller.send_one_shot(l_displacement=Displacement.RIGHT)

        # change datetime
        change(years)
        change(months)
        change(days)
        change(hours)
        change(minutes)

        # confirm datetime
        self.controller.send_one_shot(buttons=[Button.A])
