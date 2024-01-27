def deduceCadenceString(seconds):
    if seconds is None:
        return ''
    from math import floor
    daySeconds = floor(seconds/24/60/60)
    aggregate = []
    if (daySeconds > 0):
        aggregate.append(f'{daySeconds} days')
        seconds = seconds - (daySeconds*24*60*60)
    hourSeconds = floor(seconds/60/60)
    if (hourSeconds > 0):
        aggregate.append(f'{hourSeconds} hrs')
        seconds = seconds - (hourSeconds*60*60)
    minuteSeconds = floor(seconds/60)
    if (minuteSeconds > 0):
        aggregate.append(f'{minuteSeconds} mins')
        seconds = seconds - (minuteSeconds*60)
    if (seconds > 0):
        aggregate.append(f'{seconds} secs')
    return ','.join(aggregate)


def deduceOffsetString(seconds):
    if seconds is None:
        return ''
    from math import floor
    aggregate = []
    hourSeconds = floor(seconds/60/60)
    if (hourSeconds > 0):
        aggregate.append(f'{hourSeconds} hrs')
        seconds = seconds - (hourSeconds*60*60)
    minuteSeconds = floor(seconds/60)
    if (minuteSeconds > 0):
        aggregate.append(f'{minuteSeconds} mins')
        seconds = seconds - (minuteSeconds*60)
    if (seconds > 0):
        aggregate.append(f'{seconds} secs')
    return ','.join(aggregate)
