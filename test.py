import datetime as dt
import unittest

import bot


class BaterPontoTest(unittest.TestCase):

    def setUp(self):
        bot.ponto.create(bot.engine)

    def tearDown(self):
        bot.ponto.drop(bot.engine)

    def test_get_missing_time_field(self):
        time_field = bot.get_missing_time_field(12345678)
        self.assertEqual(time_field, 'arrival_time')

        bot.engine.execute(
            bot.ponto.insert().values(
                user_id=12345678,
                date=dt.date.today(),
                arrival_time='8:00'
            )
        )
        time_field = bot.get_missing_time_field(12345678)
        self.assertEqual(time_field, 'lunch_start')

        bot.engine.execute(
            bot.ponto.update()
            .where(bot.ponto.c.user_id == 12345678)
            .values(
                lunch_start='12:00'
            )
        )
        time_field = bot.get_missing_time_field(12345678)
        self.assertEqual(time_field, 'lunch_back')

        bot.engine.execute(
            bot.ponto.update()
            .where(bot.ponto.c.user_id == 12345678)
            .values(
                lunch_back='13:00'
            )
        )
        time_field = bot.get_missing_time_field(12345678)
        self.assertEqual(time_field, 'leave_time')

        bot.engine.execute(
            bot.ponto.update()
            .where(bot.ponto.c.user_id == 12345678)
            .values(
                leave_time='17:00'
            )
        )
        time_field = bot.get_missing_time_field(12345678)
        self.assertIsNone(time_field)

    def test_register_time_to_mysql(self):
        user = {
            'date': dt.date.today(),
            'first_name': 'Test',
            'last_name': 'Script',
            'id': 12345678,
        }

        bot.register_time_to_mysql(user, 'arrival_time', '8:00')

        result = bot.engine.execute(
            bot.ponto.select()
            .where(bot.ponto.c.user_id == 12345678)
        ).fetchone()

        self.assertEqual(result.arrival_time, '8:00')
        self.assertIsNone(result.leave_time)

        bot.register_time_to_mysql(user, 'leave_time', '17:00')

        results = bot.engine.execute(
            bot.ponto.select()
            .where(bot.ponto.c.user_id == 12345678)
        ).fetchall()

        self.assertEqual(len(results), 1)

        self.assertEqual(results[0].arrival_time, '8:00')
        self.assertIsNotNone(results[0].leave_time)

    def test_lunch_calculation(self):
        self.assertEqual(bot.lunch_calculation('12:00', '13:00'), '1:00')
        self.assertEqual(bot.lunch_calculation('12:00', '12:30'), '1:00')
        self.assertEqual(bot.lunch_calculation('12:00', '13:29'), '1:00')
        self.assertEqual(bot.lunch_calculation('12:00', '13:31'), '1:31')

    def test_get_remaining_time(self):
        bot.engine.execute(
            bot.ponto.insert().values(
                user_id=12345678,
                date=dt.date.today(),
                arrival_time='8:00',
                lunch_start='12:00',
                lunch_back='13:29',
                leave_time='16:30',
            )
        )

        self.assertEqual(bot.get_remaining_time(12345678), '-0:30')

        bot.engine.execute(
            bot.ponto.update()
            .where(bot.ponto.c.user_id == 12345678)
            .values(
                leave_time='17:00'
            )
        )

        self.assertEqual(bot.get_remaining_time(12345678), '0:00')

        bot.engine.execute(
            bot.ponto.update()
            .where(bot.ponto.c.user_id == 12345678)
            .values(
                leave_time='18:30'
            )
        )

        self.assertEqual(bot.get_remaining_time(12345678), '1:30')

        bot.engine.execute(
            bot.ponto.update()
            .where(bot.ponto.c.user_id == 12345678)
            .values(
                leave_time='19:30'
            )
        )

        self.assertEqual(bot.get_remaining_time(12345678), '2:00')

    def test_str_to_datetime(self):
        self.assertEqual(bot.str_to_datetime('1:00'), dt.datetime(1900, 1, 1, 1, 0))

    def test_time_sum(self):
        times = ['1:00', '2:00', '3:00']
        self.assertEqual(bot.time_sum(*times), '6:00')

        times = ['1:00', '-2:00', '3:00']
        self.assertEqual(bot.time_sum(*times), '2:00')

        times = ['1:00', '-2:00', '-3:00']
        self.assertEqual(bot.time_sum(*times), '-4:00')

        times = ['0:00', '0:00', '-1:00']
        self.assertEqual(bot.time_sum(*times), '-1:00')

    def test_time_difference(self):
        self.assertEqual(bot.time_difference('1:00', '2:00'), '1:00')
        self.assertEqual(bot.time_difference('2:00', '1:00'), '-1:00')
        self.assertEqual(bot.time_difference('8:30', '8:00'), '-0:30')
        self.assertEqual(bot.time_difference('8:30', '0:00'), '-8:30')

    def test_current_month_date_range(self):
        date = dt.date(2017, 1, 15)
        start_date, end_date = bot.current_month_date_range(date)
        self.assertEqual(start_date, dt.date(2017, 1, 1))
        self.assertEqual(end_date, dt.date(2017, 1, 31))

        date = dt.date(2016, 2, 15)
        start_date, end_date = bot.current_month_date_range(date)
        self.assertEqual(start_date, dt.date(2016, 2, 1))
        self.assertEqual(end_date, dt.date(2016, 2, 29))

    def test_hour_bank_record(self):
        date = dt.date(2017, 1, 15)

        bot.engine.execute(
            bot.ponto.insert().values(
                user_id=12345678,
                date=dt.date(2017, 1, 1),
                arrival_time='8:00',
                lunch_start='12:00',
                lunch_back='13:29',
                leave_time='17:00',
            )
        )

        self.assertEqual(bot.hour_bank_record(12345678, date), '0:00')

        bot.engine.execute(
            bot.ponto.insert().values(
                user_id=12345678,
                date=dt.date(2017, 1, 2),
                arrival_time='8:00',
                lunch_start='12:00',
                lunch_back='13:29',
                leave_time='18:00',
            )
        )

        self.assertEqual(bot.hour_bank_record(12345678, date), '1:00')

        bot.engine.execute(
            bot.ponto.insert().values(
                user_id=12345678,
                date=dt.date(2017, 1, 3),
                arrival_time='8:00',
                lunch_start='12:00',
                lunch_back='13:29',
                leave_time='15:00',
            )
        )

        self.assertEqual(bot.hour_bank_record(12345678, date), '-1:00')

        bot.engine.execute(
            bot.ponto.insert().values(
                user_id=12345678,
                date=dt.date(2017, 1, 4),
                arrival_time='8:00',
                lunch_start='8:00',
                lunch_back='9:00',
                leave_time='9:00',
            )
        )

        self.assertEqual(bot.hour_bank_record(12345678, date), '-9:00')

    def test_one_day_off(self):
        bot.set_day_off(12345678)

        result = bot.engine.execute(bot.ponto.select()).fetchone()
        self.assertEqual(result.date, dt.date.today())

        self.assertEqual(bot.hour_bank_record(12345678), '-8:00')
