from config import KILL_POINT, PLACEMENT_POINTS


def calculate(placement, kills):
    placement_points = PLACEMENT_POINTS.get(placement, 0)
    kill_points = max(0, kills) * KILL_POINT
    return placement_points, kill_points, placement_points + kill_points
