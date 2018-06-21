import datetime
from typing import List, Optional
import enum
import json
import weakref
import copy

import ipywidgets as widgets

from logger import LogItem
import time_helper
import debounce

from IPython.core.debugger import set_trace

class TwoStagePlanItem:
    __slots__ = ["first_duration", "last_duration", "is_marked"]

    def __init__(self, first_duration: str = "", last_duration: str = "", is_marked: bool = False):
        self.first_duration = first_duration
        self.last_duration = last_duration
        self.is_marked = is_marked


class ContinuingLogItem(LogItem):
    __slots__ = ["index", "is_continued", "manually_set_uncontinued", "previous_log", "next_log", "plan", "backup_plan"]

    def __init__(self, name: str, start_str: str, end_str: str,
                 index: int, plan: Optional[TwoStagePlanItem] = None,
                 is_continued: bool = False):
        # Don't use the super's attribute is_marked, use plan's is_marked instead
        super().__init__(name, start_str, end_str, is_marked=False)

        self.index: int = index
        self.is_continued: bool = is_continued
        self.manually_set_uncontinued = False
        self.previous_log: Optional[ContinuingLogItem] = None
        self.next_log: Optional[ContinuingLogItem] = None
        self.plan: TwoStagePlanItem = plan if plan is not None else TwoStagePlanItem()
        self.backup_plan: TwoStagePlanItem = self.plan

    def duration(self) -> float:
        return super().duration() + (0.0 if self.previous_log is None else self.previous_log.duration())

    def is_head(self) -> bool:
        return self.next_log is not None and self.previous_log is None

    def is_in_list(self) -> bool:
        return self.next_log is not None or self.previous_log is not None

    def tail(self) -> "ContinuingLogItem":
        if self.next_log is None:
            return self
        else:
            return self.next_log.tail()

    def clear_link_state(self):
        self.is_continued = False
        self.previous_log = None
        self.next_log = None

    def insert_to_linked_list(self, after_item: "ContinuingLogItem"):
        self.is_continued = True

        next_item = after_item.next_log

        self.previous_log = after_item
        self.next_log = next_item

        after_item.next_log = self
        if next_item is not None:
            next_item.previous_log = self


