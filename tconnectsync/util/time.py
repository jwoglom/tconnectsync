import arrow


def format_datetime(date) -> str:
    """
    Convert any datetime/Arrow-compatible input into
    a Nightscout-safe ISO-8601 UTC timestamp.

    Output example:
        2026-06-30T03:15:22+00:00
    """
    if date is None:
        return None

    return arrow.get(date).to("utc").isoformat()


def format_datetime_local(date) -> str:
    """
    If you ever need local (non-UTC) ISO format.
    Generally NOT recommended for Nightscout uploads.
    """
    if date is None:
        return None

    return arrow.get(date).isoformat()


def parse_time(date):
    """
    Normalize input into an Arrow object.
    Useful for internal processing before formatting.
    """
    if date is None:
        return None

    return arrow.get(date)


def time_range(field_name, start_time, end_time):
    """
    Build Nightscout-compatible query string for time filtering.
    Always uses ISO-8601 timestamps (no spaces, no replacements).
    """
    def fmt(date):
        return format_datetime(date)

    params = ""

    if start_time:
        params += f"&find[{field_name}][$gte]={fmt(start_time)}"

    if end_time:
        params += f"&find[{field_name}][$lte]={fmt(end_time)}"

    return params
