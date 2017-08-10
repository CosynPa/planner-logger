import datetime
from typing import List, Optional
import enum
import weakref

import ipywidgets as widgets

import time_helper


class LogItem:
    __slots__ = ["name", "start", "end", "is_marked"]

    def __init__(self, name: str, start_str: str, end_str: str, is_marked: bool = False):
        self.name: str = name
        self.start: Optional[datetime.date] = time_helper.parse_time(start_str)[0]
        self.end: Optional[datetime.date] = time_helper.parse_time(end_str)[0]
        self.is_marked: bool = is_marked

    def duration(self) -> float:
        if self.start is not None and self.end is not None:
            duration = (self.end - self.start).total_seconds()
            return duration if duration >= 0 else duration + 86400.
        else:
            return 0.


class LogController:
    __slots__ = [
        "logs",
        "container",
    ]

    def __init__(self, logs: Optional[List[LogItem]] = None, show_logs: bool = False):
        _logs: List[LogItem] = logs or []
        self.logs = _logs

        log_box = widgets.VBox()
        remove_marks_button = widgets.Button(description="Remove marks")
        plus_button = widgets.Button(description="+")
        clear_button = widgets.Button(description="Clear")
        summary_box = widgets.VBox()

        show_array_checkbox = widgets.Checkbox(description="Show logs array", value=show_logs)
        namespace_text = widgets.Text(description="namespace prefix", value="logger.")
        array_tip_text = ("You can create a new LogController from the current existing logs "
                          "by passing the following array:")
        array_tip = widgets.Label(value=array_tip_text, layout=widgets.Layout(width="100%", max_width="100%"))
        array_text = widgets.Textarea(layout=widgets.Layout(width="100%", height="15rem"))
        array_box = widgets.VBox()

        self.container = widgets.VBox(children=[log_box, plus_button, remove_marks_button, clear_button, summary_box,
                                                show_array_checkbox, array_box])

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
            self.logs.append(LogItem("", "", ""))
            update(UpdateType.APPEND)

        plus_button.on_click(on_plus_button_click)

        def on_clear_button_click(_):
            self.logs.clear()
            update(UpdateType.RESET)

        clear_button.on_click(on_clear_button_click)

        def on_namespace_change(_):
            update_array_text()

        namespace_text.observe(on_namespace_change, "value")

        def update_logs_array(show):
            if show:
                array_box.children = [namespace_text, array_tip, array_text]
            else:
                array_box.children = []

        update_logs_array(show_logs)
        show_array_checkbox.observe(lambda change: update_logs_array(change["new"]), "value")

        suspend_summary_update = False
        check_boxes = weakref.WeakSet()

        def update(update_type: UpdateType):
            def log_item_box(log_item: LogItem) -> widgets.HBox:
                check_box = widgets.Checkbox(value=log_item.is_marked, layout=widgets.Layout(width="30px"))
                name = widgets.Text(value=log_item.name)

                start_text = log_item.start.strftime("%H:%M") if log_item.start is not None else ""
                start = widgets.Text(value=start_text, description="Start:", layout=widgets.Layout(width="30%"))

                end_text = log_item.end.strftime("%H:%M") if log_item.end is not None else ""
                end = widgets.Text(value=end_text, description="End:", layout=widgets.Layout(width="30%"))

                start_now = widgets.Button(description="Now", layout=widgets.Layout(width="50px"))
                end_now = widgets.Button(description="Now", layout=widgets.Layout(width="50px"))

                duration_label = widgets.Label()

                check_boxes.add(check_box)

                def update_duration():
                    duration_label.value = time_helper.duration_str(log_item.duration())

                update_duration()

                def on_check(change):
                    log_item.is_marked = change["new"]
                    update_summary_array_text()

                check_box.observe(on_check, "value")

                def on_name_change(change):
                    log_item.name = change["new"]
                    update_summary_array_text()

                name.observe(on_name_change, "value")

                def on_start_change(change):
                    log_item.start = time_helper.parse_time(change["new"])[0]
                    update_duration()
                    update_summary_array_text()

                start.observe(on_start_change, "value")

                def on_start_now_click(_):
                    start.value = datetime.datetime.now().strftime("%H:%M")

                start_now.on_click(on_start_now_click)

                def on_end_change(change):
                    log_item.end = time_helper.parse_time(change["new"])[0]
                    update_duration()
                    update_summary_array_text()

                end.observe(on_end_change, "value")

                def on_end_now_click(_):
                    end.value = datetime.datetime.now().strftime("%H:%M")

                end_now.on_click(on_end_now_click)

                return widgets.HBox(children=[
                    check_box, name, start, start_now, end, end_now, duration_label
                ])

            if update_type is UpdateType.APPEND:
                log_box.children = list(log_box.children) + [log_item_box(self.logs[-1])]
            elif update_type is UpdateType.RESET:
                old = log_box.children

                log_box.children = [log_item_box(item) for item in self.logs]

                for box in old:
                    for child in box.children:
                        child.close()
                    box.close()
            elif update_type is UpdateType.REMOVE_MARKS:
                nonlocal suspend_summary_update
                suspend_summary_update = True  # Avoid trigger summary update each time for every check box
                for box in check_boxes:
                    box.value = False
                suspend_summary_update = False
            else:
                assert False, "Unexpected update type"

            def update_summary_array_text():
                if suspend_summary_update:
                    return

                class MarkType(enum.Flag):
                    HAS_ITEM_WITHOUT_MARK = enum.auto()
                    HAS_ITEM_WITH_MARK = enum.auto()

                class MergedItem:
                    def __init__(self, name: str, duration: float, mark_type: MarkType):
                        self.name = name
                        self.duration = duration
                        self.mark_type = mark_type

                # Merge log items with the same name
                merged_items: List[MergedItem] = []
                for item in self.logs:
                    mark_type = MarkType.HAS_ITEM_WITH_MARK if item.is_marked else MarkType.HAS_ITEM_WITHOUT_MARK
                    matched = next((merged for merged in merged_items if merged.name.lower() == item.name.lower()),
                                   None)
                    if matched is not None:
                        matched.duration += item.duration()
                        matched.mark_type |= mark_type
                    else:
                        merged_items.append(MergedItem(item.name, item.duration(), mark_type))

                def item_html(item: MergedItem) -> widgets.HTML:
                    plain_text = item.name + " " + time_helper.duration_str(item.duration)

                    color: str
                    if item.mark_type is MarkType.HAS_ITEM_WITH_MARK | MarkType.HAS_ITEM_WITHOUT_MARK:
                        color = "#804000"
                    elif item.mark_type is MarkType.HAS_ITEM_WITH_MARK:
                        color = "#FF8000"
                    elif item.mark_type is MarkType.HAS_ITEM_WITHOUT_MARK:
                        color = "black"
                    else:
                        color = "black"
                        assert False, "Unexpected mark_type {}".format(item.mark_type)

                    html_text = '<p style="color:{}">{}</p>'.format(color, plain_text)

                    return widgets.HTML(value=html_text, layout=widgets.Layout(width="100%"))

                item_htmls = [item_html(item) for item in merged_items]

                total = time_helper.duration_str(sum(item.duration() for item in self.logs))
                total_marked = time_helper.duration_str(sum(item.duration() for item in self.logs if item.is_marked))

                summary_label = widgets.Label(
                    value="Total: {}, total marked: {}".format(total, total_marked),
                    layout=widgets.Layout(width="100%")
                )

                summary_box.children = item_htmls + [summary_label]

                update_array_text()

            update_summary_array_text()

        def update_array_text():
            array_text.value = self.dumps_logs(namespace_text.value)

        update(UpdateType.RESET)

    def dumps_logs(self, namespace_prefix: str = "logger.") -> str:
        """
        Create the string of logs that can be used by Python interpreter later
        """

        def dumps_log(log: LogItem) -> str:
            return "{}LogItem({}, {}, {}, {})".format(
                namespace_prefix,
                repr(log.name),
                repr(log.start.strftime("%H:%M") if log.start is not None else "''"),
                repr(log.end.strftime("%H:%M") if log.end is not None else "''"),
                repr(log.is_marked)
            )

        result = "[\n"
        for item in self.logs:
            result += dumps_log(item) + ",\n"
        result += "]"

        return result
