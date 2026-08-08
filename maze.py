import random

while True:
    request = input("Enter the width x height like (5x5): ")
    first, second = request.split("x")
    width = int(first)
    height = int(second)
    if width >= 3 and height >= 3:
        break
    print("Width and height must both be at least 4, try again.")

print(width, height)
row = []
for i in range(width):
    current_row = []
    for j in range(height):
        if (i == 0 or i == width - 1) or (j == 0 or j == height - 1):
            current_row.append("W")
        else:
            current_row.append(".")
    row.append(current_row)

while True:
    exit_i = random.randint(1, width - 2)
    exit_j = random.randint(1, height - 2)
    if row[exit_i][exit_j] == ".":
        break
row[exit_i][exit_j] = "E"

while True:
    player_i = random.randint(1, width - 2)
    player_j = random.randint(1, height - 2)
    if row[player_i][player_j] == "E":
        continue
    else:
        break
row[player_i][player_j] = "P"

for i in range(width):
    for j in range(height):
        print(row[i][j], end="")
    print()


while True:
    move = input("Move (w=up, s=down, a=left, d=right, q=quit): ")
    move = move.strip().lower()

    new_i = player_i
    new_j = player_j

    if move == "w":
        new_i = player_i - 1
    elif move == "s":
        new_i = player_i + 1
    elif move == "a":
        new_j = player_j - 1
    elif move == "d":
        new_j = player_j + 1
    elif move == "q":
        print("Thanks for playing!")
        break
    else:
        print("Type w, a, s, d to move, or q to quit.")
        continue

    if row[new_i][new_j] == "W":
        print("That's a wall, you can't go there.")
        continue

    if row[new_i][new_j] == "E":
        print("You found the exit! You win!")
        break

    row[player_i][player_j] = "."
    row[new_i][new_j] = "P"
    player_i = new_i
    player_j = new_j

    for i in range(width):
        for j in range(height):
            print(row[i][j], end="")
        print()