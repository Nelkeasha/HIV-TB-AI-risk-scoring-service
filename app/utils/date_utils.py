from datetime import date, timedelta


def days_ago(n: int) -> date:
    return date.today() - timedelta(days=n)


def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]
