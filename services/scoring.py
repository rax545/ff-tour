from config import PLACEMENT_POINTS,KILL_POINT
def calculate(placement,kills):
    pp=PLACEMENT_POINTS.get(placement,0); kp=max(0,kills)*KILL_POINT; return pp,kp,pp+kp
