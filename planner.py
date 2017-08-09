from typing import List, Optional
import datetime

import ipywidgets as widgets

import time_helper
from time_helper import TimeType


class PlanItem:
    __slots__ = ["name", "time", "is_finished", "is_dummy"]

    def __init__(self, name: str, time: float, is_finished=False, is_dummy=False):
        self.name = name
        self.time = time
        self.is_finished = is_finished
        self.is_dummy = is_dummy

    @staticmethod
    def dummy(name: str) -> "PlanItem":
        plan = PlanItem(name, 0, False, True)
        return plan


class PlanController:
    __slots__ = [
        "plans",
        "container",
        "_plan_text",
        "_end_time_text",
        "_time_per_weekday_text",
        "_time_per_weekend_text",
        "_long_time_check",
        "_finish_time_label",
        "_time_left",
        "_plan_box",
    ]

    def __init__(self, plan_string: str, end_time_string: str = "",
                 is_long_time: bool = False, time_per_weekday: str = "", time_per_weekend: str = ""):
        self.plans = self._parse_plan(plan_string)

        # Construct widgets

        title_label = widgets.Label(value="Enter your plans here:", layout=widgets.Layout(width="100%"))
        plan_text = widgets.Textarea(layout=widgets.Layout(height="20rem", width="100%"))

        end_time_text = widgets.Text(value=end_time_string, description="End time:")

        long_time_check = widgets.Checkbox(value=is_long_time, description="Long time")
        time_per_weekday_text = widgets.Text(value=time_per_weekday,
                                             description="Time per weekday:",
                                             layout=widgets.Layout(width="250px"))
        time_per_weekend_text = widgets.Text(value=time_per_weekend,
                                             description="Time per weekend:",
                                             layout=widgets.Layout(width="250px"))
        long_time_box = widgets.HBox()

        finish_time_label = widgets.Label(value="Planning to finish in: ", layout=widgets.Layout(width="100%"))

        time_left = widgets.Label(value="Time left: ", layout=widgets.Layout(width="100%"))

        plan_box = widgets.VBox()

        refresh_button = widgets.Button(description="Update time")

        container = widgets.VBox()
        container.children = [title_label, plan_text,
                              end_time_text, long_time_box, finish_time_label, time_left,
                              plan_box, refresh_button]

        #

        self.container = container
        self._plan_text = plan_text
        self._end_time_text = end_time_text
        self._long_time_check = long_time_check
        self._time_per_weekday_text = time_per_weekday_text
        self._time_per_weekend_text = time_per_weekend_text
        self._finish_time_label = finish_time_label
        self._time_left = time_left
        self._plan_box = plan_box

        plan_text.observe(lambda change: self._plan_text_changed(change), "value")
        end_time_text.observe(lambda change: self._update_time(), "value")
        refresh_button.on_click(lambda button: self._update_time())
        time_per_weekday_text.observe(lambda change: self._update_time(), "value")
        time_per_weekend_text.observe(lambda change: self._update_time(), "value")

        def update_long_time(new_is_long_time):
            if new_is_long_time:
                long_time_box.children = [long_time_check,
                                          time_per_weekday_text,
                                          time_per_weekend_text
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
            strings = item.split(" ")
            if len(strings) < 2:
                return PlanItem.dummy(item)
            else:
                name_part = strings[:-1]
                time_part = strings[-1]

                if name_part[0].lower() == "done;":
                    is_finished = True
                    name = " ".join(name_part[1:])
                else:
                    is_finished = False
                    name = " ".join(name_part)

                duration: Optional[float] = time_helper.parse_duration(time_part)

                if duration is not None:
                    return PlanItem(name, duration, is_finished)
                else:
                    return PlanItem.dummy(item)

        return [parse_item(item) for item in s.split("\n")]

    def _update_time(self):
        planning_finish: float = sum(item.time for item in self.plans if not item.is_finished and not item.is_dummy)

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

                    days = [now + datetime.timedelta(n) for n in range(finish.toordinal() - now.toordinal() + 1)]

                    duration = sum(per_weekday if day.isoweekday() in range(1, 6) else per_weekend for day in days)

                    duration_minus_plan_str = time_helper.duration_str(duration - planning_finish)
                    self._time_left.value = "Time left: {}, -Plan: {}".format(time_helper.duration_str(duration),
                                                                              duration_minus_plan_str)

    def _update_plan_box(self):
        def item_box(item: PlanItem, index: int) -> widgets.HBox:
            def on_check_changed(change):
                self.plans[index].is_finished = change["new"]
                self._update_time()
                self._update_plan_text()

            check = widgets.Checkbox(value=item.is_finished, layout=widgets.Layout(width="30px"))
            check.observe(on_check_changed, "value")

            name_text = item.name + " " + time_helper.duration_str(item.time)
            name_title = widgets.Label(value=name_text, layout=widgets.Layout(width="80%"))

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

            if item.is_dummy:
                text += finish_prefix + item.name + end_separator
            else:
                text += finish_prefix + item.name + " " + time_helper.duration_str(item.time) + end_separator

        self._plan_text.value = text

    def _plan_text_changed(self, change):
        new_plan = change["new"]
        self.plans = self._parse_plan(new_plan)

        self._update_plan_box()
        self._update_time()
