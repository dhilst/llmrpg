from typing import Optional, Dict
import pytmx, pygame
from llmrpg.tileset import Tileset

class GameData:
    def __init__(self, tmx_data: pytmx.TiledMap):
        self.tmx_data = tmx_data
        self.objectlayer = self._get_object_layer()
        self.spawn_areas = self._load_spawn_areas()  # Dictionary of spawn areas
        self.characters = Tileset("sprites/characters.tsx")
        self.dead_characters = Tileset("sprites/dead.tsx")
        self.collision_objects = []
        # get_layer_by_name returns an  TiledObjectGroup, not int, which is interable
        # the typehint says it returns int for some reason, so I'm skipping typechecking here
        for obj in tmx_data.get_layer_by_name("Objects"): # type: ignore
            if obj.type == "wall":
                # Create a rect for the collision object
                rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
                self.collision_objects.append(rect)

    def _get_object_layer(self) -> Optional[pytmx.TiledObjectGroup]:
        """Find and return the object layer from the TMX data."""
        for layer in self.tmx_data.layers:
            if isinstance(layer, pytmx.TiledObjectGroup):
                return layer
        return None

    def _load_spawn_areas(self) -> Dict[str, pygame.Rect]:
        """
        Load all spawn areas from the object layer.
        Returns dictionary with {spawn_name: pygame.Rect}
        """
        spawns = {}

        if not self.objectlayer:
            return spawns

        for obj in self.objectlayer:
            if obj.type == "spawn":
                spawns[obj.name] = pygame.Rect(
                    obj.x,
                    obj.y,
                    obj.width,
                    obj.height
                )

        return spawns

    def get_spawn_area(self, name: str) -> Optional[pygame.Rect]:
        """Get a specific spawn area by name"""
        return self.spawn_areas.get(name)

    def get_player_spawn(self) -> Optional[pygame.Rect]:
        """Convenience method to get player spawn"""
        return self.get_spawn_area("player")

    def get_enemy_spawns(self) -> Dict[str, pygame.Rect]:
        """Get all non-player spawn areas"""
        return {
            name: rect
            for name, rect in self.spawn_areas.items()
            if name != "player"
        }


