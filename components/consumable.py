from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import actions
import color
from components.base_component import BaseComponent
from exceptions import Impossible
import components.inventory
import components.ai
from input_handlers import (
    ActionOrHandler,
    AreaRangedAttackHandler,
    SingleRangedAttackHandler,
)
from render_functions import draw_lightning
if TYPE_CHECKING:
    from entity import Actor, Item


class Consumable(BaseComponent):
    parent: Item

    def get_action(self, consumer: Actor) -> Optional[ActionOrHandler]:
        """Try to return the action for this item."""
        return actions.ItemAction(consumer, self.parent)

    def activate(self, action: actions.ItemAction) -> None:
        """Invoke this items ability.

        `action` is the context for this activation.
        """
        raise NotImplementedError()
    def consume(self) -> None:
        """Remove the consumed item from its containing inventory."""
        entity = self.parent
        inventory = entity.parent
        if isinstance(inventory, components.inventory.Inventory):
            inventory.items.remove(entity)


class HealingConsumable(Consumable):
    def __init__(self, amount: int):
        self.amount = amount

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        amount_recovered = consumer.fighter.heal(self.amount)

        if amount_recovered > 0:
            self.engine.message_log.add_message(
                f"You consume the {self.parent.name}, and recover {amount_recovered} HP!",
                color.health_recovered,
            )
            self.consume()

        else:
            raise Impossible(f"Your health is already full.")
class LightningDamageConsumable(Consumable):
    def __init__(self, damage: int, maximum_range: int):
        self.damage = damage
        self.maximum_range = maximum_range

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        target = None
        closest_distance = self.maximum_range + 1.0

        for actor in self.engine.game_map.actors:
            if actor is not consumer and self.parent.gamemap.visible[actor.x, actor.y]:
                distance = consumer.distance(actor.x, actor.y)

                if distance < closest_distance:
                    target = actor
                    closest_distance = distance

        if target:
            self.engine.message_log.add_message(
                f"A lighting bolt strikes the {target.name} with a loud thunder, for {self.damage} damage!"
            )
            target.fighter.take_damage(self.damage)
            self.engine.lightning_effect = {
                "start": (action.entity.x, action.entity.y),
                "end": (target.x, target.y),
                "color": (255, 255, 0),
                "frames": 10,  # Show for 30 frames (~0.5s at 60fps)
            }

        else:
            raise Impossible("No enemy is close enough to strike.")
class ConfusionConsumable(Consumable):
    def __init__(self, number_of_turns: int):
        self.number_of_turns = number_of_turns

    def get_action(self, consumer: Actor) -> SingleRangedAttackHandler:
        self.engine.message_log.add_message(
            "Select a target location.", color.needs_target
        )
        return SingleRangedAttackHandler(
            self.engine,
            callback=lambda xy: actions.ItemAction(consumer, self.parent, xy),
        )

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        target = action.target_actor
        x, y = action.target_xy  # Ensure target_xy is set
        x = int(x)
        y = int(y)
        if not self.engine.game_map.visible[x, y]:
            print(f"Target XY: {x}, {y}")            
            raise Impossible("You cannot target an area that you cannot see.")
        if target is consumer:
            print(f"Target XY: {x}, {y}")
            raise Impossible("You cannot confuse yourself!")
        if not target:
            print(f"Target XY: {x}, {y}")
            raise Impossible("You must select an enemy to target.")

        self.engine.message_log.add_message(
            f"The eyes of the {target.name} look vacant, as it starts to stumble around!",
            color.status_effect_applied,
        )
        target.ai = components.ai.ConfusedEnemy(
            entity=target, previous_ai=target.ai, turns_remaining=self.number_of_turns,
        )
        self.consume()
class HypnotizingConsumable(ConfusionConsumable):
    def __init__(self, number_of_turns: int):
        super().__init__(number_of_turns)
    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        target = action.target_actor
        x, y = action.target_xy  # Ensure target_xy is set
        x = int(x)
        y = int(y)
        if not self.engine.game_map.visible[x, y]:
            raise Impossible("You cannot target an area that you cannot see.")
        if target is consumer:
            raise Impossible("You cannot hypnotize yourself!")
        if not target:
            raise Impossible("You must select an enemy to target.")

        self.engine.message_log.add_message(
            f"The {target.name} looks entranced, as it starts to follow your commands!",
            color.status_effect_applied,
        )
        target.ai = components.ai.HypnotizedEnemy(
            entity=target, previous_ai=target.ai, turns_remaining=self.number_of_turns,
        )
        self.consume()
class FireballDamageConsumable(Consumable):
    def __init__(self, damage: int, radius: int):
        self.damage = damage
        self.radius = radius

    def get_action(self, consumer: Actor) -> AreaRangedAttackHandler:
        self.engine.message_log.add_message(
            "Select a target location.", color.needs_target
        )
        return AreaRangedAttackHandler(
            self.engine,
            radius=self.radius,
            callback=lambda xy: actions.ItemAction(consumer, self.parent, xy),
        )
        return None

    def activate(self, action: actions.ItemAction) -> None:
        x, y = action.target_xy
        target_xy = (int(x), int(y))
        if not self.engine.game_map.visible[target_xy]:
            raise Impossible("You cannot target an area that you cannot see.")

        affected_tiles = []
        targets_hit = False
        for actor in self.engine.game_map.actors:
            if actor.distance(*target_xy) <= self.radius:
                self.engine.message_log.add_message(
                    f"The {actor.name} is engulfed in a fiery explosion, taking {self.damage} damage!"
                )
                actor.fighter.take_damage(self.damage)
                targets_hit = True
        # Collect all tiles affected by fireball
        for tx in range(target_xy[0] - self.radius, target_xy[0] + self.radius + 1):
            for ty in range(target_xy[1] - self.radius, target_xy[1] + self.radius + 1):
                if (
                    self.engine.game_map.in_bounds(tx, ty)
                    and (abs(tx - target_xy[0]) ** 2 + abs(ty - target_xy[1]) ** 2) <= self.radius ** 2
                ):
                    affected_tiles.append((tx, ty))
        if affected_tiles:
            self.engine.fireball_effect = {
                "tiles": affected_tiles,
                "frames": 10,
                "color": (255, 0, 0),  # Red
            }
        if not targets_hit:
            raise Impossible("There are no targets in the radius.")
        self.consume()
class SpeedScroll(Consumable):
    def __init__(self, number_of_turns: int):
        self.number_of_turns = number_of_turns

    def activate(self, action: actions.ItemAction) -> None:
        consumer = action.entity
        if consumer.is_speeded:
            raise Impossible("You are already under the effect of a speed scroll.")

        self.engine.message_log.add_message(
            f"You feel yourself moving faster for {self.number_of_turns} turns!",
            color.status_effect_applied,
        )
        consumer.is_speeded = True
        consumer.speed_turns_remaining = self.number_of_turns
        self.consume()