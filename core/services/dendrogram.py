import os
import pandas as pd
import numpy as np
import sys
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform


def load_distance_matrix(filepath):
    df = pd.read_csv(filepath, sep="\t", index_col=0)
    language_labels = df.index.tolist()
    if not np.allclose(df.values, df.values.T):
        raise ValueError("The distance matrix is not symmetric.")
    condensed_matrix = squareform(df.values)
    return condensed_matrix, language_labels

def hc_from_distances(condensed_matrix):
    method = "average"
    linkage_matrix = linkage(condensed_matrix, method=method)
    return linkage_matrix

def hc_dendrogram(linkage_matrix, language_labels, filename=None, title="Dendrogram"):

    plt.figure(figsize=(12, 8))

    dendrogram(
        linkage_matrix,
        labels=language_labels,
        orientation='top',
        distance_sort='descending',  # ascending / None
        show_leaf_counts=True,
        color_threshold=0,
        above_threshold_color='black'
    )
    
    plt.title(title)
    plt.xlabel("Languages")
    plt.ylabel("Distance")
    plt.tight_layout()

    if filename:
        plt.savefig(filename, dpi=300, bbox_inches="tight")
    # plt.show()


def save_clustering_results(linkage_matrix, labels, script_dir, distance_name):
    output_filename = os.path.join(script_dir, f"dendrogram_{distance_name}_average.png")
    hc_dendrogram(
        linkage_matrix,
        labels,
        filename=output_filename,
        title=f"Dendrogram, {distance_name}, average"
    )


def main():

    if len(sys.argv) < 2:
        print("Usage: python dendrogram.py <distance_matrix_folder>")
        sys.exit(1)

    distance_matrix = sys.argv[1]

    script_dir = os.path.dirname(os.path.abspath(__file__))

    files = [f for f in os.listdir(distance_matrix) if f.startswith('hamming') or f.startswith('jaccard')]

    for file in files:
        filepath = os.path.join(distance_matrix, file)
        distance_name = os.path.splitext(file)[0]
        condensed_matrix, labels = load_distance_matrix(filepath)

        linkage_matrix = hc_from_distances(condensed_matrix)

        save_clustering_results(linkage_matrix, labels, script_dir, distance_name)

if __name__ == "__main__":
    main()
