def count_char_frequency(text):
    char_counts = {}
    
    for char in text:
        if char == ' ':
            continue
        char_counts[char] = char_counts.get(char, 0) + 1
        
    return char_counts


sample_text = input("Please type word ").lower()
result = count_char_frequency(sample_text)
print(result)
