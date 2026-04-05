# Plan: Phase 5 — Inventory & Weight Overhaul

**Spec:** [phase-05-inventory-weight.md](../specs/phase-05-inventory-weight.md)
**Depends on:** Phase 2 (stamina affected by carry weight), Phase 4 (food stacking patterns)
**Status:** NOT STARTED

---

## Overview

Replace the flat per-character inventory with a party-wide pool backed by backpacks and a cart. Add a `back` equipment slot. Carry weight (excluding cart items) feeds into the speed formula. The cart is outdoor-only and auto-detaches on entering indoor/underground rooms.

---

## Phase A — Equipment Slot & Container Items

1. Add `"back"` to `EQUIPMENT_SLOTS` tuple in `server/engine/character.py`
2. Add `carry_slots` computed `@property` to `Character`:
   - Base: 5 slots
   - If backpack equipped in `back` slot: add backpack `slot_bonus` from item data
3. Add `carry_weight_cap` computed `@property` to `Character`:
   - Base: 20 units
   - If backpack equipped: add backpack `weight_bonus` from item data
4. Add container item definitions to item data (use `server/data/items/misc.json` or a separate `containers.json`):

   | ID | Name | Type | slot_bonus | weight_bonus | Notes |
   |----|------|------|------------|--------------|-------|
   | `small_backpack` | Small Backpack | armor (back) | +8 | +30 | |
   | `large_backpack` | Large Backpack | armor (back) | +12 | +50 | |
   | `travellers_cart` | Traveller's Cart | misc/vehicle | +40 | +200 | outdoor only |

---

## Phase B — Weight Formula Update

5. In `character.py` `effective_speed` calculation: add `_carried_weight` (sum of all inventory item weights, excluding equipped items which are already counted) to the formula:
   ```python
   speed = AGI - floor((equipped_weight + carried_weight) / WEIGHT_DIVISOR)
   ```
6. Items stored in the cart do **not** count toward carried weight — only items in `character.inventory`

---

## Phase C — Cart State in GameSession

7. Add to `GameSession` in `game.py`:
   ```python
   _cart_present: bool = False
   _cart_room_id: str | None = None
   _cart_inventory: list[str] = []
   ```
8. `_party_has_cart() -> bool`: checks if any party member has `travellers_cart` in inventory or equipped
9. In `_do_move()`, after resolving destination room:
   - If destination `room_type` is `indoor` or `underground` and cart present:
     - Set `_cart_present = False`, `_cart_room_id = current_room_id`
     - Print: `"Your cart remains outside at [current room name]."`
   - If destination `room_type` is `outdoor` and `_cart_room_id` is set:
     - Set `_cart_present = True`, `_cart_room_id = None`
     - Print: `"Your cart catches up with the party."`

---

## Phase D — Auto-Placement Algorithm

10. Implement `_auto_assign_item(item_id: str) -> bool` in `game.py`:
    1. Find party members (including player) with available slots (`len(inventory) < carry_slots`) and weight capacity
    2. If multiple candidates: pick randomly
    3. If no party member can hold it: check `_cart_present` — assign to `_cart_inventory` if cart is in room
    4. If still no space: print `"Your party is over-encumbered. Drop something first."` and return `False`
    5. Return `True` on success
11. Replace direct `inventory.append()` call in `_do_take()` with `_auto_assign_item()`

---

## Phase E — Party Inventory View

12. Implement `_party_inventory_view() -> list[tuple[str, str, str]]` in `game.py`:
    - Returns `(holder_name, item_id, item_name)` for all party member inventories
    - Sorted by item type (weapons → armor → consumables → misc)
13. Update `INVENTORY` handler (bare `INV`): use `_party_inventory_view()`, display unified list with holder name in brackets
14. `INVENTORY <member>`: filter to that member's items only
15. `INV CART`: display `_cart_inventory` contents

---

## Phase F — Manual Management Commands

16. `GIVE <item> TO <member>`:
    - Find item in any party member's inventory
    - Validate target member has available slots and weight capacity
    - Transfer item
17. `LOAD CART <item>` / `STASH <item>`:
    - Cart must be present in current room (`_cart_present == True`)
    - Move item from party inventory to `_cart_inventory`
    - Print confirmation
18. `UNLOAD CART <item>`:
    - Cart must be present
    - Move item from `_cart_inventory` to party via `_auto_assign_item()`

---

## Phase G — Over-Encumbered Guard

19. In `_auto_assign_item()`: if all party slots full and no cart → refuse with message and `return False`
20. In `_do_move()`: moving is still allowed while over-encumbered (weight slows speed via formula, does not block)

---

## Relevant Files

| File | Changes |
|------|---------|
| `server/engine/character.py` | `back` slot, `carry_slots` property, `carry_weight_cap` property, speed formula update |
| `server/engine/game.py` | Cart state fields, `_auto_assign_item()`, `_party_inventory_view()`, `INVENTORY` update, new commands |
| `server/data/items/misc.json` | Backpack + cart item definitions (or new `containers.json`) |

---

## Verification Checklist

- [ ] Equip `large_backpack`: `carry_slots` increases by 12, `carry_weight_cap` increases by 50
- [ ] `INV` shows unified party list with holder names
- [ ] `INVENTORY Gareth` shows only Gareth's items
- [ ] Pick up item when all party slots full → over-encumbered message, item not picked up
- [ ] Pick up item when party full but cart present in room → item goes to cart
- [ ] Enter building with cart → *"Your cart remains outside"* message
- [ ] Exit building → *"Your cart catches up"* message; cart items accessible via `INV CART`
- [ ] `GIVE sword TO Gareth` → sword transfers if Gareth has space
- [ ] `LOAD CART waterskin` → waterskin moves to cart; no longer in party carried weight
- [ ] Carry heavy load → `effective_speed` decreases (reflected in combat action_interval)
