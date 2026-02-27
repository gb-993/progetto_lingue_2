from collections import defaultdict
import sys


def hamming(P1, P2, include_zero=False):
    id = 0.0
    dif = 0.0
    for i in range(len(P1)):
        if include_zero:
            # identities are counted on '+', '-', and '0'
            if P1[i] == P2[i] and P1[i] in {"+", "-", "0"}:
                id += 1
            # differences include all mismatches among '+', '-', and '0'
            elif P1[i] in {"+", "-", "0"} and P2[i] in {"+", "-", "0"}:
                dif += 1
        else:
            # identities are counted on '+', and '-'
            if P1[i] == P2[i] == "+" or P1[i] == P2[i] == "-":
                id += 1
            # differences include all mismatches among '+' and '-', other symbols are ignored
            elif (P1[i] == "+" and P2[i] == "-") or (P1[i] == "-" and P2[i] == "+"):
                dif += 1
    return dif / (dif + id)


def jaccard(P1, P2, identity, include_zero=False):
    id = 0.0
    dif = 0.0
    for i in range(len(P1)):
        # identities are counted ONLY on the chosen symbol
        if P1[i] == P2[i] == identity:
            id += 1
        elif include_zero:
            # differences include all mismatches among '+', '-', '0'
            if P1[i] in {"+", "-", "0"} and P2[i] in {"+", "-", "0"} and P1[i] != P2[i]:
                dif += 1
        else:
            # differences include all mismatches among '+' and '-', other symbols are ignored
            if (P1[i] == "+" and P2[i] == "-") or (P1[i] == "-" and P2[i] == "+"):
                dif += 1
    return dif / (dif + id)


def distance_matrix(dist_func, data, languages, output_path, identity=None):
    dist = defaultdict(dict)
    for lang1 in data:
        for lang2 in data:
            if identity is None:
                # dist[lang1[0]][lang2[0]] = round(dist_func(lang1, lang2), 3)
                dist[lang1[0]][lang2[0]] = dist_func(lang1, lang2)
            else:
                # dist[lang1[0]][lang2[0]] = round(dist_func(lang1, lang2, identity), 3)
                dist[lang1[0]][lang2[0]] = dist_func(lang1, lang2, identity)

    with open(output_path, "w") as output:
        output.write("Language" + "\t" + "\t".join(languages) + "\n")
        for lang in languages:
            output.write(lang + "\t" + "\t".join([str(dist[lang][lang2]) for lang2 in languages]) + "\n")


def main():

    if len(sys.argv) != 2:
        print("Usage: python distance.py <Table_A.txt>")
        sys.exit(1)

    table_a = sys.argv[1]

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


    # solo queste due
    distance_matrix(hamming, original, languages, "hamming.txt")
    distance_matrix(jaccard, original, languages, "jaccard[+].txt", identity="+")


    # non servono
    distance_matrix(jaccard, original, languages, "jaccard[-].txt", identity="-")
    distance_matrix(hamming, zero_to_minus, languages, "hamming[NO_0].txt")
    distance_matrix(jaccard, zero_to_minus, languages, "jaccard[+_NO_0].txt", identity="+")
    distance_matrix(jaccard, zero_to_minus, languages, "jaccard[-_NO_0].txt", identity="-")
    distance_matrix(lambda x, y: hamming(x, y, include_zero=True), original, languages, "hamming[0].txt")
    distance_matrix(lambda x, y: jaccard(x, y, identity="+", include_zero=True), original, languages, "jaccard[+_0].txt")
    distance_matrix(lambda x, y: jaccard(x, y, identity="-", include_zero=True), original, languages, "jaccard[-_0].txt")

    print(f"Nine distance matrices generated successfully.")


if __name__ == "__main__":
    main()