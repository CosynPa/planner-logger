from typing import List, Optional, Union
import ipywidgets as widgets
import datetime


class PlanItem:
    __slots__ = ["name", "time", "is_finished"]

    def __init__(self, name: str, time: int, is_finished=False):
        self.name = name
        self.time = time
        self.is_finished = is_finished


class PlanController:
    __slots__ = [
        "plans",
        "container",
        "_plan_text",
        "_end_time_text",
        "_time_per_weekday_text",
        "_time_per_weekend_text",
        "_long_time_box",
        "_finish_time_label",
        "_time_left",
        "_plan_box",
    ]

    def __init__(self, plan_string: str, end_time_string: str = "",
                 is_long_time: bool = False, time_per_weekday: str = "", time_per_weekend: str = ""):
        self.plans = self._parse_plan(plan_string)

        # Construct widgets

        plan_text = widgets.Textarea(layout=widgets.Layout(height="20rem", width="100%"))

        end_time_title = widgets.Label(value="End time: ")
        end_time_text = widgets.Text(value=end_time_string)
        end_time_box = widgets.HBox(children=[end_time_title, end_time_text])

        long_time_title = widgets.Label(value="Long time")
        long_time_check = widgets.Checkbox(value=is_long_time, layout=widgets.Layout(width="20px"))
        time_per_weekday_title = widgets.Label(value="Time per weekday: ", layout=widgets.Layout(width="150px"))
        time_per_weekday_text = widgets.Text(value=time_per_weekday, layout=widgets.Layout(width="100px"))
        time_per_weekend_title = widgets.Label(value="Time per weekend: ", layout=widgets.Layout(width="150px"))
        time_per_weekend_text = widgets.Text(value=time_per_weekend, layout=widgets.Layout(width="100px"))
        long_time_box = widgets.HBox()

        finish_time_label = widgets.Label(value="Planning to finish in: ", layout=widgets.Layout(width="100%"))

        time_left = widgets.Label(value="Time left: ", layout=widgets.Layout(width="100%"))

        plan_box = widgets.VBox()

        refresh_button = widgets.Button(description="Refresh")

        container = widgets.VBox()
        container.children = [plan_text,
                              end_time_box, long_time_box, finish_time_label, time_left,
                              plan_box, refresh_button]

        #

        self.container = container
        self._plan_text = plan_text
        self._end_time_text = end_time_text
        self._long_time_box = long_time_box
        self._time_per_weekday_text = time_per_weekday_text
        self._time_per_weekend_text = time_per_weekend_text
        self._finish_time_label = finish_time_label
        self._time_left = time_left
        self._plan_box = plan_box

        plan_text.observe(lambda change: self._plan_text_changed(change), "value")
        end_time_text.observe(lambda change: self._update_time(), "value")
        refresh_button.on_click(lambda button: self._update_time())

        def update_long_time(new_is_long_time):
            if new_is_long_time:
                long_time_box.children = [long_time_title, long_time_check,
                                          time_per_weekday_title, time_per_weekday_text,
                                          time_per_weekend_title, time_per_weekend_text
                                          ]
            else:
                long_time_box.children = [long_time_title, long_time_check]
            self._update_time()

        long_time_check.observe(lambda change: update_long_time(change["new"]), "value")

        self._update_plan_box()
        self._update_time()
        self._update_plan_text()
        update_long_time(is_long_time)

    @staticmethod
    def _parse_plan(s: str) -> List[PlanItem]:
        def parse_item(item: str) -> Optional[PlanItem]:
            strings = item.split(" ")
            if len(strings) < 2:
                return None
            else:
                name_part = strings[:-1]
                time_part = strings[-1]

                if name_part[0].lower() == "done;":
                    is_finished = True
                    name = " ".join(name_part[1:])
                else:
                    is_finished = False
                    name = " ".join(name_part)

                days = time_part.split("d")

                if len(days) == 2:
                    try:
                        day_number = float(days[0])
                    except ValueError:
                        day_number = 0
                else:
                    day_number = 0

                hours = days[-1].split("h")

                if len(hours) == 2:
                    try:
                        hour_number = float(hours[0])
                    except ValueError:
                        hour_number = 0
                else:
                    hour_number = 0

                minutes = hours[-1].split("min")

                if len(minutes) == 2:
                    try:
                        minute_number = float(minutes[0])
                    except ValueError:
                        minute_number = 0
                else:
                    minute_number = 0

                return PlanItem(name, day_number * 24 * 3600 + hour_number * 3600 + minute_number * 60, is_finished)

        return [parsed for parsed in (parse_item(item) for item in s.split("\n")) if parsed is not None]

    @staticmethod
    def _time_str(seconds: Union[int, float]) -> str:
        days, left = divmod(seconds, 86400)
        hours, left = divmod(left, 3600)
        minutes, left = divmod(left, 60)

        if days != 0:
            return "{day:d}d{hour:d}h{minute:d}min".format(day=int(days), hour=int(hours), minute=int(minutes))
        elif hours != 0:
            return "{hour:d}h{minute:d}min".format(hour=int(hours), minute=int(minutes))
        else:
            return "{minute:d}min".format(minute=int(minutes))

    def _update_time(self):
        planning_finish: int = sum(item.time for item in self.plans if not item.is_finished)

        self._finish_time_label.value = "Planning to finish in: {}".format(self._time_str(planning_finish))

        try:
            finish_time = datetime.datetime.strptime(self._end_time_text.value, "%H:%M")
            finish_datetime = datetime.datetime.combine(datetime.datetime.now().date(), finish_time.time())
            now = datetime.datetime.now()
            duration = (finish_datetime - now).total_seconds()
            if duration < 0:
                duration += 86400

            duration_minus_plan = duration - planning_finish
            if duration_minus_plan >= 0:
                duration_minus_plan_str = self._time_str(duration_minus_plan)
            else:
                duration_minus_plan_str = "-" + self._time_str(-duration_minus_plan)

            self._time_left.value = "Time left: {}, -Plan: {}".format(self._time_str(duration), duration_minus_plan_str)
        except ValueError:
            self._time_left.value = "Time left: "

    def _update_plan_box(self):
        def item_box(item: PlanItem, index: int) -> widgets.HBox:
            def on_check_changed(change):
                self.plans[index].is_finished = change["new"]
                self._update_time()
                self._update_plan_text()

            check = widgets.Checkbox(value=item.is_finished, layout=widgets.Layout(width="20px"))
            check.observe(on_check_changed, "value")

            name_text = item.name + " " + self._time_str(item.time)
            name_title = widgets.Label(value=name_text, layout=widgets.Layout(width="80%"))

            return widgets.HBox(children=[check, name_title])

        self._plan_box.children = [item_box(item, i) for i, item in enumerate(self.plans)]

    def _update_plan_text(self):
        text = ""
        for item in self.plans:
            if item.is_finished:
                finish_prefix = "Done; "
            else:
                finish_prefix = ""

            text += finish_prefix + item.name + " " + self._time_str(item.time) + "\n"

        self._plan_text.value = text

    def _plan_text_changed(self, change):
        new_plan = change["new"]
        self.plans = self._parse_plan(new_plan)

        self._update_plan_box()
        self._update_time()
