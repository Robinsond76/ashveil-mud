# Phase 5: Inventory & Weight Overhaul
**Status: NOT STARTED**
**Depends on: Phase 2 (stamina affected by carry weight), Phase 4 (food stacking)**

## Overview
Replace the flat per-character inventory with a party-wide system backed by backpacks and a cart. The player sees one unified inventory view. Weight and slot limits are determined by what containers each party member is carrying. Items can also be manually assigned to specific containers.

---

## Core Concepts

### Container Items
| Item | Slots | Weight Capacity | Notes |
|------|-------|-----------------|-------|
| No backpack | 5 slots | 20 units | Every character has basic carry |
| Small Backpack | +8 slots | +30 weight | Equippable in `back` slot |
| Large Backpack | +12 slots | +50 weight | Equippable in `back` slot |
| Traveller's Cart | +40 slots | +200 weight | Party vehicle; left outside caves/buildings automatically |

### Party Inventory Pool
- Total slots = sum of all party member slots (base + backpack bonus)
- Total weight = sum of all party member weight capacities
- Items picked up are placed in a random party member's backpack automatically
- Player sees all items in one flat `INVENTORY` view (sorted by type)

---

## Cart Rules
- Cart is a special item that follows the party in outdoor/overworld rooms
- The cart **cannot enter** buildings (`room_type: indoor`) or underground (`room_type: underground`)
- On entering such a room, a smart alert prints: *"Your cart remains outside at [room name]."*
- On exiting back to outdoor, the cart automatically rejoins
- If the party is ambushed in a room where the cart isn't present, cart items are unavailable
- Cart cannot be stolen (for now)

---

## Weight System

### Current
Weight only affects `effective_speed` via equipped gear.

### New
- Total **carried** weight (inventory + equipped) now contributes to speed penalty
- Formula: `speed = AGI - floor((equipped_weight + carried_weight) / WEIGHT_DIVISOR)`
- Items in the cart do NOT count toward character weight

### Over-Encumbered
If total party carried weight exceeds capacity:
- Cannot pick up new items
- Prompt: *"Your party is over-encumbered. Drop something first."*

---

## Auto-Placement Algorithm
When `PICK UP <item>` is called:
1. Find party members with available slots and weight capacity
2. Randomly assign to one of them
3. If none available, check cart (if present in room)
4. If still no space, refuse pickup with message

---

## Manual Management

### Commands
| Command | Description |
|---------|-------------|
| `INVENTORY` | View all party items (unified, grouped by type) |
| `INVENTORY <member>` | View one character's items only |
| `INV CART` | View cart contents specifically |
| `GIVE <item> TO <member>` | Move an item from auto-assigned holder to another |
| `LOAD CART <item>` | Move item to cart (cart must be in room) |
| `UNLOAD CART <item>` | Move item from cart to party |
| `STASH <item>` | Alias for LOAD CART |

---

## Equipment Slot Addition
Add `back` to `EQUIPMENT_SLOTS` for backpacks.

```python
EQUIPMENT_SLOTS = ("weapon", "offhand", "head", "body", "hands", "feet", "back")
```

---

## New Items to Create

| Item ID | Name | Type | Effect |
|---------|------|------|--------|
| `small_backpack` | Small Backpack | armor (back) | +8 slots, +30 weight cap |
| `large_backpack` | Large Backpack | armor (back) | +12 slots, +50 weight cap |
| `travellers_cart` | Traveller's Cart | misc/vehicle | +40 slots, +200 weight cap, outdoor only |

---

## Data Changes

### Character fields to add
```python
backpack_id: str | None = None   # item_id of equipped backpack
# Slot count and weight cap become computed properties
```

### New computed properties
```python
@property
def carry_slots(self) -> int: ...

@property
def carry_weight_cap(self) -> int: ...
```

### Party-level helpers (in game.py)
```python
def _party_inventory_view(self) -> list[tuple[str, str, str]]: ...  # (holder_name, item_id, item_name)
def _party_total_weight(self) -> int: ...
def _party_total_slots(self) -> int: ...
def _party_has_cart(self) -> bool: ...
def _cart_in_room(self) -> bool: ...
```

---

## Help entries to add
- `HELP INVENTORY`, `HELP BACKPACK`, `HELP CART`, `HELP WEIGHT`, `HELP GIVE`

---

## Notes
- Phase 6 (Horses) introduces a similar auto-detach/reattach mechanic to carts
- The cart and horse systems share a "vehicle presence" abstraction
- INV shows item holder name in parentheses when `INVENTORY` is called with details
