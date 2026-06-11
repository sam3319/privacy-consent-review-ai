def calculate_wage_estimate(
    hourly_wage: int | float = 0,
    regular_hours: int | float = 0,
    overtime_hours: int | float = 0,
    night_hours: int | float = 0,
    holiday_hours: int | float = 0,
    workplace_has_five_or_more: bool = True,
    monthly_ordinary_wage: int | float = 0,
    monthly_standard_hours: int | float = 209,
    weekly_paid_holiday_hours: int | float = 0,
) -> dict | None:
    monthly_wage = max(float(monthly_ordinary_wage or 0), 0)
    monthly_hours = max(float(monthly_standard_hours or 0), 0)
    wage = max(float(hourly_wage or 0), 0)
    if not wage and monthly_wage and monthly_hours:
        wage = monthly_wage / monthly_hours
    regular = max(float(regular_hours or 0), 0)
    overtime = max(float(overtime_hours or 0), 0)
    night = max(float(night_hours or 0), 0)
    holiday = max(float(holiday_hours or 0), 0)
    paid_holiday = max(float(weekly_paid_holiday_hours or 0), 0)
    if not wage or not any((regular, overtime, night, holiday)):
        return None

    premium_rate = 0.5 if workplace_has_five_or_more else 0
    regular_pay = wage * regular
    overtime_pay = wage * overtime * (1 + premium_rate)
    night_premium = wage * night * premium_rate
    holiday_first_eight = min(holiday, 8)
    holiday_over_eight = max(holiday - 8, 0)
    holiday_pay = (
        wage * holiday_first_eight * (1 + premium_rate)
        + wage
        * holiday_over_eight
        * (2 if workplace_has_five_or_more else 1)
    )
    paid_holiday_pay = wage * paid_holiday
    total = (
        regular_pay
        + overtime_pay
        + night_premium
        + holiday_pay
        + paid_holiday_pay
    )
    warnings = []
    if not workplace_has_five_or_more:
        warnings.append(
            "5인 미만 사업장 선택으로 연장·야간·휴일 가산율을 0%로 계산했습니다. "
            "업종·근로형태·적용 조항을 별도 확인해야 합니다."
        )
    if overtime > 12:
        warnings.append("입력한 주간 연장근로가 12시간을 초과합니다.")
    if regular + overtime > 52:
        warnings.append("입력한 주간 근로시간이 52시간을 초과합니다.")
    if night > regular + overtime + holiday:
        warnings.append("야간근로 시간이 전체 입력 근로시간보다 큽니다.")

    return {
        "inputs": {
            "hourly_wage": round(wage),
            "monthly_ordinary_wage": round(monthly_wage),
            "monthly_standard_hours": monthly_hours,
            "regular_hours": regular,
            "overtime_hours": overtime,
            "night_hours": night,
            "holiday_hours": holiday,
            "weekly_paid_holiday_hours": paid_holiday,
            "workplace_has_five_or_more": workplace_has_five_or_more,
        },
        "regular_pay": round(regular_pay),
        "overtime_pay": round(overtime_pay),
        "night_premium": round(night_premium),
        "holiday_pay": round(holiday_pay),
        "paid_holiday_pay": round(paid_holiday_pay),
        "weekly_total": round(total),
        "premium_rate": premium_rate,
        "warnings": warnings,
        "disclaimer": (
            "입력한 통상시급 또는 월 통상임금 환산값을 사용합니다. 주휴수당 발생요건, "
            "통상임금 산입범위, 포괄임금, 탄력·선택근로제, 감시·단속적 근로와 "
            "사업장별 적용 예외는 자동 확정하지 않습니다."
        ),
    }
