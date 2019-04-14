import datetime
from typing import List, Optional
import enum
import weakref
import json
import ipywidgets as widgets

import time_helper
import debounce


class LogItem:
    __slots__ = ["name", "start", "end", "is_marked"]

    def __init__(self, name: str, start_str: str, end_str: str, is_marked: bool = False):
        self.name: str = name
        self.start: Optional[datetime.time] = time_helper.parse_time(start_str)
        self.end: Optional[datetime.time] = time_helper.parse_time(end_str)
        self.is_marked: bool = is_marked

    def duration(self) -> float:
        if self.start is not None and self.end is not None:
            duration = time_helper.time_diff(self.end, self.start)
            return duration if duration >= 0 else duration + 86400.
        else:
            return 0.

    @staticmethod
    def item_htmls(logs: List["LogItem"], colon_indicate_title: bool, highlights: Optional[List[str]] = None, highlight_color=None):
        highlights = [text.lower() for text in highlights] if highlights is not None else []
        highlight_color = "black" if highlight_color is None else highlight_color

        class MarkType(enum.Flag):
            HAS_ITEM_WITHOUT_MARK = enum.auto()
            HAS_ITEM_WITH_MARK = enum.auto()

        class MergedItem:
            def __init__(self, name: str, duration: float, mark_type: MarkType):
                self.name = name
                self.duration = duration
                self.mark_type = mark_type
                self.is_highlighted = False

        def should_merge(merged: MergedItem, item: LogItem):
            if colon_indicate_title:
                return merged.name.lower() == item.name.split(":")[0].lower()
            else:
                return merged.name.lower() == item.name.lower()

        def merged_name(item: LogItem):
            if colon_indicate_title:
                return item.name.split(":")[0]
            else:
                return item.name

        # Merge log items with the same name
        merged_items: List[MergedItem] = []
        for item in logs:
            mark_type = MarkType.HAS_ITEM_WITH_MARK if item.is_marked else MarkType.HAS_ITEM_WITHOUT_MARK
            matched = next((merged for merged in merged_items if should_merge(merged, item)),
                           None)
            if matched is not None:
                matched.duration += item.duration()
                matched.mark_type |= mark_type
            else:
                merged_items.append(MergedItem(merged_name(item), item.duration(), mark_type))

        for merged in merged_items:
            merged.is_highlighted = merged.name.lower().strip() != "" and merged.name.lower().strip() in highlights

        merged_items.sort(key=lambda merged: merged.is_highlighted, reverse=True)

        def item_html(item: MergedItem) -> widgets.HTML:
            plain_text = item.name + " " + time_helper.duration_str(item.duration)

            color: str
            if item.is_highlighted:
                color = highlight_color
            elif item.mark_type is MarkType.HAS_ITEM_WITH_MARK | MarkType.HAS_ITEM_WITHOUT_MARK:
                color = "#804000"
            elif item.mark_type is MarkType.HAS_ITEM_WITH_MARK:
                color = "#FF8000"
            elif item.mark_type is MarkType.HAS_ITEM_WITHOUT_MARK:
                color = "black"
            else:
                color = "black"
                assert False, "Unexpected mark_type {}".format(item.mark_type)

            if item.is_highlighted:
                html_text = '<p style="color:{}"><b>{}</b></p>'.format(color, plain_text)
            else:
                html_text = '<p style="color:{}">{}</p>'.format(color, plain_text)

            return widgets.HTML(value=html_text, layout=widgets.Layout(width="90%"))

        return [item_html(item) for item in merged_items]


