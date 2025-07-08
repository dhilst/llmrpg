import pygame
from typing import Protocol

from llmrpg.direction import Direction
from llmrpg.action import Action

class Player(Protocol):
    moving: bool
    def move(self, direction: Direction, current_time: int) -> bool: ...
    def act(self, action: Action, current_time: int) -> bool: ...

class Controller[T](Protocol):
    def __init__(self, player: Player): ...
    def handle_event(self, event: T, current_time: int) -> bool: ...

class PygameController(Controller[pygame.Event]):
    def __init__(self, player: Player):
        self.player = player

    def handle_event(self, event: pygame.Event, current_time: int) -> bool:
        if event.type == pygame.KEYDOWN:
            # Control player (boy) with arrow keys only if not moving
            if not self.player.moving:
                if event.key == pygame.K_LEFT:
                    self.player.act(Action.MOVE_UP, current_time)
                    return True
                elif event.key == pygame.K_RIGHT:
                    self.player.act(Action.MOVE_RIGHT, current_time)
                    return True
                elif event.key == pygame.K_UP:
                    self.player.act(Action.MOVE_UP, current_time)
                    return True
                elif event.key == pygame.K_DOWN:
                    self.player.act(Action.MOVE_DOWN, current_time)
                    return True
            return False
        return False

