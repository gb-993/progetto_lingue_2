import pandas as pd
from skbio import DistanceMatrix
from skbio.stats.distance import mantel
import plotly.express as px
import matplotlib.pyplot as plt
from itertools import combinations
import os
import glob
import sys


if len(sys.argv) != 2:
    raise ValueError("Usage: python mantel.py <matrix_folder>")

folder = sys.argv[1]

matrix_files = sorted(glob.glob(os.path.join(folder, "*.tsv")) + 
                      glob.glob(os.path.join(folder, "*.txt")))

if len(matrix_files) < 2:
    raise ValueError("La cartella deve contenere almeno due matrici di distanza.")

results = []

for f1, f2 in combinations(matrix_files, 2):

    dm1 = pd.read_csv(f1, sep="\t", index_col=0)
    dm2 = pd.read_csv(f2, sep="\t", index_col=0)

    x = DistanceMatrix(dm1.values, ids=dm1.index.tolist())
    y = DistanceMatrix(dm2.values, ids=dm2.index.tolist())

    label1 = os.path.splitext(os.path.basename(f1))[0]
    label2 = os.path.splitext(os.path.basename(f2))[0]

    pairs = list(combinations(range(len(dm1)), 2))
    vals1 = [dm1.iat[i, j] for i, j in pairs]
    vals2 = [dm2.iat[i, j] for i, j in pairs]

    # default parameters: mantel(x, y, method='pearson', permutations=999, alternative='two-sided', strict=True, lookup=None, seed=None)
    for method in ["pearson", "spearman", "kendalltau"]:
        corr_coeff, p_value, n = mantel(x, y, method=method, seed=42)

        results.append({
            "matrix1": label1,
            "matrix2": label2,
            "method": method,
            "correlation": corr_coeff,
            "p_value": p_value,
        })

    output_file = f"{label1}-{label2}_mantel_scatterplot.png"

    plt.figure(figsize=(12, 8))
    plt.scatter(vals1, vals2, s=10, alpha=0.75)
    plt.grid(True, linestyle='--', linewidth=0.5, alpha=0.75)
    plt.xlabel(label1)
    plt.ylabel(label2)
    # plt.title("Mantel test")

    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()

    df_plot = pd.DataFrame({
        'x': vals1,
        'y': vals2,
        'pair': [f"{dm1.index[i]} - {dm1.index[j]}" for i, j in pairs]
    })

    fig = px.scatter(df_plot, x='x', y='y', hover_data=['pair'],
                     labels={'x': label1, 'y': label2},
                     )
    fig.update_traces(marker=dict(size=10, opacity=0.75))
    fig.write_html(f"{label1}-{label2}_mantel_scatterplot_interactive.html")


results_df = pd.DataFrame(results)

long_format = "mantel_results.csv"
results_df.to_csv(long_format, index=False)