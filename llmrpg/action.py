from enum import Enum

class Action(str, Enum):
    """Enum representing player actions"""
    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    MOVE_UP = "move_up"
    MOVE_DOWN = "move_down"
