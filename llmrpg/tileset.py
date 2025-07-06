import pygame
from pathlib import Path
from lxml import etree # type: ignore

class Tileset:
    def __init__(self, filpath: str):
        """Load and parse a Tiled tileset XML file"""
        path = Path(filpath)
        self.spritesheet = pygame.image.load(path.with_suffix(".png")).convert_alpha()
        # Parse XML with lxml
        tree = etree.parse(path)
        root = tree.getroot()

        # Extract basic tileset properties
        self.name = root.get("name", "untitled")
        self.tile_width = int(root.get("tilewidth", 16))
        self.tile_height = int(root.get("tileheight", 16))
        self.tile_count = int(root.get("tilecount", 0))
        self.columns = int(root.get("columns", 0))

        # Get the image source path
        image_node = root.find("image")
        if image_node is not None:
            self.image_source = image_node.get("source")
            self.image_width = int(image_node.get("width", 0))
            self.image_height = int(image_node.get("height", 0))
        else:
            self.image_source = None
            self.image_width = 0
            self.image_height = 0

        # Parse individual tile properties and animations
        self._tiles = {}
        for tile_node in root.findall("tile"):
            tile_id = int(tile_node.get("id"))
            tile_type = tile_node.get("type", "")

            # Parse properties
            props = {}
            properties_node = tile_node.find("properties")
            if properties_node is not None:
                for prop_node in properties_node.findall("property"):
                    props[prop_node.get("name")] = prop_node.get("value")

            # Parse animations
            animation = []
            anim_node = tile_node.find("animation")
            if anim_node is not None:
                for frame_node in anim_node.findall("frame"):
                    animation.append({
                        "tileid": int(frame_node.get("tileid")),
                        "duration": int(frame_node.get("duration"))
                    })

            self._tiles[tile_id] = {
                "type": tile_type,
                "properties": props,
                "animation": animation
            }

        # Group animations by imageset and direction
        self.animations = {}
        for tile in self._tiles.values():
            if tile["animation"]:
                imageset = tile["properties"].get("imageset", "unknown")
                direction = tile["properties"].get("direction", "unknown")

                if imageset not in self.animations:
                    self.animations[imageset] = {}
                if direction not in self.animations[imageset]:
                    self.animations[imageset][direction] = {}

                self.animations[imageset][direction].update(**{
                    "frames": tile["animation"],
                    "type": tile["type"],
                    "properties": tile["properties"]
                })

    def frames(self, imageset: str) -> dict[str, list[pygame.Surface]]:
        """
        Return a dict of direction to list of animation frames for the given imageset.
        e.g. { "down": [frame1, frame2, ...], "up": [...], ... }
        """

        frames_dict = {}
        if imageset not in self.animations:
            return frames_dict  # empty dict if imageset unknown

        for direction, anim_data in self.animations[imageset].items():
            frames_list = []
            for frame in anim_data["frames"]:
                tileid = frame["tileid"]
                frames_list.append(self.tile(tileid))
            frames_dict[direction] = frames_list

        return frames_dict

    def tile(self, tileid: int) -> pygame.Surface:
        x = (tileid % self.columns) * self.tile_width
        y = (tileid // self.columns) * self.tile_height
        rect = pygame.Rect(x, y, self.tile_width, self.tile_height)
        return self.spritesheet.subsurface(rect)


    def tiles(self, imageset: str) -> list[pygame.Surface]:
        return [self.tile(tileid) for tileid, tile in self._tiles.items()
            if tile.get("properties", {}).get("imageset") == imageset]

    def __repr__(self):
        """Return a string representation of the tileset"""
        return (
            f"<Tileset {self.name} ({self.tile_width}x{self.tile_height}) "
            f"tiles={self.tile_count} cols={self.columns} "
            f"image='{self.image_source}' "
            f"tiles_with_props={len([t for t in self._tiles.values() if t['properties']])}>"
        )


