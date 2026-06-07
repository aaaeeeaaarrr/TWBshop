"""Tests for gm_bot/attendance.py — geofence + availability + lateness (pure)."""

from gm_bot import attendance as att


# ── geofence ──────────────────────────────────────────────────────────────────

def test_in_work_zone_at_bakery():
    assert att.in_work_zone(att.TWB_LAT, att.TWB_LNG) is True


def test_just_inside_and_outside_100m():
    # 100m zone (session 28): ~0.0005 deg lat ≈ 55m -> inside; ~0.001 deg ≈ 111m -> outside.
    assert att.in_work_zone(att.TWB_LAT + 0.0005, att.TWB_LNG) is True
    assert att.in_work_zone(att.TWB_LAT + 0.001, att.TWB_LNG) is False


def test_haversine_known_distance():
    d = att.haversine_m(att.TWB_LAT, att.TWB_LNG, att.TWB_LAT + 0.001, att.TWB_LNG)
    assert 100 < d < 125     # ~111m per 0.001 deg latitude


# ── time parsing + overlap ────────────────────────────────────────────────────

def test_to_min():
    assert att.to_min("08:00") == 480
    assert att.to_min("8:30") == 510
    assert att.to_min("2:00pm") == 840
    assert att.to_min("12:00am") == 0
    assert att.to_min("12:00pm") == 720
    assert att.to_min(480) == 480
    assert att.to_min("") is None


def test_overlaps_normal_and_overnight():
    assert att.overlaps(480, 1020, 600, 700) is True     # 8-17 vs 10-11:40
    assert att.overlaps(480, 1020, 1100, 1200) is False  # 8-17 vs 18:20-20
    # overnight shift 22:00-06:00 overlaps a 23:00-01:00 window
    assert att.overlaps(1320, 360, 1380, 60) is True


# ── availability (the senior-approval picture) ────────────────────────────────

def _sched(name, start, end, day_off=""):
    return {"name": name, "work_start": att.to_min(start), "work_end": att.to_min(end), "day_off": day_off}


def test_available_staff_filters_hours_dayoff_and_al():
    schedules = [
        _sched("Lina", "08:00", "17:00"),
        _sched("Seth", "14:00", "22:00"),
        _sched("Davy", "08:00", "17:00", day_off="Tuesday"),  # off Tuesday
        _sched("Nak",  "08:00", "17:00"),
    ]
    # Window 09:00-12:00 on Tuesday; Nak is on AL.
    avail = att.available_staff(att.to_min("09:00"), att.to_min("12:00"), "Tuesday",
                                schedules, on_al_names={"Nak"})
    assert "Lina" in avail
    assert "Seth" not in avail       # starts 14:00, no overlap
    assert "Davy" not in avail       # day off Tuesday
    assert "Nak" not in avail        # on AL
    assert avail == ["Lina"]


def test_available_staff_overlap_at_edges():
    schedules = [_sched("A", "14:00", "22:00")]
    assert att.available_staff(att.to_min("13:00"), att.to_min("15:00"), "Mon", schedules) == ["A"]
    assert att.available_staff(att.to_min("22:00"), att.to_min("23:00"), "Mon", schedules) == []


# ── lateness + outside budget ─────────────────────────────────────────────────

def test_lateness_kind():
    assert att.lateness_kind(att.to_min("07:30"), att.to_min("08:00")) == "before_shift"
    assert att.lateness_kind(att.to_min("08:10"), att.to_min("08:00")) == "already_started"


def test_outside_budget():
    assert att.outside_exceeded(10) is False
    assert att.outside_exceeded(30) is False
    assert att.outside_exceeded(31) is True


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
