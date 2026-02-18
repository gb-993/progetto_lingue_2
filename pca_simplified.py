import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
from adjustText import adjust_text
import sys


def prepare_data(filepath, target_col="Language"):
    df = pd.read_csv(filepath, sep=",")      
    convert = df.columns.difference(['Language'])
    df[convert] = (df[convert].replace({'+': 1, '-': 0, '0': 0}).astype(float))

    cols_to_check = df.columns.difference([target_col])
    nunique = df[cols_to_check].nunique()
    dropped_cols = nunique[nunique <= 1].index.tolist()

    if dropped_cols:
        remaining_vars = [col for col in cols_to_check if col not in dropped_cols]
        print(f"Dropped variables ({len(dropped_cols)}/{len(cols_to_check)}):\n"f"{dropped_cols}\n"
              f"Remaining variables ({len(remaining_vars)}/{len(cols_to_check)}):\n"f"{remaining_vars}")

    df = df.drop(columns=dropped_cols)

    X = df.drop(columns=[target_col])
    y = df[target_col]
    return X, y, df


def run_pca(X, n_components=None):
    scaler = StandardScaler()            
    X_std = scaler.fit_transform(X)    
    pca = PCA(n_components=n_components)
    vecs = pca.fit_transform(X_std)   
    n_components_actual = pca.n_components_
    reduced_df = pd.DataFrame(data=vecs, columns=[f'F{i+1}' for i in range(n_components_actual)]) 
    return reduced_df, pca


def pca_scatterplot(reduced_df, language_labels, pca, filename=None):

    plt.figure(figsize=(12, 8))

    plt.scatter(reduced_df['F1'], reduced_df['F2'], c='black', s=10, alpha=0.75)

    texts = [plt.text(x, y, label, fontsize=9) for x, y, label in zip(reduced_df['F1'], reduced_df['F2'], language_labels)] 
    adjust_text(texts, arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))     

    plt.grid(True, linestyle='--', linewidth=0.5, alpha=0.75)
    plt.xlabel(f'F1 ({pca.explained_variance_ratio_[0]*100:.2f}%)')
    plt.ylabel(f'F2 ({pca.explained_variance_ratio_[1]*100:.2f}%)')
    # plt.title('PCA Scatterplot')
    plt.axhline(0, color='gray', lw=0.5)
    plt.axvline(0, color='gray', lw=0.5)
    plt.tight_layout()

    if filename:
        plt.savefig(filename, dpi=300, bbox_inches='tight')
    # plt.show()


def main():
    if len(sys.argv) != 2:
        print("Usage: python pca.py <path_to_csv>")
        sys.exit(1)

    data_path = sys.argv[1]

    X, y, _ = prepare_data(data_path)

    reduced_df, pca = run_pca(X)

    var1 = pca.explained_variance_ratio_[0]
    var2 = pca.explained_variance_ratio_[1]
    total_var = var1 + var2

    print(f"Explained variance (F1): {var1}\n"
          f"Explained variance (F2): {var2}\n"
          f"Total explained variance (F1 + F2): {total_var}")

    pca_scatterplot(reduced_df, y, pca, filename="pca_scatterplot.png")
    
if __name__ == "__main__":
    main()