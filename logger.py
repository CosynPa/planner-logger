import datetime
from typing import List, Optional
import enum
import weakref

import ipywidgets as widgets

import time_helper


class LogItem:
    __slots__ = ["name", "start", "end", "is_marked"]

    def __init__(self, name: str, start_str: str, end_str: str, is_marked: bool = False):
        self.name = name
        self.start = time_helper.parse_time(start_str)[0]
        self.end = time_helper.parse_time(end_str)[0]
        self.is_marked = is_marked

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

    def __init__(self, logs: Optional[List[LogItem]] = None):
        _logs: List[LogItem] = logs or []
        self.logs = _logs

        log_box = widgets.VBox()
        remove_marks_button = widgets.Button(description="Remove marks")
        plus_button = widgets.Button(description="+")
        clear_button = widgets.Button(description="Clear")
        summary_box = widgets.VBox()

        self.container = widgets.VBox(children=[log_box, plus_button, remove_marks_button, clear_button, summary_box])

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
                    update_summary()

                check_box.observe(on_check, "value")

                def on_name_change(change):
                    log_item.name = change["new"]
                    update_summary()

                name.observe(on_name_change, "value")

                def on_start_change(change):
                    log_item.start = time_helper.parse_time(change["new"])[0]
                    update_duration()
                    update_summary()

                start.observe(on_start_change, "value")

                def on_start_now_click(_):
                    start.value = datetime.datetime.now().strftime("%H:%M")

                start_now.on_click(on_start_now_click)

                def on_end_change(change):
                    log_item.end = time_helper.parse_time(change["new"])[0]
                    update_duration()
                    update_summary()

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

            def update_summary():
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

            update_summary()

        update(UpdateType.RESET)
