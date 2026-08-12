import random
import time
class Fighter:
    def __init__(self, name, hp, speed, attack_damage,special_ability):
        self.name = name
        self.hp = hp
        self.speed = speed
        self.attack_damage = attack_damage
        self.special_ability = special_ability

    def attack(self, defender):
        variety = random.randint(2,4)
        special_ability = random.randint(1, 3)
        if special_ability == 1:
            if self.special_ability == "Fireball":
                damage = self.attack_damage * 2 + variety
                defender.hp -= damage
                print(f"{self.name} uses {self.special_ability}!")
            else:
                damage = self.attack_damage * 1.5 + variety
                defender.hp -= damage
                print(f"{self.name} uses {self.special_ability}!")
        else:
            damage = self.attack_damage + variety
            defender.hp -= damage
            print(f"{self.name} hits {defender.name} for {damage}")

    def is_alive(self):
        return self.hp > 0

andy = Fighter("Andy", 100, 5, 10, "Fireball")
bob = Fighter("Bob", 80, 8, 15, "Ice Blast")
def main():
    while andy.is_alive() and bob.is_alive():
        if andy.speed >= bob.speed:
          
            andy.attack(bob)
            time.sleep(1)
            if bob.hp < 0:
                bob.hp = 0
            print(f"{bob.name} has {bob.hp} HP left.")
            
            if bob.is_alive():
                bob.attack(andy)
                time.sleep(1)
        else:
            
            bob.attack(andy)
            time.sleep(1)
            if andy.hp < 0:
                andy.hp = 0
            print(f"{andy.name} has {andy.hp} HP left.")
            if andy.is_alive():
                andy.attack(bob)

    if andy.is_alive():
        print(f"{andy.name} wins!")
    else:
        print(f"{bob.name} wins!")

main()