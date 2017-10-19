from typing import List, Optional, Tuple
import datetime
import json
import ipywidgets as widgets

import time_helper
from time_helper import TimeType


class PlanItem:
    __slots__ = ["name", "durations", "is_finished", "is_dummy"]

    def __init__(self, name: str, durations: List[Optional[float]], is_finished=False, is_dummy=False):
        self.name = name
        self.durations = durations
        self.is_finished = is_finished
        self.is_dummy = is_dummy

    def text(self):
        if self.is_dummy:
            return self.name
        else:
            duration_strings = [time_helper.duration_str(duration) if duration is not None else " "
                                for duration in self.durations]
            return self.name + " " + " | ".join(duration_strings)

    @staticmethod
    def dummy(name: str) -> "PlanItem":
        plan = PlanItem(name, [], False, True)
        return plan


class PlanController:
    __slots__ = [
        "file",
        "plans",
        "container",
        "_plan_text",
        "_end_time_text",
        "_time_per_weekday_text",
        "_time_per_weekend_text",
        "_today_is_over_checkbox",
        "_long_time_check",
        "_finish_time_label",
        "_time_left",
        "_total_time",
        "_plan_box",
    ]

    def __init__(self, file: Optional[str]):
        self.file = file

        plan_string: str = ""
        end_time_string: str = ""
        is_long_time: bool = False
        time_per_weekday: str = ""
        time_per_weekend: str = ""
        is_today_over: bool = False
        if file is not None:
            try:
                with open(file) as data_file:
                    dic = json.load(data_file)
                    if isinstance(dic, dict):
                        plan_string = dic["plan_string"]
                        end_time_string = dic["end_time_string"]
                        is_long_time = dic["is_long_time"]
                        time_per_weekday = dic["time_per_weekday"]
                        time_per_weekend = dic["time_per_weekend"]
                        is_today_over = dic["is_today_over"]
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        self.plans = self._parse_plan(plan_string)

        # Construct widgets

        title_label = widgets.Label(value="Enter your plans here:", layout=widgets.Layout(width="100%"))
        plan_text = widgets.Textarea(layout=widgets.Layout(height="20rem", width="100%"))

        end_time_text = widgets.Text(value=end_time_string, description="End time:")

        long_time_check = widgets.Checkbox(value=is_long_time, description="Long time",
                                           layout={"width": "150px"},
                                           indent=False)
        time_per_weekday_text = widgets.Text(value=time_per_weekday,
                                             description="Time per weekday:")
        time_per_weekday_text.style.description_width = "120px"

        time_per_weekend_text = widgets.Text(value=time_per_weekend,
                                             description="Time per weekend:")
        time_per_weekend_text.style.description_width = "120px"

        today_is_over_checkbox = widgets.Checkbox(value=is_today_over,
                                                  description="Today is over",
                                                  layout={"width":"150px"},
                                                  indent=False)
        long_time_box = widgets.HBox()

        finish_time_label = widgets.Label(value="Planning to finish in: ", layout=widgets.Layout(width="100%"))

        time_left = widgets.Label(value="Time left: ", layout=widgets.Layout(width="100%"))

        total_time = widgets.Label(value="Total: ", layout=widgets.Layout(width="100%"))

        plan_box = widgets.VBox()

        refresh_button = widgets.Button(description="Update time")

        container = widgets.VBox()
        container.children = [title_label, plan_text,
                              end_time_text, long_time_box, finish_time_label, time_left, total_time,
                              plan_box, refresh_button]

        #

        self.container = container
        self._plan_text = plan_text
        self._end_time_text = end_time_text
        self._long_time_check = long_time_check
        self._time_per_weekday_text = time_per_weekday_text
        self._time_per_weekend_text = time_per_weekend_text
        self._today_is_over_checkbox = today_is_over_checkbox
        self._finish_time_label = finish_time_label
        self._time_left = time_left
        self._total_time = total_time
        self._plan_box = plan_box

        plan_text.observe(lambda change: self._plan_text_changed(change), "value")
        end_time_text.observe(lambda change: self._update_time(), "value")
        refresh_button.on_click(lambda button: self._update_time())
        time_per_weekday_text.observe(lambda change: self._update_time(), "value")
        time_per_weekend_text.observe(lambda change: self._update_time(), "value")
        today_is_over_checkbox.observe(lambda change: self._update_time(), "value")

        def update_long_time(new_is_long_time):
            if new_is_long_time:
                long_time_box.children = [long_time_check,
                                          time_per_weekday_text,
                                          time_per_weekend_text,
                                          today_is_over_checkbox,
                                          ]
            else:
                long_time_box.children = [long_time_check]
            self._update_time()

        long_time_check.observe(lambda change: update_long_time(change["new"]), "value")

        self._update_plan_box()
        self._update_time()
        self._update_plan_text()
        update_long_time(is_long_time)

    @staticmethod
    def _parse_plan(s: str) -> List[PlanItem]:
        def parse_item(item: str) -> PlanItem:
            """Parse plan item

            Examples:
                 Normal: do something 1h30m
                 Comment: # some text
                 Text: some text
                 Multiple time: do something 1h30m | 1h40m
            """

            if len(item) >= 1 and item[0] == "#":
                return PlanItem.dummy(item)

            bar_components = item.split("|")

            first_part = bar_components[0]

            def parse_first_part(first_part: str) -> Tuple[str, bool, Optional[float]]:
                strings = first_part.strip().split(" ")

                if len(strings) == 0:
                    return "", False, None
                elif len(strings) == 1:
                    return strings[0], False, None
                else:
                    possible_duration_string = strings[-1]
                    possible_duration: Optional[float] = time_helper.parse_duration(possible_duration_string)

                    if possible_duration is not None:
                        name_part = strings[:-1]
                    else:
                        name_part = strings

                    if name_part[0].lower() == "done;":
                        is_finished = True
                        name = " ".join(name_part[1:])
                    else:
                        is_finished = False
                        name = " ".join(name_part)

                    return name, is_finished, possible_duration

            name, is_finished, first_duration = parse_first_part(first_part)

            durations: List[Optional[float]] = [first_duration]
            for a_time_string in bar_components[1:]:
                duration: Optional[float] = time_helper.parse_duration(a_time_string.strip())
                durations.append(duration)

            if all(duration is None for duration in durations):
                return PlanItem.dummy(item)
            else:
                return PlanItem(name, durations, is_finished)

        return [parse_item(item) for item in s.split("\n")]

    def _update_time(self):
        planning_finish: float = sum(item.durations[0] or 0 for item in self.plans
                                     if not item.is_finished and not item.is_dummy)

        self._finish_time_label.value = "Planning to finish in: {}".format(time_helper.duration_str(planning_finish))

        time_type: TimeType
        nullable_finish_time: Optional[datetime.datetime]
        nullable_finish_time, time_type,  = time_helper.parse_time(self._end_time_text.value)
        if time_type is TimeType.NONE:
            self._time_left.value = "Time left: "
        else:
            finish_time: datetime.datetime = nullable_finish_time
            if not self._long_time_check.value:
                now = datetime.datetime.now()
                duration: float = (finish_time - now).total_seconds()

                duration_minus_plan_str = time_helper.duration_str(duration - planning_finish)
                self._time_left.value = "Time left: {}, -Plan: {}".format(time_helper.duration_str(duration),
                                                                          duration_minus_plan_str)
            else:
                now = datetime.datetime.now().date()
                finish = finish_time.date()

                if now > finish:
                    self._time_left.value = "Time left: 0"
                else:
                    per_weekday = time_helper.parse_duration(self._time_per_weekday_text.value)
                    per_weekday = per_weekday if per_weekday is not None else 86400.

                    per_weekend = time_helper.parse_duration(self._time_per_weekend_text.value)
                    per_weekend = per_weekend if per_weekend is not None else 86400.

                    range_start = 0 if not self._today_is_over_checkbox.value else 1

                    days = [now + datetime.timedelta(n) for n in
                            range(range_start, finish.toordinal() - now.toordinal() + 1)]

                    duration = sum(per_weekday if day.isoweekday() in range(1, 6) else per_weekend for day in days)

                    duration_minus_plan_str = time_helper.duration_str(duration - planning_finish)
                    self._time_left.value = "Time left: {}, -Plan: {}".format(time_helper.duration_str(duration),
                                                                              duration_minus_plan_str)

        number_column = max(len(item.durations) for item in self.plans)
        total_time_texts: List[str] = []
        for i in range(0, number_column):
            total = sum(item.durations[i] for item in self.plans
                        if not item.is_dummy and i < len(item.durations) and item.durations[i] is not None)
            total_time_texts.append(time_helper.duration_str(total))

        self._total_time.value = "Total time: " + ", ".join(total_time_texts)

        self.save()

    def save(self):
        if self.file is None:
            return

        try:
            with open(self.file, mode="w") as f:
                dic = {
                    "plan_string": self._plan_text.value,
                    "end_time_string": self._end_time_text.value,
                    "is_long_time": self._long_time_check.value,
                    "time_per_weekday": self._time_per_weekday_text.value,
                    "time_per_weekend": self._time_per_weekend_text.value,
                    "is_today_over": self._today_is_over_checkbox.value,
                }
                json.dump(dic, f)
        except OSError:
            print("File open fail")

    def _update_plan_box(self):
        def item_box(item: PlanItem, index: int) -> widgets.HBox:
            def on_check_changed(change):
                self.plans[index].is_finished = change["new"]
                self._update_time()
                self._update_plan_text()

            check = widgets.Checkbox(value=item.is_finished, layout=widgets.Layout(width="30px"), indent=False)
            check.observe(on_check_changed, "value")

            name_text = item.text()
            name_title = widgets.Label(value=name_text, layout=widgets.Layout(width="80%", max_width="80%"))

            return widgets.HBox(children=[check, name_title])

        self._plan_box.children = [item_box(item, i) for i, item in enumerate(self.plans) if not item.is_dummy]

    def _update_plan_text(self):
        text = ""
        for i, item in enumerate(self.plans):
            if item.is_finished:
                finish_prefix = "Done; "
            else:
                finish_prefix = ""

            end_separator = "\n" if i != len(self.plans) - 1 else ""

            text += finish_prefix + item.text() + end_separator

        self._plan_text.value = text

    def _plan_text_changed(self, change):
        new_plan = change["new"]
        self.plans = self._parse_plan(new_plan)

        self._update_plan_box()
        self._update_time()
