import math
from datetime import datetime, timedelta, timezone
import requests


# ----------------------------
# Helpers
# ----------------------------
ns = None
import hashlib

def hash_api_secret(secret: str) -> str:
    return hashlib.sha1(secret.encode("utf-8")).hexdigest()
def utcnow():
    return datetime.now(timezone.utc)


def parse_time(t):
    # Nightscout ISO format
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


# ----------------------------
# Insulin action curve (Nightscout-like approximation)
# ----------------------------

def insulin_activity_curve(t_hours, dia):
    """
    Approximation of insulin activity curve.
    Returns fraction of insulin activity remaining.
    """
    if t_hours <= 0:
        return 1.0
    if t_hours >= dia:
        return 0.0

    # exponential decay approximation
    # tuned to resemble Nightscout/OpenAPS curves
    tau = dia / 3.0
    return math.exp(-t_hours / tau)


def insulin_remaining(amount, age_hours, dia):
    return amount * insulin_activity_curve(age_hours, dia)


# ----------------------------
# Fetch Nightscout data
# ----------------------------

def get_profile(ns_url, api_secret):
    r = requests.get(
        f"{ns_url}/api/v1/profile/current",
        headers={"api-secret": api_secret}
    )
    r.raise_for_status()
    return r.json()


def get_treatments(ns_url, api_secret, start_time):
    r = requests.get(
        f"{ns_url}/api/v1/treatments.json",
        params={"find[created_at][$gte]": start_time.isoformat()},
        headers={"api-secret": api_secret}
    )
    r.raise_for_status()
    return r.json()


# ----------------------------
# Basal schedule lookup
# ----------------------------

def get_current_basal(profile):
    prof = profile["store"][profile["defaultProfile"]]
    schedule = prof["basal"]

    now = utcnow().time()

    current = schedule[0]["value"]
    for entry in schedule:
        h, m = map(int, entry["time"].split(":"))
        if now >= datetime(2000,1,1,h,m).time():
            current = entry["value"]

    return current


# ----------------------------
# IOB calculation
# ----------------------------

def calculate_iob(treatments, basal_schedule, dia):
    now = utcnow()

    bolus_iob = 0.0
    basal_iob = 0.0

    # --------------------
    # Boluses
    # --------------------
    for t in treatments:
        if not t.get("insulin"):
            continue

        age = (now - parse_time(t["created_at"])).total_seconds() / 3600
        bolus_iob += insulin_remaining(t["insulin"], age, dia)

    # --------------------
    # Basal (micro-bolus method)
    # --------------------

    # simulate last 6 hours (enough for most DIA ranges)
    step_min = 5
    steps = int((dia * 60) / step_min)

    for i in range(steps):
        t = now - timedelta(minutes=i * step_min)
        age = (now - t).total_seconds() / 3600

        basal_rate = basal_schedule_at_time(basal_schedule, t)
        units = basal_rate * (step_min / 60)

        basal_iob += insulin_remaining(units, age, dia)

    return bolus_iob, basal_iob


def basal_schedule_at_time(schedule, dt):
    t = dt.time()

    current = schedule[0]["value"]
    for entry in schedule:
        h, m = map(int, entry["time"].split(":"))
        if t >= datetime(2000,1,1,h,m).time():
            current = entry["value"]

    return current


# ----------------------------
# Main entry
# ----------------------------

def compute_iob(ns_url, api_secret):
    profile = get_profile(ns_url, api_secret)

    dia = profile.get("dia", 4)

    basal_schedule = profile["store"][profile["defaultProfile"]]["basal"]

    start_time = utcnow() - timedelta(hours=dia)

    treatments = get_treatments(ns_url, api_secret, start_time)

    bolus_iob, basal_iob = calculate_iob(
        treatments,
        basal_schedule,
        dia
    )

    return {
        "iob": bolus_iob + basal_iob,
        "bolusiob": bolus_iob,
        "basaliob": basal_iob
    }