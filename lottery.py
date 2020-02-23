import datetime
from dataclasses import dataclass
import random

from time_helper import parse_duration, time_str, duration_str


@dataclass
class LotterySetting:
    # The total plan time a day in seconds, such as 8 * 3600
    total_time: float

    # Bonus ratio when you complete the task using time less than the first plan time, such as 1.0
    first_plan_bonus: float

    # Bonus ratio when you complete the task using time less than the second plan time, such as 0.5
    second_plan_bonus: float

    # The expected total winning time when the `total_time` of tasks are completed, such as 1800
    expected_total_win: float

    # The time that is accumulated for later lottery, used to reduce the variance, such as 0.5.
    # 0.0 means vanilla geometric distribution.
    # The value should be greater than or equal to 0.0 and less than or equal to 1.0
    accumulate_later_ratio: float


@dataclass
class LotteryContext:
    accumulated_time: float = 0.0


random.seed()


def draw_lottery(actual: str, first_plan: str, second_plan: str, winning: str,
                 setting: LotterySetting, context: LotteryContext):
    """Draw the lottery

    When you complete a task, you can use this lottery game to reward you some extra time.

    :param actual: the actual finish time of the task
    :param first_plan: the first plan time of the task that you've just finished
    :param second_plan: the second plan time of the task
    :param winning: the time you get when you win the lottery
    :param setting:
    :return: When win, returns "You win!!!" otherwise some random encouraging sentences.
    """

    actual_duration: float = parse_duration(actual)
    first_plan_duration: float = parse_duration(first_plan)
    second_plan_duration: float = parse_duration(second_plan)
    winning_duration: float = parse_duration(winning)
    assert actual_duration is not None, f"Unexpected `actual` time: {actual}"
    assert first_plan_duration is not None, f"Unexpected `first_plan` time {first_plan}"
    assert second_plan_duration is not None, f"Unexpected `second_plan` time {second_plan}"
    assert winning_duration is not None, f"Unexpected `winning` time {winning_duration}"

    assert first_plan_duration <= second_plan_duration, "First plan time should be less than second plan time."

    duration = second_plan_duration

    if actual_duration > second_plan_duration:
        pass
    elif actual_duration > first_plan_duration:
        duration += (second_plan_duration - actual_duration) * setting.second_plan_bonus
    else:
        duration += (second_plan_duration - first_plan_duration) * setting.second_plan_bonus
        duration += (first_plan_duration - actual_duration) * setting.first_plan_bonus

    # The mathematical expectation of the winning time
    expected_winning = duration * setting.expected_total_win / setting.total_time

    accumulate_later = expected_winning * setting.accumulate_later_ratio

    win: bool
    if context.accumulated_time + expected_winning < winning_duration:
        p = (expected_winning - accumulate_later) / (winning_duration - context.accumulated_time - accumulate_later)
        win = random.random() < p
        if win:
            context.accumulated_time = 0
        else:
            context.accumulated_time += accumulate_later
    else:
        win = True
        context.accumulated_time = context.accumulated_time + expected_winning - winning_duration

    print(time_str(datetime.datetime.now()))

    if win:
        print("CONGRATULATIONS! YOU WIN!")
    else:
        sentence = random.choice([
            "Cheer up!",
            "Fantastic!",
            "Good for you!",
            "Great!",
            "I'm so proud of me!",
            "I’m impressed!",
            "Keep fighting!",
            "Keep going!",
            "Keep it up!",
            "Keep on trying!",
            "Keep pushing!",
            "Keep up the good work!",
            "Keep up the great work!",
            "Keep up the hard work!",
            "Marvelous!",
            "Nice going!",
            "Nothing can stop you now!",
            "Outstanding!",
            "Play up!",
            "Sensational!",
            "Stay the course!",
            "Super-duper!",
            "Tremendous!",
            "You’re getting better and better!",
            "You’re getting better every day!",
        ])
        print(sentence)

    if context.accumulated_time > 0:
        print(f"(Accumulated for next {duration_str(context.accumulated_time)})")
