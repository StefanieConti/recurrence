import datetime as dt
import unittest

from recurrence import Rule, iter_recurrences, parse


class TestRuleValidation(unittest.TestCase):
    def test_freq_must_be_supported(self):
        with self.assertRaises(ValueError):
            Rule(freq="YEARLY", dtstart=dt.datetime(2024, 1, 1))

    def test_interval_must_be_positive(self):
        with self.assertRaises(ValueError):
            Rule(freq="DAILY", dtstart=dt.datetime(2024, 1, 1), interval=0)

    def test_count_must_be_positive(self):
        with self.assertRaises(ValueError):
            Rule(freq="DAILY", dtstart=dt.datetime(2024, 1, 1), count=0)

    def test_daily_rejects_byday(self):
        with self.assertRaises(ValueError):
            Rule(freq="DAILY", dtstart=dt.datetime(2024, 1, 1), byday=["MO"])

    def test_weekly_rejects_bymonthday(self):
        with self.assertRaises(ValueError):
            Rule(freq="WEEKLY", dtstart=dt.datetime(2024, 1, 1), bymonthday=[15])

    def test_invalid_weekday_code(self):
        with self.assertRaises(ValueError):
            Rule(freq="WEEKLY", dtstart=dt.datetime(2024, 1, 1), byday=["XX"])

    def test_bymonthday_out_of_range(self):
        with self.assertRaises(ValueError):
            Rule(freq="MONTHLY", dtstart=dt.datetime(2024, 1, 1), bymonthday=[32])


class TestDaily(unittest.TestCase):
    def test_basic_daily(self):
        rule = Rule(freq="DAILY", dtstart=dt.datetime(2024, 1, 1), count=3)
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 2),
            dt.datetime(2024, 1, 3),
        ])

    def test_daily_interval(self):
        rule = Rule(freq="DAILY", dtstart=dt.datetime(2024, 1, 1), interval=2, count=3)
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 3),
            dt.datetime(2024, 1, 5),
        ])

    def test_daily_until_inclusive(self):
        rule = Rule(
            freq="DAILY",
            dtstart=dt.datetime(2024, 1, 1),
            until=dt.datetime(2024, 1, 3),
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(len(result), 3)

    def test_daily_until_excludes_after(self):
        rule = Rule(
            freq="DAILY",
            dtstart=dt.datetime(2024, 1, 1),
            until=dt.datetime(2024, 1, 1, 12, 0, 0),
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [dt.datetime(2024, 1, 1)])

    def test_daily_preserves_time(self):
        rule = Rule(
            freq="DAILY",
            dtstart=dt.datetime(2024, 1, 1, 9, 30, 0),
            count=2,
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result[1].hour, 9)
        self.assertEqual(result[1].minute, 30)


class TestWeekly(unittest.TestCase):
    def test_weekly_no_byday(self):
        rule = Rule(freq="WEEKLY", dtstart=dt.datetime(2024, 1, 1), count=3)
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 8),
            dt.datetime(2024, 1, 15),
        ])

    def test_weekly_byday(self):
        rule = Rule(
            freq="WEEKLY",
            dtstart=dt.datetime(2024, 1, 1),
            byday=["MO", "WE"],
            count=4,
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 3),
            dt.datetime(2024, 1, 8),
            dt.datetime(2024, 1, 10),
        ])

    def test_weekly_byday_interval(self):
        rule = Rule(
            freq="WEEKLY",
            dtstart=dt.datetime(2024, 1, 1),
            byday=["MO"],
            interval=2,
            count=3,
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 15),
            dt.datetime(2024, 1, 29),
        ])

    def test_weekly_byday_until(self):
        rule = Rule(
            freq="WEEKLY",
            dtstart=dt.datetime(2024, 1, 1),
            byday=["TU"],
            until=dt.datetime(2024, 1, 10),
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [dt.datetime(2024, 1, 2), dt.datetime(2024, 1, 9)])


class TestMonthly(unittest.TestCase):
    def test_monthly_basic(self):
        rule = Rule(freq="MONTHLY", dtstart=dt.datetime(2024, 1, 15), count=3)
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 15),
            dt.datetime(2024, 2, 15),
            dt.datetime(2024, 3, 15),
        ])

    def test_monthly_skips_february_30(self):
        rule = Rule(freq="MONTHLY", dtstart=dt.datetime(2024, 1, 31), count=3)
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 31),
            dt.datetime(2024, 3, 31),
            dt.datetime(2024, 5, 31),
        ])

    def test_monthly_bymonthday_positive(self):
        rule = Rule(
            freq="MONTHLY",
            dtstart=dt.datetime(2024, 1, 1),
            bymonthday=[1, 15],
            count=4,
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 15),
            dt.datetime(2024, 2, 1),
            dt.datetime(2024, 2, 15),
        ])

    def test_monthly_bymonthday_negative(self):
        rule = Rule(
            freq="MONTHLY",
            dtstart=dt.datetime(2024, 1, 1),
            bymonthday=[-1],
            count=3,
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 31),
            dt.datetime(2024, 2, 29),
            dt.datetime(2024, 3, 31),
        ])

    def test_monthly_byday(self):
        rule = Rule(
            freq="MONTHLY",
            dtstart=dt.datetime(2024, 1, 1),
            byday=["MO"],
            count=4,
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 8),
            dt.datetime(2024, 1, 15),
            dt.datetime(2024, 1, 22),
        ])

    def test_monthly_byday_and_bymonthday_intersection(self):
        rule = Rule(
            freq="MONTHLY",
            dtstart=dt.datetime(2024, 1, 1),
            byday=["MO"],
            bymonthday=[15],
            count=3,
        )
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 15),
            dt.datetime(2024, 4, 15),
            dt.datetime(2024, 7, 15),
        ])


class TestParse(unittest.TestCase):
    def test_parse_daily(self):
        rule = parse("RRULE:FREQ=DAILY;DTSTART=20240101T000000;COUNT=3")
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 2),
            dt.datetime(2024, 1, 3),
        ])

    def test_parse_weekly_byday(self):
        rule = parse("RRULE:FREQ=WEEKLY;DTSTART=20240101T000000;BYDAY=MO,WE;COUNT=4")
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 1),
            dt.datetime(2024, 1, 3),
            dt.datetime(2024, 1, 8),
            dt.datetime(2024, 1, 10),
        ])

    def test_parse_monthly_bymonthday(self):
        rule = parse("RRULE:FREQ=MONTHLY;DTSTART=20240101T000000;BYMONTHDAY=15;COUNT=3")
        result = list(iter_recurrences(rule))
        self.assertEqual(result, [
            dt.datetime(2024, 1, 15),
            dt.datetime(2024, 2, 15),
            dt.datetime(2024, 3, 15),
        ])

    def test_parse_until(self):
        rule = parse("RRULE:FREQ=DAILY;DTSTART=20240101T000000;UNTIL=20240103T000000")
        result = list(iter_recurrences(rule))
        self.assertEqual(len(result), 3)

    def test_parse_rejects_unknown_part(self):
        with self.assertRaises(ValueError):
            parse("RRULE:FREQ=DAILY;DTSTART=20240101T000000;BYHOUR=10")

    def test_parse_requires_rrule_prefix(self):
        with self.assertRaises(ValueError):
            parse("FREQ=DAILY;DTSTART=20240101T000000")

    def test_parse_requires_freq(self):
        with self.assertRaises(ValueError):
            parse("RRULE:DTSTART=20240101T000000")

    def test_parse_requires_dtstart(self):
        with self.assertRaises(ValueError):
            parse("RRULE:FREQ=DAILY")


if __name__ == "__main__":
    unittest.main()