class PlannerLoggerItemBox(widgets.HBox):
    def __init__(self, log_item: ContinuingLogItem, controller):
        style = {"description_width": "initial"}

        check_box = widgets.Checkbox(value=log_item.is_marked,
                                     layout=widgets.Layout(width="20px"),
                                     indent=False)
        name = widgets.Text(value=log_item.name, layout=widgets.Layout(width="100px"))

        continue_check = widgets.Checkbox(value=log_item.is_continued,
                                          layout=widgets.Layout(width="20px"),
                                          indent=False)

        duration_label = widgets.Label(layout=widgets.Layout(width="50px"))
        time_diff_label = widgets.HTML(layout=widgets.Layout(width="50px"))
        first_duration = widgets.Text(value=log_item.plan.first_duration,
            description="First duration:", layout=widgets.Layout(width="150px"), style=style)
        last_duration = widgets.Text(value=log_item.plan.last_duration,
            description="Last duration:", layout=widgets.Layout(width="150px"), style=style)

        spacing = widgets.HBox(layout=widgets.Layout(width="40px"))

        start_text = log_item.start.strftime("%H:%M") if log_item.start is not None else ""
        start = widgets.Text(value=start_text, description="Start:", layout=widgets.Layout(width="100px"), style=style)

        end_text = log_item.end.strftime("%H:%M") if log_item.end is not None else ""
        end = widgets.Text(value=end_text, description="End:", layout=widgets.Layout(width="100px"), style=style)

        start_now = widgets.Button(description="Now", layout=widgets.Layout(width="auto"))
        last_button = widgets.Button(description="Last", layout=widgets.Layout(width="auto"))
        end_now = widgets.Button(description="Now", layout=widgets.Layout(width="auto"))

        def on_check(change):
            if self.is_updating:
                return

            self.log_item.plan.is_marked = change["new"]
            if self.log_item.is_in_list():
                controller.update_link()
            controller.update_summary_and_save()

        check_box.observe(on_check, "value")

        def on_continue_check(change):
            if self.is_updating:
                return

            new_value = change["new"]
            self.log_item.is_continued = new_value
            self.log_item.manually_set_uncontinued = not new_value

            controller.update_link()
            controller.update_summary_and_save()

        continue_check.observe(on_continue_check, "value")

        def on_name_change(change):
            if self.is_updating:
                return
            
            new_name = change["new"]
            self.log_item.name = new_name

            controller.update_link()
            controller.update_summary_and_save()

        name.observe(debounce.debounced(0.1)(on_name_change), "value")

        def on_first_duration_change(change):
            if self.is_updating:
                return
            
            self.log_item.plan.first_duration = change["new"]
            self.update()
            if self.log_item.is_head():
                controller.update_link()
            controller.update_summary_and_save()

        first_duration.observe(on_first_duration_change, "value")

        def on_last_duration_change(change):
            if self.is_updating:
                return
            
            self.log_item.plan.last_duration = change["new"]
            self.update()
            if self.log_item.is_head():
                controller.update_link()
            controller.update_summary_and_save()

        last_duration.observe(on_last_duration_change, "value")

        def on_start_change(change):
            if self.is_updating:
                return
            
            self.log_item.start = time_helper.parse_time(change["new"])[0]
            self.update()
            if self.log_item.is_in_list():
                controller.update_link()
            controller.update_summary_and_save()

        start.observe(on_start_change, "value")

        def on_start_now_click(_):
            if self.is_updating:
                return
            
            start.value = datetime.datetime.now().strftime("%H:%M")

        start_now.on_click(on_start_now_click)

        def on_last_click(_):
            if self.is_updating:
                return
            
            if self.log_item.index >= 1:
                last_end = controller.logs[self.log_item.index - 1].end
                if last_end is not None:
                    start.value = last_end.strftime("%H:%M")

        last_button.on_click(on_last_click)

        def on_end_change(change):
            if self.is_updating:
                return
            
            self.log_item.end = time_helper.parse_time(change["new"])[0]
            self.update()
            if self.log_item.is_in_list():
                controller.update_link()
            controller.update_summary_and_save()

        end.observe(on_end_change, "value")

        def on_end_now_click(_):
            if self.is_updating:
                return
            
            end.value = datetime.datetime.now().strftime("%H:%M")

        end_now.on_click(on_end_now_click)

        super().__init__(children=[
            check_box, name, continue_check,
            duration_label, time_diff_label, first_duration, last_duration,
            spacing,
            start, start_now, last_button,
            end, end_now,
        ])

        self.log_item = log_item
        self.check_box = check_box
        self.continue_check = continue_check
        self.first_duration = first_duration
        self.last_duration = last_duration
        self.time_diff_label = time_diff_label
        self.duration_label = duration_label

        self.is_updating = False

        self.update()

    def update(self):
        if self.is_updating:
            return

        self.is_updating = True

        self.duration_label.value = time_helper.duration_str(self.log_item.duration())

        self.first_duration.value = self.log_item.plan.first_duration
        self.last_duration.value = self.log_item.plan.last_duration

        self.check_box.value = self.log_item.plan.is_marked

        self.check_box.disabled = self.log_item.is_continued
        self.continue_check.value = self.log_item.is_continued
        self.first_duration.disabled = self.log_item.is_continued
        self.last_duration.disabled = self.log_item.is_continued

        first_duration = time_helper.parse_duration(self.log_item.plan.first_duration)
        last_duration = time_helper.parse_duration(self.log_item.plan.last_duration)

        time_diff_last = last_duration - self.log_item.tail().duration() if last_duration is not None else 0.0
        time_diff_first = first_duration - self.log_item.tail().duration() if first_duration is not None else 0.0
        if time_diff_first >= 0 and first_duration is not None:
            color = "green"
        elif time_diff_last >= 0:
            color = "black"
        else:
            color = "red"
        self.time_diff_label.value = '<p style="color:{}">{}</p>'.format(color, time_helper.duration_str(time_diff_last))

        self.is_updating = False

