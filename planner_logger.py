import datetime
from typing import List, Optional, Tuple
import enum
import json
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
    __slots__ = ["index", "_is_continued", "previous_log", "next_log", "plan", "backup_plan"]

    def __init__(self, name: str, start_str: str, end_str: str,
                 index: int, plan: Optional[TwoStagePlanItem] = None,
                 is_continued: bool = False):
        self.plan: TwoStagePlanItem = plan if plan is not None else TwoStagePlanItem()

        super().__init__(name, start_str, end_str, is_marked=self.plan.is_marked)

        self.index: int = index
        self._is_continued: bool = is_continued
        self.previous_log: Optional[ContinuingLogItem] = None
        self.next_log: Optional[ContinuingLogItem] = None

        # Backup the plan when you set continuing, and recover the previous plan when you set uncontinuing.
        self.backup_plan: TwoStagePlanItem = self.plan

    @property
    def is_marked(self):
        return self.plan.is_marked

    @is_marked.setter
    def is_marked(self, value):
        """Directly setting plan.is_marked is preferred"""
        self.plan.is_marked = value

    @property
    def is_continued(self) -> bool:
        return self._is_continued

    @is_continued.setter
    def is_continued(self, new_value: bool):
        old_value = self._is_continued
        self._is_continued = new_value

        if old_value is False and new_value is True:
            self.backup_plan = copy.copy(self.plan)
        elif old_value is True and new_value is False:
            self.plan = copy.copy(self.backup_plan)

    def total_duration(self) -> float:
        """The duration with all previous logs summed"""
        return self.duration() + (0.0 if self.previous_log is None else self.previous_log.total_duration())

    def time_diffs(self) -> Tuple[Optional[float], Optional[float]]:

        first_duration = time_helper.parse_duration(self.plan.first_duration)
        last_duration = time_helper.parse_duration(self.plan.last_duration)

        tail = self.tail()

        if tail.start is not None and tail.end is not None and last_duration is not None:
            time_diff_last = last_duration - tail.total_duration()
        else:
            time_diff_last = None

        if tail.start is not None and tail.end is not None and first_duration is not None:
            time_diff_first = first_duration - tail.total_duration()
        else:
            time_diff_first = None

        return time_diff_first, time_diff_last

    def effective_duration(self) -> float:
        """The effective duration of this plan. It's the last duration if that is set,
         or the actual duration otherwise.

         The benefit of using this duration is that
         you can accomplish some amount of effective time with less actual time.
         """
        last_duration = time_helper.parse_duration(self.plan.last_duration)

        if last_duration is not None:
            return last_duration
        else:
            return self.total_duration()

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
    def __init__(self, log_item: ContinuingLogItem, controller, show_plan_time: bool, show_upload: bool):
        self.controller = controller

        style = {"description_width": "initial"}

        check_box = widgets.Checkbox(value=log_item.is_marked,
                                     layout=widgets.Layout(width="15px"),
                                     indent=False)
        name_width = "150px"
        name = widgets.Text(value=log_item.name, layout=widgets.Layout(width=name_width))

        continue_check = widgets.Checkbox(value=log_item.is_continued,
                                          layout=widgets.Layout(width="15px"),
                                          indent=False)

        duration_label = widgets.Label(layout=widgets.Layout(width="70px"))
        time_diff_label = widgets.HTML(layout=widgets.Layout(width="70px"))
        first_duration = widgets.Text(
            value=log_item.plan.first_duration,
            description="First:", layout=widgets.Layout(width="100px"), style=style
        )
        last_duration = widgets.Text(
            value=log_item.plan.last_duration,
            description="Last:", layout=widgets.Layout(width="100px"), style=style
        )

        spacing = widgets.HBox(layout=widgets.Layout(width="20px"))

        start_text = log_item.start_str
        start = widgets.Text(value=start_text, description="Start:", layout=widgets.Layout(width="100px"), style=style)

        end_text = log_item.end_str
        end = widgets.Text(value=end_text, description="End:", layout=widgets.Layout(width="100px"), style=style)

        start_now = widgets.Button(description="Now", layout=widgets.Layout(width="auto"))
        last_button = widgets.Button(description="Last", layout=widgets.Layout(width="auto"))
        end_now = widgets.Button(description="Now", layout=widgets.Layout(width="auto"))

        upload_button = widgets.Button(description="↑", layout=widgets.Layout(width="auto"))
        uploaded_check = widgets.Checkbox(value=False, layout=widgets.Layout(width="15px"), indent=False)
        uploaded_check.disabled = True

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

        name.observe(on_name_change, "value")

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
            
            self.log_item.start_str = change["new"]
            self.update()
            if self.log_item.is_in_list():
                controller.update_link()
            controller.update_summary_and_save()

        start.observe(on_start_change, "value")

        def on_start_now_click(_):
            if self.is_updating:
                return
            
            controller.register_undo()
            start.value = time_helper.time_str(datetime.datetime.now())

        start_now.on_click(on_start_now_click)

        def on_last_click(_):
            if self.is_updating:
                return
            
            if self.log_item.index >= 1:
                last_end = controller.logs[self.log_item.index - 1].end_str
                if last_end != "":
                    controller.register_undo()
                    start.value = last_end

        last_button.on_click(on_last_click)

        def on_end_change(change):
            if self.is_updating:
                return
            
            self.log_item.end_str = change["new"]
            self.update()
            if self.log_item.is_in_list():
                controller.update_link()
            controller.update_summary_and_save()

        end.observe(on_end_change, "value")

        def on_end_now_click(_):
            if self.is_updating:
                return
            
            controller.register_undo()
            end.value = time_helper.time_str(datetime.datetime.now())

        end_now.on_click(on_end_now_click)

        def on_upload_click(_):
            if controller.reference_controller is not None:
                new_log = ContinuingLogItem(
                    self.log_item.name,
                    "",
                    "",
                    len(controller.reference_controller.logs), plan=None, is_continued=True
                )
                new_log.start = self.log_item.start
                new_log.end = self.log_item.end

                controller.reference_controller.register_undo()
                controller.reference_controller.logs.append(new_log)
                controller.reference_controller.update(UpdateType.APPEND)

                self.update()

        upload_button.on_click(on_upload_click)

        upload_widgets = [uploaded_check, upload_button] if show_upload else []
        plan_time_widgets = [time_diff_label, first_duration, last_duration] if show_plan_time else []
        super().__init__(children=[check_box, name] + upload_widgets + [duration_label] + plan_time_widgets + [
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
        self.upload_button = upload_button
        self.uploaded_check = uploaded_check

        self.is_updating = False

        self.update()

    def update(self):
        if self.is_updating:
            return

        self.is_updating = True

        self.duration_label.value = time_helper.duration_str(self.log_item.total_duration())

        self.first_duration.value = self.log_item.plan.first_duration
        self.last_duration.value = self.log_item.plan.last_duration

        self.check_box.value = self.log_item.plan.is_marked

        self.check_box.disabled = self.log_item.is_continued
        self.continue_check.value = self.log_item.is_continued
        self.first_duration.disabled = self.log_item.is_continued
        self.last_duration.disabled = self.log_item.is_continued

        time_diff_first, time_diff_last = self.log_item.time_diffs()

        if time_diff_first is not None and time_diff_first >= 0:
            color = "#00d000"
        elif time_diff_last is not None and time_diff_last < 0:
            color = "red"
        else:
            color = "black"
        duration_str = time_helper.duration_str(time_diff_last) if time_diff_last is not None else ""
        self.time_diff_label.value = '<p style="color:{}">{}</p>'.format(color, duration_str)

        if self.controller.reference_controller is not None:
            self_valid = self.log_item.start is not None and self.log_item.end is not None
            self.upload_button.disabled = not self_valid

            any_match = self_valid and any(
                log.start == self.log_item.start and log.end == self.log_item.end
                for log in reversed(self.controller.reference_controller.logs))

            self.uploaded_check.value = any_match

        self.is_updating = False


class UpdateType(enum.Enum):
    APPEND = enum.auto()
    RESET = enum.auto()
    REMOVE_MARKS = enum.auto()


class PlannerLoggerController:
    __slots__ = ["show_plan_time", "reference_controller",
                 "logs", "plans", "container", "file", "suspend_summary_update", "suspend_link_update",
                 "previous_logs", 
                 "undo_stack", "redo_stack", "undo_button", "redo_button",
                 "continue_after_break_check", "break_text", "highlights_text",
                 "log_box", "summary_box",]

    def __init__(self, file: Optional[str] = None, show_plan_time: bool = False,
                 reference_controller: Optional["PlannerLoggerController"] = None):
        self.show_plan_time = show_plan_time
        _logs: List[ContinuingLogItem] = []
        _previous_logs: List[ContinuingLogItem] = []
        _continue_after_break = True
        _highlights = None
        _break_title = None
        self.file = file
        self.reference_controller = reference_controller
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
                                is_mark_set = plan_dic["is_mark_set"]
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

                        previous_logs = data["previous_logs"]
                        if isinstance(previous_logs, list):
                            for dic in previous_logs:
                                log = parse_log(dic)
                                if log is not None:
                                    _previous_logs.append(log)

                        _continue_after_break = data["continue_after_break"]
                        _highlights = data["highlights"]
                        _break_title = data["break_title"]

            except (OSError, json.JSONDecodeError, KeyError):
                pass

        self.logs = _logs
        self.previous_logs = _previous_logs
        self.undo_stack: List[List[ContinuingLogItem]] = []
        self.redo_stack: List[List[ContinuingLogItem]] = []

        self.log_box = widgets.VBox()
        remove_marks_button = widgets.Button(description="Remove marks")
        plus_button = widgets.Button(description="+")
        clear_button = widgets.Button(description="Clear")
        self.undo_button = widgets.Button(description="Undo")
        self.redo_button = widgets.Button(description="Redo")
        break_button = widgets.Button(description="Took a Break")
        self.continue_after_break_check = widgets.Checkbox(value=_continue_after_break,
                                                           description="Continue After Break",
                                                           indent=False)
        self.break_text = widgets.Text(
            description="Break Title:", layout=widgets.Layout(width="300px"),
            style={"description_width": "initial"}
        )
        self.summary_box = widgets.VBox()

        self.break_text.value = _break_title if _break_title is not None else ""

        self.highlights_text = widgets.Text(
            description="Highlights", layout=widgets.Layout(width="300px"),
            style={"description_width": "initial"}
        )
        self.highlights_text.value = _highlights if _highlights is not None else ""

        self.container = widgets.VBox(children=[self.log_box, plus_button, remove_marks_button, clear_button,
                                                self.undo_button, self.redo_button,
                                                break_button, self.continue_after_break_check, self.break_text,
                                                self.highlights_text,
                                                self.summary_box])

        def on_remove_marks_click(_):
            self.register_undo()
            for item in self.logs:
                item.plan.is_marked = False
                item.plan.is_mark_set = True
            self.update(UpdateType.REMOVE_MARKS)

        remove_marks_button.on_click(on_remove_marks_click)

        def on_plus_button_click(_):
            self.register_undo()

            start_str = self.logs[-1].end_str if self.logs else ""
            self.logs.append(ContinuingLogItem("", start_str, "", len(self.logs)))

            self.update(UpdateType.APPEND)

        plus_button.on_click(on_plus_button_click)

        def on_clear_button_click(_):
            self.register_undo()

            # Save logs to previous_logs, keep recent 1000 logs
            self.logs.reverse()
            self.previous_logs = self.logs + self.previous_logs
            self.previous_logs = self.previous_logs[0:1000]

            self.logs = []
            self.update(UpdateType.RESET)

        clear_button.on_click(on_clear_button_click)

        def on_undo_button_click(_):
            if len(self.undo_stack) > 0:
                self.register_redo()
                self.logs = self.undo_stack.pop()
                self.update_undo_redo()
                self.update(UpdateType.RESET)

        self.undo_button.on_click(on_undo_button_click)

        def on_redo_button_click(_):
            if len(self.redo_stack) > 0:
                self.register_undo(clear_redo=False)
                self.logs = self.redo_stack.pop()
                self.update_undo_redo()
                self.update(UpdateType.RESET)

        self.redo_button.on_click(on_redo_button_click)

        def on_continue_after_break_change(_):
            self.save()

        self.continue_after_break_check.observe(on_continue_after_break_change)

        def on_break_button_click(_):
            if len(self.logs) > 0:
                self.register_undo()

                last_log: ContinuingLogItem = self.logs[-1]
                now_str = time_helper.time_str(datetime.datetime.now())
                break_log = ContinuingLogItem(name=self.break_text.value,
                                              start_str=last_log.end_str,
                                              end_str=now_str,
                                              index=len(self.logs)
                                              )
                next_log = ContinuingLogItem(name=last_log.name,
                                             start_str=now_str,
                                             end_str="",
                                             index=len(self.logs) + 1,
                                             is_continued=self.continue_after_break_check.value
                                             )

                self.logs.append(break_log)
                self.update(UpdateType.APPEND)
                self.logs.append(next_log)
                self.update(UpdateType.APPEND)

        break_button.on_click(on_break_button_click)

        def on_highlights_change(_):
            self.update_summary_and_save()

        self.highlights_text.observe(on_highlights_change, "value")

        self.suspend_summary_update = False
        self.suspend_link_update = False

        self.update_undo_redo()
        self.update(UpdateType.RESET)

    def register_undo(self, clear_redo=True):
        if clear_redo:
            self.redo_stack.clear()
        self.undo_stack.append(copy.deepcopy(self.logs))
        self.update_undo_redo()

    def register_redo(self):
        self.redo_stack.append(copy.deepcopy(self.logs))
        self.update_undo_redo()

    def update_undo_redo(self):
        self.undo_button.disabled = len(self.undo_stack) == 0
        self.redo_button.disabled = len(self.redo_stack) == 0

    def update(self, update_type: UpdateType):
        if update_type is UpdateType.APPEND:
            self.log_box.children = list(self.log_box.children) + [
                PlannerLoggerItemBox(self.logs[-1], self, self.show_plan_time, self.reference_controller is not None),
                ]
        elif update_type is UpdateType.RESET:
            old = self.log_box.children

            self.log_box.children = [PlannerLoggerItemBox(log_item, self, self.show_plan_time,
                                                          self.reference_controller is not None)
                                     for log_item in self.logs]

            for box in old:
                for child in box.children:
                    child.close()
                box.close()
        elif update_type is UpdateType.REMOVE_MARKS:
            self.suspend_summary_update = True  # Avoid trigger summary update each time for every check box
            for item_box in self.log_box.children:
                item_box.check_box.value = False
            self.suspend_summary_update = False
        else:
            assert False, "Unexpected update type"

        self.update_link()
        self.update_summary_and_save()

    def set_logs(self, logs: List[ContinuingLogItem]):
        for index, log in enumerate(logs):
            log.index = index

        self.register_undo()
        self.logs = logs
        self.update(UpdateType.RESET)

    def set_reference_controller(self, reference_controller):
        self.reference_controller = reference_controller
        self.update(UpdateType.RESET)

    def update_link(self):
        if self.suspend_link_update:
            return

        self.suspend_link_update = True

        for index, log in enumerate(self.logs):
            log.clear_link_state()

            same_name_logs = [a_log for a_log in self.logs[0:index] if a_log.name == log.name]
            if same_name_logs and log.is_continued:
                log.insert_to_linked_list(after_item=same_name_logs[-1])
                log.plan = same_name_logs[-1].plan    
            else:
                log.is_continued = False
                if not log.plan.is_mark_set:
                    if same_name_logs:
                        log.plan.is_marked = same_name_logs[-1].plan.is_marked
                    else:
                        same_name_logs_in_previous = [a_log for a_log in 
                                                      self.previous_logs if a_log.name == log.name]
                        if same_name_logs_in_previous:
                            log.plan.is_marked = same_name_logs_in_previous[0].plan.is_marked
                        else:
                            log.plan.is_marked = False

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
                marked_total += log.effective_duration()
            else:
                if time_diff_last >= 0:
                    not_marked_plus += time_diff_last
                else:
                    not_marked_minus += time_diff_last
                not_marked_total += log.effective_duration()

        layout = widgets.Layout(width="90%", max_width="90%")

        marked_title = widgets.Label(value="Marked:",
                                     layout=layout)

        if self.show_plan_time:
            marked_summary = widgets.Label(
                value="Total: {}, plus: {}, minus: {}".format(
                    time_helper.duration_str(marked_total),
                    time_helper.duration_str(marked_plus),
                    time_helper.duration_str(marked_minus)),
                layout=layout)
        else:
            marked_summary = widgets.Label(
                value="Total: {}".format(
                    time_helper.duration_str(marked_total)),
                layout=layout)
        
        not_marked_title = widgets.Label(value="Not Marked:",
                                         layout=layout)

        if self.show_plan_time:
            not_marked_summary = widgets.Label(
                value="Total: {}, plus: {}, minus: {}".format(
                    time_helper.duration_str(not_marked_total),
                    time_helper.duration_str(not_marked_plus),
                    time_helper.duration_str(not_marked_minus)),
                layout=layout)
        else:
            not_marked_summary = widgets.Label(
                value="Total: {}".format(
                    time_helper.duration_str(not_marked_total)),
                layout=layout)

        item_summary_title = widgets.Label(value="Total Time:", layout=layout)

        highlights = [text.strip() for text in self.highlights_text.value.split(",")]

        self.summary_box.children = [marked_title, marked_summary, not_marked_title, not_marked_summary,
                                     item_summary_title] + LogItem.item_htmls(self.logs, True, highlights, "blue")

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
                        "start_str": log.start_str,
                        "end_str": log.end_str,
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
                    "continue_after_break": self.continue_after_break_check.value,
                    "break_title": self.break_text.value,
                    "highlights": self.highlights_text.value,
                }
                json.dump(root, f)
        except OSError:
            print("File open fail")

