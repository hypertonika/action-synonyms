def parse_text_file(file_path):
    word_dict = {}
    with open(file_path, "r", encoding="utf-8") as file:
        
        i = 0
        for line in file:
            
            try:
                i += 1
                print(i)
                # Разделяем английскую часть и остальную строку
                eng_syns, ru_kz = line.split(")", 1)
                eng, syns = eng_syns.split("(", 1)
                
                # Разделяем русскую и казахскую части с учётом дефисов
                ru, kz = ru_kz[2:].split(" - ", 1)
                
                # Форматируем данные
                eng = eng.strip()
                syns = syns.strip().split(", ")  # Список синонимов
                ru = ru.strip()
                kz = kz.strip()

                # Добавляем в словарь
                word_dict[eng] = [syns, ru, kz]
                
            except IndexError:
                print(f"Skipping malformed line: {line}")
    return word_dict


# File path to the input text file
file_path = "./data/data19.txt"

# Generate the dictionary
dictionary = parse_text_file(file_path)

# Display the dictionary

if __name__ == "__main__":
    for key, value in dictionary.items():
        print(f"{key}: {value}")