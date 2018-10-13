import datetime
from typing import List, Optional, Tuple
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
    __slots__ = ["first_duration", "last_duration", "is_marked", "is_mark_set"]

    def __init__(self, first_duration: str = "", last_duration: str = "",
                 is_marked: bool = False, is_mark_set: bool = False):
        self.first_duration = first_duration
        self.last_duration = last_duration
        self.is_marked = is_marked
        self.is_mark_set = is_mark_set # Whether the mark is manually set


class ContinuingLogItem(LogItem):
    __slots__ = ["index", "is_continued", "previous_log", "next_log", "plan", "backup_plan"]

    def __init__(self, name: str, start_str: str, end_str: str,
                 index: int, plan: Optional[TwoStagePlanItem] = None,
                 is_continued: bool = False):
        # Don't use the super's attribute is_marked, use plan's is_marked instead
        super().__init__(name, start_str, end_str, is_marked=False)

        self.index: int = index
        self.is_continued: bool = is_continued
        self.previous_log: Optional[ContinuingLogItem] = None
        self.next_log: Optional[ContinuingLogItem] = None
        self.plan: TwoStagePlanItem = plan if plan is not None else TwoStagePlanItem()
        self.backup_plan: TwoStagePlanItem = self.plan

    def duration(self) -> float:
        return super().duration() + (0.0 if self.previous_log is None else self.previous_log.duration())

    def time_diffs(self) -> Tuple[Optional[float], Optional[float]]:

        first_duration = time_helper.parse_duration(self.plan.first_duration)
        last_duration = time_helper.parse_duration(self.plan.last_duration)

        tail = self.tail()

        if tail.start is not None and tail.end is not None and last_duration is not None:
            time_diff_last = last_duration - tail.duration()
        else:
            time_diff_last = None

        if tail.start is not None and tail.end is not None and first_duration is not None:
            time_diff_first = first_duration - tail.duration()
        else:
            time_diff_first = None

        return time_diff_first, time_diff_last

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
    def __init__(self, log_item: ContinuingLogItem, controller, show_plan_time: bool):
        style = {"description_width": "initial"}

        check_box = widgets.Checkbox(value=log_item.is_marked,
                                     layout=widgets.Layout(width="20px"),
                                     indent=False)
        name_width = "100px" if show_plan_time else "200px"
        name = widgets.Text(value=log_item.name, layout=widgets.Layout(width=name_width))

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
            self.log_item.plan.is_mark_set = True
            if self.log_item.is_in_list():
                controller.update_link()
            controller.update_summary_and_save()

        check_box.observe(on_check, "value")

        def on_continue_check(change):
            if self.is_updating:
                return

            new_value = change["new"]
            self.log_item.is_continued = new_value

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

        plan_time_widgets = [time_diff_label, first_duration, last_duration] if show_plan_time else []
        super().__init__(children=[check_box, name, duration_label] + plan_time_widgets + [
            continue_check,
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

        time_diff_first, time_diff_last = self.log_item.time_diffs()

        if time_diff_first is not None and time_diff_first  >= 0:
            color = "green"
        elif time_diff_last is not None and time_diff_last < 0:
            color = "red"
        else:
            color = "black"
        duration_str = time_helper.duration_str(time_diff_last) if time_diff_last is not None else ""
        self.time_diff_label.value = '<p style="color:{}">{}</p>'.format(color, duration_str)

        self.is_updating = False

class PlannerLoggerController:
    __slots__ = ["show_plan_time",
                 "logs", "plans", "container", "file", "suspend_summary_update", "suspend_link_update",
                 "previous_logs",
                 "log_box", "summary_box", "bonus_formula", "plan_time", "previous_bonus", "bonus"]

    def __init__(self, file: Optional[str] = None, show_plan_time: bool = False):
        self.show_plan_time = show_plan_time
        _logs: List[ContinuingLogItem] = []
        _previous_logs: List[ContinuingLogItem] = []
        _bonus_formula = None
        _plan_time = None
        _previous_bonus = None
        self.file = file
        if file is not None:
            try:
                with open(file) as data_file:
                    data = json.load(data_file)
                    if isinstance(data, dict):
                        def parse_log(dic):
                            try:
                                if not isinstance(dic, dict):
                                    return None

                                name = dic["name"]
                                start_str = dic["start_str"]
                                end_str = dic["end_str"]
                                index = dic["index"]
                                is_continued = dic["is_continued"]
                                plan_dic = dic["plan"]

                                if not isinstance(plan_dic, dict):
                                    return None

                                first_duration = plan_dic["first_duration"]
                                last_duration = plan_dic["last_duration"]
                                is_marked = plan_dic["is_marked"]
                                is_mark_set = plan_dic.get("is_mark_set", False)
                                plan = TwoStagePlanItem(first_duration, last_duration, is_marked, is_mark_set)
                                log = ContinuingLogItem(name, start_str, end_str, index, plan, is_continued)

                                return log

                            except KeyError:
                                return None

                        logs = data["logs"]
                        if isinstance(logs, list):
                            for dic in logs:
                                log = parse_log(dic)
                                if log is not None:
                                    _logs.append(log)

                        previous_logs = data.get("previous_logs")
                        if isinstance(previous_logs, list):
                            for dic in previous_logs:
                                log = parse_log(dic)
                                if log is not None:
                                    _previous_logs.append(log)

                        _bonus_formula = data["bonus_formula"]
                        _plan_time = data["plan_time"]
                        _previous_bonus = data["previous_bonus"]

            except (OSError, json.JSONDecodeError, KeyError):
                pass

        self.logs = _logs
        self.previous_logs = _previous_logs

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

        plan_time_summary_widgets = [default_formula_button, 
            self.bonus_formula, self.plan_time, self.previous_bonus, self.bonus] if self.show_plan_time else []
        self.container = widgets.VBox(children=[self.log_box, plus_button, remove_marks_button, clear_button,
                                                self.summary_box] + plan_time_summary_widgets)


        class UpdateType(enum.Enum):
            APPEND = enum.auto()
            RESET = enum.auto()
            REMOVE_MARKS = enum.auto()

        def on_remove_marks_click(_):
            for item in self.logs:
                item.plan.is_marked = False
                item.plan.is_mark_set = True
            update(UpdateType.REMOVE_MARKS)

        remove_marks_button.on_click(on_remove_marks_click)

        def on_plus_button_click(_):
            self.logs.append(ContinuingLogItem("", "", "", len(self.logs)))
            update(UpdateType.APPEND)

        plus_button.on_click(on_plus_button_click)

        def on_clear_button_click(_):
            # Save logs to previous_logs, keep recent 100 logs
            self.logs.reverse()
            self.previous_logs = self.logs + self.previous_logs
            self.previous_logs = self.previous_logs[0:100]

            self.logs = []
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
                    PlannerLoggerItemBox(self.logs[-1], self, self.show_plan_time),
                    ]
            elif update_type is UpdateType.RESET:
                old = self.log_box.children

                self.log_box.children = [PlannerLoggerItemBox(log_item, self, self.show_plan_time)
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
            if same_name_logs and log.is_continued:
                log.insert_to_linked_list(after_item=same_name_logs[-1])
                log.backup_plan = copy.copy(log.plan)
                log.plan = same_name_logs[-1].plan    
            else:
                log.is_continued = False
                log.plan = log.backup_plan
                if not log.plan.is_mark_set:
                    if same_name_logs:
                        log.plan.is_marked = same_name_logs[-1].plan.is_marked
                    else:
                        same_name_logs_in_previous = [a_log for a_log in 
                                self.previous_logs if a_log.name == log.name]
                        if same_name_logs_in_previous:
                            log.plan.is_marked = same_name_logs_in_previous[0].plan.is_marked
                
            
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
            _, time_diff_last = log.time_diffs()
            time_diff_last = time_diff_last if time_diff_last is not None else 0.0

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
                def log_dic(log):
                    plan_dic = {
                        "first_duration": log.plan.first_duration,
                        "last_duration": log.plan.last_duration,
                        "is_marked": log.plan.is_marked,
                        "is_mark_set": log.plan.is_mark_set,
                    }

                    dic = {
                        "name": log.name,
                        "start_str": log.start.strftime("%H:%M") if log.start is not None else "''",
                        "end_str": log.end.strftime("%H:%M") if log.end is not None else "''",
                        "index": log.index,
                        "is_continued": log.is_continued,
                        "plan": plan_dic,
                    }

                    return dic

                logs = []
                for log in self.logs:
                    logs.append(log_dic(log))

                previous_logs = []
                for log in self.previous_logs:
                    previous_logs.append(log_dic(log))

                root = {
                    "logs": logs,
                    "previous_logs": previous_logs,
                    "bonus_formula": self.bonus_formula.value,
                    "plan_time": self.plan_time.value,
                    "previous_bonus": self.previous_bonus.value,
                }
                json.dump(root, f)
        except OSError:
            print("File open fail")

