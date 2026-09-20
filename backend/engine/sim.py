"""Шаг 6. SIM — прогон смены фиксированным тиком (§10).

Пишется вручную, не на SimPy: нужен плотный массив позиций по времени для анимации.
"""

from __future__ import annotations

from .models import CalcRequest, Plan, Scenario, ShiftRun, SimEvent, TraceStep


def run(
    req: CalcRequest, scenario: Scenario, plan: Plan, *, tick_s: float = 0.5
) -> tuple[ShiftRun, list[TraceStep]]:
    # TODO(E5): реальный прогон парка по маршрутам плана; пересчёт с N+1 при загрузке > 95 %.
    # Заглушка §13.1: один робот, сто событий по первому маршруту.
    route = plan.routes[0] if plan.routes else None
    events: list[SimEvent] = []
    if route is not None:
        pts = route.points
        for i in range(100):
            k = i / 99
            seg = min(int(k * (len(pts) - 1)), len(pts) - 2)
            local = k * (len(pts) - 1) - seg
            x = pts[seg][0] + (pts[seg + 1][0] - pts[seg][0]) * local
            y = pts[seg][1] + (pts[seg + 1][1] - pts[seg][1]) * local
            events.append(SimEvent(t=i * tick_s, robot_id="R1", x=x, y=y, state="moving"))

    run_ = ShiftRun(
        tick_s=tick_s,
        duration_s=req.site.shift_hours * 3600,
        fleet_size=1,
        utilization=0.0,
        charge_queue_max=0,
        completed_ops=0,
        events=events,
    )
    return run_, [TraceStep(step="sim", message="Симуляция смены — заглушка, 100 событий")]
