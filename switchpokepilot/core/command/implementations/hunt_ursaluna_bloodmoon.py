import datetime
from configparser import ConfigParser
from dataclasses import dataclass
from distutils.util import strtobool

from switchpokepilot import config
from switchpokepilot.core.command.base import Command, CommandInitParams
from switchpokepilot.core.command.utils import CommandUtils, CropRegionUtils, CropRegionPreset
from switchpokepilot.core.controller.button import Button
from switchpokepilot.core.controller.stick import StickDisplacementPreset as Displacement
from switchpokepilot.core.image.image import Image
from switchpokepilot.core.image.region import ImageRegion
from switchpokepilot.core.logger.logger import Logger

CONFIG_BASE_SECTION = "command.hunt_ursaluna_bloodmoon"


class HuntUrsalunaBloodmoon(Command):
    NAME = "ガチグマ(アカツキ)厳選"

    def __init__(self, params: CommandInitParams):
        super().__init__(params=params)
        self.generation = "9"
        self.utils = CommandUtils(command=self)
        self.config: HuntUrsalunaBloodmoonConfig | None = None

    def process(self):
        try:
            # Initialize
            self.utils.start_timer()
            self.utils.reload_config()

            # Parse config
            self.config = HuntUrsalunaBloodmoonConfig(config)
            is_config_valid = self.config.validate(logger=self.logger)
            if not is_config_valid:
                return

            # Main loop
            while self.should_keep_running:
                self.utils.increment_attempts()
                self._log_command_status()

                self._send_repeat_a_until_battle_start()
                self._wait_for_command_appear()
                self._send_attack_command()

                # Check speed
                if self.config.status.should_check_speed and self._detect_ursaluna_preemptive_attack():
                    restart_succeeded = self.utils.restart_sv()
                    if not restart_succeeded:
                        return
                    continue
                else:
                    self._wait_for_battle_finish()

                self._catch_ursaluna()
                self._skip_pokedex()

                # Check status
                self._goto_status_screen()
                achieved = self._check_ursaluna_status()
                if achieved:
                    self.logger.info(f"{self.NAME} finished.")
                    self._log_command_status()
                    return

                restart_succeeded = self.utils.restart_sv()
                if not restart_succeeded:
                    return

        finally:
            self.utils.stop_timer()
            self.finish()

    def postprocess(self):
        self.utils = None
        super().postprocess()

    def _send_repeat_a_until_battle_start(self):
        height, width, _ = self.camera.current_frame.shape
        capture_region = ImageRegion(x=(0.28, 0.45), y=(0.76, 0.82))
        template = self._template_path("voice.png")
        threshold = self.config.template_matching.battle_started
        while not self._detect_battle_started(capture_region=capture_region,
                                              template_path=template,
                                              threshold=threshold):
            self.controller.send_one_shot(buttons=[Button.A],
                                          duration=0.05)
            self.wait(0.05)

    def _wait_for_command_appear(self):
        height, width, _ = self.camera.current_frame.shape
        capture_region = ImageRegion(x=(0.76, 0.83), y=(0.82, 0.98))
        template_path = self._template_path("battle_command.png")
        threshold = self.config.template_matching.command_appeared
        while not self._detect_battle_command_appeared(capture_region=capture_region,
                                                       template_path=template_path,
                                                       threshold=threshold):
            self.wait(0.5)
        self.wait(1)

    def _send_attack_command(self):
        self.controller.send_repeat(buttons=[Button.A],
                                    count=2,
                                    duration=0.05,
                                    interval=0.8)
        self.wait(1.7)

    def _wait_for_battle_finish(self):
        # ターン経過待機
        self.wait(36.5)
        # 撃破後演出待機
        self.wait(16.5)

    def _detect_battle_started(self,
                               capture_region: ImageRegion,
                               template_path: str,
                               threshold: float) -> bool:
        image = self.camera.get_current_frame(region=capture_region)
        template = Image.from_file(template_path)
        return image.contains(other=template, threshold=threshold)

    def _detect_battle_command_appeared(self,
                                        capture_region: ImageRegion,
                                        template_path: str,
                                        threshold: float) -> bool:
        image = self.camera.get_current_frame(region=capture_region)
        template = Image.from_file(template_path)
        return image.contains(other=template, threshold=threshold)

    def _detect_ursaluna_preemptive_attack(self) -> bool:
        height, width, _ = self.camera.current_frame.shape
        capture_region = ImageRegion(x=(0.15, 0.34), y=(0.72, 0.79))
        image = self.camera.get_current_frame(region=capture_region)
        threshold = self.config.template_matching.ursaluna_attacked_preemptive
        template = Image.from_file(self._template_path("ursaluna_attack.png"))
        return image.contains(other=template, threshold=threshold)

    def _catch_ursaluna(self):
        # 捕まえるを選択
        self.controller.send_one_shot(buttons=[Button.A],
                                      duration=0.05)
        self.wait(0.6)

        displacement_for_select_ball = Displacement.RIGHT
        if self.config.ball_index_seek_direction == "Left":
            displacement_for_select_ball = Displacement.LEFT

        # ボールを選択して投げる
        self.controller.send_repeat(l_displacement=displacement_for_select_ball,
                                    count=self.config.ball_index,
                                    duration=0.05,
                                    interval=0.3,
                                    skip_last_interval=False)
        self.controller.send_one_shot(buttons=[Button.A],
                                      duration=0.05)
        # 演出待機
        self.wait(20)

    def _skip_pokedex(self):
        if not self.config.pokedex_registered:
            self.controller.send_one_shot(buttons=[Button.A],
                                          duration=0.05)
            self.wait(1.05)

    def _goto_status_screen(self):
        self.controller.send_one_shot(l_displacement=Displacement.BOTTOM)
        self.controller.send_one_shot(buttons=[Button.A])
        self.wait(1)
        self.controller.send_one_shot(l_displacement=Displacement.RIGHT)
        self.wait(0.5)
        if self.config.status.should_save_screenshot:
            self.camera.save_capture()

    def _check_ursaluna_status(self) -> bool:
        if self.config.status.should_check_speed:
            return (self._check_ursaluna_attack_actual_value() and
                    self._check_ursaluna_speed_actual_value())
        else:
            return self._check_ursaluna_attack_actual_value()

    def _check_ursaluna_attack_actual_value(self) -> bool:
        height, width, _ = self.camera.current_frame.shape
        capture_region = CropRegionUtils.calc_region(key=CropRegionPreset.STATUS_A)
        image = self.camera.get_current_frame(region=capture_region)
        threshold = self.config.template_matching.actual_value
        contains_10 = image.contains(other=Image.from_file(self._template_path("10.png")), threshold=threshold)
        contains_3 = image.contains(other=Image.from_file(self._template_path("3.png")), threshold=threshold)
        return contains_10 and contains_3

    def _check_ursaluna_speed_actual_value(self) -> bool:
        height, width, _ = self.camera.current_frame.shape
        capture_region = CropRegionUtils.calc_region(key=CropRegionPreset.STATUS_S)
        image = self.camera.get_current_frame(region=capture_region)
        threshold = self.config.template_matching.actual_value

        template_file = "77.png"
        template_path = self._template_path(template_file)
        template = Image.from_file(template_path)
        contains_77 = image.contains(other=template, threshold=threshold)
        if self.config.status.speed_individual_value == 0:
            return contains_77

        template_file = "78.png"
        template_path = self._template_path(template_file)
        template = Image.from_file(template_path)
        contains_78 = image.contains(other=template, threshold=threshold)
        return contains_77 or contains_78

    def _log_command_status(self):
        elapsed = self.utils.elapsed_time
        self.logger.info(f"現在時刻: {datetime.datetime.now()}")
        self.logger.info(f"試行回数: {self.utils.attempts}回目")
        self.logger.info(f"経過時間: {elapsed.hours}時間{elapsed.minutes}分{elapsed.seconds}秒")

    @staticmethod
    def _template_path(file: str):
        return f"hunt_ursaluna_bloodmoon/{file}"


