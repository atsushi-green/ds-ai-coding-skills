# notebooks/

このディレクトリには分析用のJupyter Notebookを配置します。

## ルール

- Notebookは探索とコミュニケーションのために使います。
- 再利用可能なロジックは `src/analysis_project/` に移動してください。
- クリーンなカーネルから再実行可能な状態を保ってください。
- 秘密情報や顧客レベルのレコードを含めないでください。
- 最終的な図表は `outputs/` に保存してください。

## 命名規則

```
NNN_短い説明.ipynb
```

例: `001_data_exploration.ipynb`, `002_feature_analysis.ipynb`
