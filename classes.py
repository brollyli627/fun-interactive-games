import random
import time

# Every attack is a special attack now; each entry is name -> damage multiplier.
SPECIAL_ABILITIES = {
    "Fireball": 2.0,
    "Ice Blast": 1.5,
    "Lightning Bolt": 1.75,
}

# A single fighter in the PvP battle: holds its own stats and knows how to attack.
class Fighter:
    def __init__(self, name, hp, speed, attack_damage):
        self.name = name
        self.hp = hp
        self.speed = speed              # higher speed acts first each round
        self.attack_damage = attack_damage

    def attack(self, defender, ability):
        variety = random.randint(2, 4)  # small random bonus added to every hit
        multiplier = SPECIAL_ABILITIES[ability]
        damage = round(self.attack_damage * multiplier + variety)
        defender.hp -= damage
        print(f"{self.name} uses {ability} on {defender.name} for {damage}!")

    def is_alive(self):
        return self.hp > 0

# The two combatants for this match.
andy = Fighter("Andy", 100, 5, 10)
bob = Fighter("Bob", 80, 8, 15)

def choose_fighter():
    print(f"Choose your fighter: [1] {andy.name}  [2] {bob.name}")
    choice = input("> ").strip()
    if choice == "1":
        return andy, bob   # (player, cpu)
    else:
        return bob, andy

def choose_ability():
    ability_names = list(SPECIAL_ABILITIES)
    print("Choose your special ability:")
    for i, name in enumerate(ability_names, start=1):
        print(f"[{i}] {name}")
    choice = input("> ").strip()
    if choice in ("1", "2", "3"):
        return ability_names[int(choice) - 1]
    return ability_names[0]  # default if input wasn't 1-3

def perform_attack(attacker, defender, is_player):
    ability = choose_ability() if is_player else random.choice(list(SPECIAL_ABILITIES))
    attacker.attack(defender, ability)
    time.sleep(1)
    if defender.hp < 0:
        defender.hp = 0             # clamp HP so it never prints as negative
    print(f"{defender.name} has {defender.hp} HP left.")


def main():
    for i in range(3):
        print("LOADING")
        time.sleep(0.1)
    player_fighter, cpu_fighter = choose_fighter()
    # Whoever is faster attacks first each round; that's decided once per
    # exchange below by comparing speed, not re-rolled mid-fight.
    while player_fighter.is_alive() and cpu_fighter.is_alive():
        if player_fighter.speed >= cpu_fighter.speed:
            perform_attack(player_fighter, cpu_fighter, True)
            if cpu_fighter.is_alive():                 # only counter-attack if player's hit didn't finish cpu_fighter off
                perform_attack(cpu_fighter, player_fighter, False)
        else:
            perform_attack(cpu_fighter, player_fighter, False)
            if player_fighter.is_alive():               # only counter-attack if cpu_fighter's hit didn't finish player_fighter off
                perform_attack(player_fighter, cpu_fighter, True)

    # Whoever is still standing when the loop exits wins.
    if player_fighter.is_alive():
        print(f"{player_fighter.name} wins!")
    else:
        print(f"{cpu_fighter.name} wins!")

main()