class HuntUrsalunaBloodmoonConfig:
    def __init__(self, parser: ConfigParser):
        base_section = parser[CONFIG_BASE_SECTION]
        self.ball_index_seek_direction = base_section["BallIndexSeekDirection"]
        self.ball_index = int(base_section["BallIndex"])
        self.pokedex_registered = strtobool(base_section["PokedexRegistered"])

        status_section = parser[f"{CONFIG_BASE_SECTION}.status"]
        self.status = StatusConfig(
            should_check_speed=bool(strtobool(status_section["ShouldCheckSpeed"])),
            should_check_status=bool(strtobool(status_section["ShouldCheckStatus"])),
            should_save_screenshot=bool(strtobool(status_section["ShouldSaveScreenshot"])),
            attack_individual_value=int(status_section["AttackIndividualValue"]),
            speed_individual_value=int(status_section["SpeedIndividualValue"]),
        )

        template_matching_section = parser[f"{CONFIG_BASE_SECTION}.template_matching"]
        self.template_matching = TemplateMatchingThresholdConfig(
            battle_started=float(template_matching_section["BattleStarted"]),
            command_appeared=float(template_matching_section["CommandAppeared"]),
            ursaluna_attacked_preemptive=float(template_matching_section["UrsalunaAttackedPreemptive"]),
            actual_value=float(template_matching_section["ActualValue"]),
            individual_value=float(template_matching_section["IndividualValue"]),
        )

    def validate(self, logger: Logger) -> bool:
        if self.ball_index_seek_direction not in ["Right", "Left"]:
            logger.error("Invalid BallIndexSeekDirection: required Right or Left")
            return False

        if self.ball_index < 0:
            logger.error("Invalid BallIndex: require BallIndex >= 0")
            return False

        if self.status.attack_individual_value not in [0, 1]:
            logger.error("Invalid AttackIndividualValue: 0 or 1")
            return False

        if self.status.speed_individual_value not in [0, 1]:
            logger.error("Invalid SpeedIndividualValue: 0 or 1")
            return False

        return True


@dataclass
class StatusConfig:
    should_check_speed: bool
    should_check_status: bool
    should_save_screenshot: bool
    attack_individual_value: int
    speed_individual_value: int


@dataclass
class TemplateMatchingThresholdConfig:
    battle_started: float
    command_appeared: float
    ursaluna_attacked_preemptive: float
    actual_value: float
    individual_value: float
