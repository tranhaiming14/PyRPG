from __future__ import annotations

from typing import TYPE_CHECKING
import render_functions
from message_log import MessageLog
import exceptions
import lzma
import pickle

from tcod.context import Context
from tcod.console import Console
from tcod.map import compute_fov

if TYPE_CHECKING:
    from entity import Actor
    from game_map import GameMap, GameWorld


class Engine:
    game_map: GameMap
    game_world: GameWorld

    def __init__(self, player: Actor):
        self.player = player
        self.message_log = MessageLog()
        self.mouse_location = (0, 0)
        self.lightning_effect = None # For lightning effect rendering
        self.fireball_effect = None  # For fireball effect rendering
    def handle_enemy_turns(self) -> None:
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass  # Ignore impossible action exceptions from AI.
    

    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        self.game_map.visible[:] = compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=4,
        )
        # If a tile is "visible" it should be added to "explored".
        self.game_map.explored |= self.game_map.visible

    def render(self, console: Console) -> None:
        self.game_map.render(console)
        self.message_log.render(console=console, x=21, y=45, width=40, height=5)        
        render_functions.render_bar(
            console=console,
            current_value=self.player.fighter.hp,
            maximum_value=self.player.fighter.max_hp,
            total_width=20,
        )
        render_functions.render_dungeon_level(
            console=console,
            dungeon_level=self.game_world.current_floor,
            location=(0, 47),
        )

        render_functions.render_names_at_mouse_location(
            console=console, x=21, y=44, engine=self
        )

        console.print(
            x=1,
            y=48,
            string=f"Defense: {self.player.fighter.defense}",
        )    
        console.print(
            x=1,
            y=49,
            string=f"Attack: {self.player.fighter.power}",
        )

        if self.lightning_effect:
            render_functions.draw_lightning(
                console,
                self.lightning_effect["start"],
                self.lightning_effect["end"],
                self.lightning_effect["color"],
            )
            self.lightning_effect["frames"] -= 1
            if self.lightning_effect["frames"] <= 0:
                self.lightning_effect = None
        if self.fireball_effect:
            for x, y in self.fireball_effect["tiles"]:
                console.bg[x, y] = self.fireball_effect["color"]
            self.fireball_effect["frames"] -= 1
            if self.fireball_effect["frames"] <= 0:
                self.fireball_effect = None


    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)

