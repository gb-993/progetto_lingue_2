from collections import defaultdict
from pathlib import Path


"""
distance.py

This script computes pairwise distance matrices. It supports two distance metrics:
- Hamming distance: counts both '+' and '-' as possible identity symbols.
- Jaccard distance: counts identities only on a chosen symbol (either '+' or '-').
"""


def hamming(P1, P2):
    id = 0.0
    dif = 0.0
    for i in range(len(P1)):
        # an identity on '+' or on '-' is counted as an identity
        if P1[i] == P2[i] == "+" or P1[i] == P2[i] == "-":
            id += 1
        # differences are counted on the characters that exhibit a '+'/'-' contrast. Other symbols are ignored
        elif (P1[i] == "+" and P2[i] == "-") or (P1[i] == "-" and P2[i] == "+"):
            dif += 1
    dist = dif / (dif + id)
    return dist


def jaccard(P1, P2, identity):
    id = 0.0
    dif = 0.0
    for i in range(len(P1)):
        # an identity ONLY on the chosen symbol is counted as an identity
        if P1[i] == P2[i] == identity:
            id += 1
        # differences are counted on the characters that exhibit a '+'/'-' contrast. Other symbols are ignored
        elif (P1[i] == "+" and P2[i] == "-") or (P1[i] == "-" and P2[i] == "+"):
            dif += 1
    dist = dif / (dif + id)
    return dist


def distance_matrix(dist_func, data, languages, output_path, identity=None):
    dist = defaultdict(dict)
    for lang1 in data:
        for lang2 in data:
            if identity is None:
                dist[lang1[0]][lang2[0]] = round(dist_func(lang1, lang2), 3)
            else:
                dist[lang1[0]][lang2[0]] = round(dist_func(lang1, lang2, identity), 3)

    with open(output_path, "w") as output:
        output.write("Language" + "\t" + "\t".join(languages) + "\n")
        for lang in languages:
            output.write(lang + "\t" + "\t".join([str(dist[lang][lang2]) for lang2 in languages]) + "\n")


def main():

    while True:
        table_a = input("Enter the path to Table_A: ").strip()
        file_path = Path(table_a)
        if not file_path.is_file():
            print("File not found, please enter a valid path.")
        elif file_path.suffix.lower() != ".txt":
            print("The file must have a .txt extension.")
        else:
            break

    with open(table_a, "r") as f:
        lines = f.readlines()

    languages = [line.split()[0] for line in lines]
    original = [line.split() for line in lines]

    zero_to_minus = []
    for line in lines:
        parts = line.strip().split()
        new_parts = [parts[0]]
        for char in parts[1:]:
            if char == '0':
                new_parts.append('-')
            else:
                new_parts.append(char)
        zero_to_minus.append(new_parts)


    # Create output directory if it doesn't exist -> anche in RAM
    output_dir = Path("distances")
    output_dir.mkdir(exist_ok=True)

    distance_matrix(hamming, original, languages, output_dir / "hamming.txt")
    distance_matrix(jaccard, original, languages, output_dir / "jaccard[+].txt", identity="+")


    print(f"Six distance matrices generated successfully.")


if __name__ == "__main__":
    main()