class PlannerLoggerController:
    __slots__ = ["logs", "plans", "container", "file", "suspend_summary_update", "suspend_link_update",
                 "log_box", "summary_box", "bonus_formula", "plan_time", "previous_bonus", "bonus"]

    def __init__(self, file: Optional[str] = None):
        _logs: List[ContinuingLogItem] = []
        _bonus_formula = None
        _plan_time = None
        _previous_bonus = None
        self.file = file
        if file is not None:
            try:
                with open(file) as data_file:
                    data = json.load(data_file)
                    if isinstance(data, dict):
                        logs = data["logs"]
                        if isinstance(logs, list):
                            for dic in logs:
                                if isinstance(dic, dict):
                                    name = dic["name"]
                                    start_str = dic["start_str"]
                                    end_str = dic["end_str"]
                                    index = dic["index"]
                                    is_continued = dic["is_continued"]
                                    manually_set_uncontinued = dic["manually_set_uncontinued"]
                                    plan_dic = dic["plan"]

                                    if isinstance(plan_dic, dict):
                                        first_duration = plan_dic["first_duration"]
                                        last_duration = plan_dic["last_duration"]
                                        is_marked = plan_dic["is_marked"]
                                        plan = TwoStagePlanItem(first_duration, last_duration, is_marked)
                                        log = ContinuingLogItem(name, start_str, end_str, index, plan, is_continued)
                                        log.manually_set_uncontinued = manually_set_uncontinued
                                        _logs.append(log)

                        _bonus_formula = data["bonus_formula"]
                        _plan_time = data["plan_time"]
                        _previous_bonus = data["previous_bonus"]

            except (OSError, json.JSONDecodeError, KeyError):
                pass

        self.logs = _logs

        self.log_box = widgets.VBox()
        remove_marks_button = widgets.Button(description="Remove marks")
        plus_button = widgets.Button(description="+")
        clear_button = widgets.Button(description="Clear")
        self.summary_box = widgets.VBox()

        default_formula_button = widgets.Button(description="Default formula")

        default_formula = "not_marked_total - plan_time + previous_bonus * 0.5 + not_marked_plus * 0.5"

        style = {"description_width": "100px"}
        self.bonus_formula = widgets.Text(description="Bonus formula", layout=widgets.Layout(width="90%"), style=style)
        self.bonus_formula.value = _bonus_formula if _bonus_formula is not None else default_formula

        self.plan_time = widgets.Text(description="Plan time", layout=widgets.Layout(widht="120px"), style=style)
        self.plan_time.value = _plan_time if _plan_time is not None else ""

        self.previous_bonus = widgets.Text(description="Previous bonus", layout=widgets.Layout(widht="120px"), style=style)
        self.previous_bonus.value = _previous_bonus if _previous_bonus is not None else ""

        self.bonus = widgets.Label(layout=widgets.Layout(widht="150px"))

        self.container = widgets.VBox(children=[self.log_box, plus_button, remove_marks_button, clear_button,
                                                self.summary_box,
                                                default_formula_button,
                                                self.bonus_formula, self.plan_time, self.previous_bonus, self.bonus])

        class UpdateType(enum.Enum):
            APPEND = enum.auto()
            RESET = enum.auto()
            REMOVE_MARKS = enum.auto()

        def on_remove_marks_click(_):
            for item in self.logs:
                item.is_marked = False
            update(UpdateType.REMOVE_MARKS)

        remove_marks_button.on_click(on_remove_marks_click)

        def on_plus_button_click(_):
            self.logs.append(ContinuingLogItem("", "", "", len(self.logs)))
            update(UpdateType.APPEND)

        plus_button.on_click(on_plus_button_click)

        def on_clear_button_click(_):
            self.logs.clear()
            update(UpdateType.RESET)

        clear_button.on_click(on_clear_button_click)

        def on_default_formula_click(_):
            self.bonus_formula.value = default_formula

        default_formula_button.on_click(on_default_formula_click)

        def on_bonus_related_change(change):
            self.update_summary_and_save()

        self.bonus_formula.observe(on_bonus_related_change, "value")
        self.plan_time.observe(on_bonus_related_change, "value")
        self.previous_bonus.observe(on_bonus_related_change, "value")

        self.suspend_summary_update = False
        self.suspend_link_update = False

        def update(update_type: UpdateType):
            if update_type is UpdateType.APPEND:
                self.log_box.children = list(self.log_box.children) + [
                    PlannerLoggerItemBox(self.logs[-1], self),
                    ]
            elif update_type is UpdateType.RESET:
                old = self.log_box.children

                self.log_box.children = [PlannerLoggerItemBox(log_item, self)
                                         for log_item in self.logs]

                for box in old:
                    for child in box.children:
                        child.close()
                    box.close()
            elif update_type is UpdateType.REMOVE_MARKS:
                self.suspend_summary_update = True  # Avoid trigger summary update each time for every check box
                for iterm_box in self.log_box.children:
                    iterm_box.check_box.value = False
                self.suspend_summary_update = False
            else:
                assert False, "Unexpected update type"

            self.update_link()
            self.update_summary_and_save()

        update(UpdateType.RESET)

    def update_link(self):
        if self.suspend_link_update:
            return

        self.suspend_link_update = True

        for index, log in enumerate(self.logs):
            log.clear_link_state()

            same_name_logs = [a_log for a_log in self.logs[0:index] if a_log.name == log.name]
            if same_name_logs and not log.manually_set_uncontinued:
                log.insert_to_linked_list(after_item=same_name_logs[-1])
                log.backup_plan = copy.copy(log.plan)
                log.plan = same_name_logs[-1].plan
            else:
                # When a log is changed from continued to uncontinued, it usually
                # has the same type of mark state as the previous log with the same name
                is_marked = log.plan.is_marked
                log.plan = log.backup_plan
                log.plan.is_marked = is_marked
            
        # should update after linked list structure is completely constructed
        for box in self.log_box.children:
            box.update()

        self.suspend_link_update = False

    def update_summary_and_save(self):
        if self.suspend_summary_update:
            return

        tail_logs = []

        for log in self.logs:
            if id(log.plan) not in [id(tail_log.plan) for tail_log in tail_logs]:
                tail_logs.append(log.tail())

        marked_plus = 0.0
        marked_minus = 0.0
        marked_total = 0.0
        not_marked_plus = 0.0
        not_marked_minus = 0.0
        not_marked_total = 0.0
        for log in tail_logs:
            last_duration = time_helper.parse_duration(log.plan.last_duration)

            time_diff_last = last_duration - log.duration() if last_duration is not None else 0.0

            if log.plan.is_marked:
                if time_diff_last >= 0:
                    marked_plus += time_diff_last
                else:
                    marked_minus += time_diff_last
                marked_total += log.duration()
            else:
                if time_diff_last >= 0:
                    not_marked_plus += time_diff_last
                else:
                    not_marked_minus += time_diff_last
                not_marked_total += log.duration()

        layout = widgets.Layout(width="100%", max_width="100%")

        marked_title = widgets.Label(value="Marked:",
            layout=layout)
        marked_summary = widgets.Label(
            value="Total: {}, plus: {}, minus: {}".format(
                time_helper.duration_str(marked_total),
                time_helper.duration_str(marked_plus),
                time_helper.duration_str(marked_minus)),
            layout=layout)
        not_marked_title = widgets.Label(value="Not marked:",
            layout=layout)
        not_marked_summary = widgets.Label(
            value="Total: {}, plus: {}, minus: {}".format(
                time_helper.duration_str(not_marked_total),
                time_helper.duration_str(not_marked_plus),
                time_helper.duration_str(not_marked_minus)),
            layout=layout)

        self.summary_box.children = [marked_title, marked_summary, not_marked_title, not_marked_summary]

        previous_bonus = time_helper.parse_duration(self.previous_bonus.value) or 0.0
        plan_time = time_helper.parse_duration(self.plan_time.value) or 0.0

        eval_error = None
        try:
            local_dic = {
                "plan_time": plan_time,
                "previous_bonus": previous_bonus,
                "marked_plus": marked_plus,
                "marked_minus": marked_minus,
                "marked_total": marked_total,
                "not_marked_plus": not_marked_plus,
                "not_marked_minus": not_marked_minus,
                "not_marked_total": not_marked_total,
            }
            bonus_duration = eval(self.bonus_formula.value, {'__builtins__':{}}, local_dic)
        except BaseException as error:
            eval_error = error
            bonus_duration = 0.0

        if eval_error is None:
            self.bonus.value = "Bonus: {}".format(time_helper.duration_str(bonus_duration))
        else:
            self.bonus.value = "Error: " + str(eval_error)

        self.save()

    def save(self):
        if self.file is None:
            return

        try:
            with open(self.file, mode="w") as f:
                logs = []
                for log in self.logs:
                    plan_dic = {
                        "first_duration": log.plan.first_duration,
                        "last_duration": log.plan.last_duration,
                        "is_marked": log.plan.is_marked,
                    }

                    dic = {
                        "name": log.name,
                        "start_str": log.start.strftime("%H:%M") if log.start is not None else "''",
                        "end_str": log.end.strftime("%H:%M") if log.end is not None else "''",
                        "index": log.index,
                        "is_continued": log.is_continued,
                        "manually_set_uncontinued": log.manually_set_uncontinued,
                        "plan": plan_dic,
                    }

                    logs.append(dic)
                root = {
                    "logs": logs,
                    "bonus_formula": self.bonus_formula.value,
                    "plan_time": self.plan_time.value,
                    "previous_bonus": self.previous_bonus.value,
                }
                json.dump(root, f)
        except OSError:
            print("File open fail")

