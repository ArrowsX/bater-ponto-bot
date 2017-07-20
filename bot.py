import logging
import calendar
import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table, Column, Date, Integer, BigInteger, String
from telegram.ext import Updater, CommandHandler

from credentials import CONNECTION, TOKEN  # Constants from credentials.py -> your choice

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
metadata = MetaData()

ponto = Table('ponto', metadata,
    Column('id', Integer, primary_key=True),
    Column('date', Date, index=True),
    Column('first_name', String(120)),
    Column('last_name', String(120)),
    Column('user_id', BigInteger, index=True),
    Column('arrival_time', String(5)),
    Column('lunch_start', String(5)),
    Column('lunch_back', String(5)),
    Column('leave_time', String(5)),
)

engine = create_engine(CONNECTION)  # Default to 'sqlite:///ponto.db'


def get_missing_time_field(user_id, date=dt.date.today()):
    result = engine.execute(
        ponto.select()
        .where(ponto.c.date == date)
        .where(ponto.c.user_id == user_id)
    ).fetchone()

    if result:
        if not result.lunch_start:
            return 'lunch_start'
        if not result.lunch_back:
            return 'lunch_back'
        if not result.leave_time:
            return 'leave_time'
    else:
        return 'arrival_time'


def register_time_to_mysql(user, time_field, time, date=dt.date.today()):
    row = {
        'date': date,
        'first_name': user['first_name'],
        'last_name': user['last_name'],
        'user_id': user['id'],
    }

    result = engine.execute(
        ponto.select()
        .where(ponto.c.date == date)
        .where(ponto.c.user_id == user['id'])
    ).fetchone()

    if result:
        row[time_field] = time

        engine.execute(
            ponto.update()
            .where(ponto.c.date == date)
            .where(ponto.c.user_id == user['id'])
            .values(**row)
        )

    else:
        row[time_field] = time  # Not overwrite arrival time
        engine.execute(ponto.insert().values(**row))


def lunch_calculation(lunch_start, lunch_back):
    diff = time_difference(lunch_start, lunch_back)
    if time_difference(diff, '1:30').startswith('-'):
        return diff
    else:
        return '1:00'


def get_remaining_time(user_id, date=dt.date.today()):
    result = engine.execute(
        ponto.select()
        .where(ponto.c.date == date)
        .where(ponto.c.user_id == user_id)
    ).fetchone()

    if result.leave_time:
        work_time = time_difference(result.arrival_time, result.leave_time)
    else:
        current_time = dt.datetime.now().strftime('%H:%M')
        work_time = time_difference(result.arrival_time, current_time)

    lunch_time = lunch_calculation(result.lunch_start, result.lunch_back)

    actual_time = time_difference(lunch_time, work_time)

    remaining_time = time_difference('8:00', actual_time)
    if remaining_time.startswith('-'):
        return remaining_time
    else:
        if time_difference('2:00', remaining_time).startswith('-'):
            return remaining_time
        else:
            return '2:00'


def str_to_datetime(time, fmt='%H:%M'):
    return dt.datetime.strptime(time, fmt)


def time_sum(*time_list):
    total = dt.timedelta()
    for time in time_list:
        h, m = time.split(':')
        total += dt.timedelta(hours=int(h), minutes=int(m))

    seconds = int(total.total_seconds())
    return '{0}:{1:02d}'.format(seconds//3600, seconds//60 % 60)


def time_difference(start_time, end_time):
    diff = str_to_datetime(end_time) - str_to_datetime(start_time)
    logging.info('{} - {}'.format(end_time, start_time))
    seconds = int(diff.total_seconds())
    if seconds < 0:
        return '-{0}:{1:02d}'.format(-seconds//3600, seconds//60 % 60)
    else:
        return '{0}:{1:02d}'.format(seconds//3600, seconds//60 % 60)


def current_month_date_range(date=dt.date.today()):
    total_days = calendar.monthrange(date.year, date.month)[1]

    start = dt.date(date.year, date.month, 1)
    end = dt.date(date.year, date.month, total_days)

    return start, end


def hour_bank_record(user_id, date=dt.date.today()):
    start_date, end_date = current_month_date_range(date)

    time_list = list()
    for row in engine.execute(
            ponto.select()
            .where(ponto.c.date >= start_date)
            .where(ponto.c.date <= end_date)
            .where(ponto.c.user_id == user_id)
            .where(ponto.c.leave_time != None)
    ):
        time = get_remaining_time(user_id, row.date)
        time_list.append(time)

    return time_sum(*time_list)


def set_day_off(user_id, date=dt.date.today()):
    engine.execute(
        ponto.insert().values(
            user_id=user_id,
            date=date,
            arrival_time='8:00',
            lunch_start='8:00',
            lunch_back='9:00',
            leave_time='9:00'
        )
    )


def start(bot, update):
    messages = [
        'Lista de comandos:',
        '/ponto - Registrar o meu ponto',
        '/embora - Eu já posso ir embora? Quanto de banco eu fiz?',
        '/situacao - Total de banco de horas nesse mês',
    ]

    update.message.reply_text('\n'.join(messages))


def register_time(bot, update):
    user = update.message.from_user
    time = dt.datetime.now().strftime('%H:%M')
    missing_time_field = get_missing_time_field(user.id)

    if missing_time_field:
        register_time_to_mysql(user, missing_time_field, time)
        update.message.reply_text('%s registrado' % missing_time_field)
    else:
        # TODO: Check if user can leave first
        update.message.reply_text('Chega de trabalhar, tchau!')


def can_i_leave(bot, update):
    user = update.message.from_user
    remaining_time = get_remaining_time(user.id).replace(':', 'h')

    if remaining_time.startswith('-'):
        update.message.reply_text('Calma, ainda falta %s' % remaining_time[1:])
    else:
        update.message.reply_text('Pode ir, você já fez %s de banco hoje' % remaining_time)


def hour_bank_report(bot, update):
    user_id = update.message.from_user.id
    accumulated_hours = hour_bank_record(user_id).replace(':', 'h')

    if accumulated_hours.startswith('-'):
        update.message.reply_text('Você está devendo %s esse mês' % accumulated_hours[1:])
    else:
        update.message.reply_text('Você tem um total de %s de banco' % accumulated_hours)


def one_day_off(bot, update):
    user_id = update.message.from_user.id
    set_day_off(user_id)
    update.message.reply_text('Desconto de 8 horas no banco')

    accumulated_hours = hour_bank_record(user_id).replace(':', 'h')

    if accumulated_hours.startswith('-'):
        update.message.reply_text('Você está devendo %s esse mês' % accumulated_hours[1:])
    else:
        update.message.reply_text('Você tem um total de %s de banco' % accumulated_hours)


def main():
    metadata.create_all(engine)
    updater = Updater(TOKEN)  # Get your token from BotFather
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("ponto", register_time))
    dispatcher.add_handler(CommandHandler("embora", can_i_leave))
    dispatcher.add_handler(CommandHandler("situacao", hour_bank_report))
    dispatcher.add_handler(CommandHandler("faltei", one_day_off))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