class LogController:
    __slots__ = [
        "logs",
        "container",
        "file",
    ]

    def __init__(self, file: Optional[str] = None):
        self.file = file

        _logs: List[LogItem] = []
        if file is not None:
            try:
                with open(file) as data_file:
                    data = json.load(data_file)
                    if isinstance(data, list):
                        for dic in data:
                            if isinstance(dic, dict):
                                name = dic["name"]
                                start_str = dic["start_str"]
                                end_str = dic["end_str"]
                                is_marked = dic["is_marked"]
                                log = LogItem(name, start_str, end_str, is_marked)
                                _logs.append(log)
            except (OSError, json.JSONDecodeError, KeyError):
                pass

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
            def log_item_box(log_item: LogItem, index: int) -> widgets.HBox:
                check_box = widgets.Checkbox(value=log_item.is_marked,
                                             layout=widgets.Layout(width="30px"),
                                             indent=False)
                name = widgets.Text(value=log_item.name)

                start_text = time_helper.time_str(log_item.start)
                start = widgets.Text(value=start_text, description="Start:", layout=widgets.Layout(width="30%"))

                end_text = time_helper.time_str(log_item.end)
                end = widgets.Text(value=end_text, description="End:", layout=widgets.Layout(width="30%"))

                start_now = widgets.Button(description="Now", layout=widgets.Layout(width="70px"))
                last_button = widgets.Button(description="Last", layout=widgets.Layout(width="70px"))
                end_now = widgets.Button(description="Now", layout=widgets.Layout(width="70px"))

                duration_label = widgets.Label(layout=widgets.Layout(width="80px"))

                check_boxes.add(check_box)

                def update_duration():
                    duration_label.value = time_helper.duration_str(log_item.duration())

                update_duration()

                def on_check(change):
                    log_item.is_marked = change["new"]
                    update_summary_and_save()

                check_box.observe(on_check, "value")

                def on_name_change(change):
                    log_item.name = change["new"]
                    update_summary_and_save()

                name.observe(debounce.debounced(0.1)(on_name_change), "value")

                def on_start_change(change):
                    log_item.start = time_helper.parse_time(change["new"])
                    update_duration()
                    update_summary_and_save()

                start.observe(on_start_change, "value")

                def on_start_now_click(_):
                    start.value = time_helper.time_str(datetime.datetime.now())

                start_now.on_click(on_start_now_click)

                def on_last_click(_):
                    if index >= 1:
                        last_end = self.logs[index - 1].end
                        if last_end is not None:
                            start.value = time_helper.time_str(last_end)

                last_button.on_click(on_last_click)

                def on_end_change(change):
                    log_item.end = time_helper.parse_time(change["new"])
                    update_duration()
                    update_summary_and_save()

                end.observe(on_end_change, "value")

                def on_end_now_click(_):
                    end.value = time_helper.time_str(datetime.datetime.now())

                end_now.on_click(on_end_now_click)

                return widgets.HBox(children=[
                    check_box, name, start, start_now, last_button, end, end_now, duration_label
                ])

            if update_type is UpdateType.APPEND:
                log_box.children = list(log_box.children) + [log_item_box(self.logs[-1], len(self.logs) - 1)]
            elif update_type is UpdateType.RESET:
                old = log_box.children

                log_box.children = [log_item_box(item, i) for i, item in enumerate(self.logs)]

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

            def update_summary_and_save():
                if suspend_summary_update:
                    return

                total = sum(item.duration() for item in self.logs)
                total_marked = sum(item.duration() for item in self.logs if item.is_marked)
                total_str = time_helper.duration_str(total)
                total_marked_str = time_helper.duration_str(total_marked)
                total_not_marked_str = time_helper.duration_str(total - total_marked)

                summary_label = widgets.Label(
                    value="Total: {}. Total marked: {}. Not marked {}.".format(
                        total_str, total_marked_str, total_not_marked_str),
                    layout=widgets.Layout(width="100%", max_width="100%")
                )

                summary_box.children = LogItem.item_htmls(self.logs, False) + [summary_label]

                self.save()

            update_summary_and_save()

        update(UpdateType.RESET)

    def save(self):
        if self.file is None:
            return

        try:
            with open(self.file, mode="w") as f:
                array = []
                for log in self.logs:
                    dic = {
                        "name": log.name,
                        "start_str": time_helper.time_str(log.start),
                        "end_str": time_helper.time_str(log.end),
                        "is_marked": log.is_marked
                    }

                    array.append(dic)

                json.dump(array, f)
        except OSError:
            print("File open fail")
