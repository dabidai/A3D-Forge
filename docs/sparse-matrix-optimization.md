# 稀疏矩阵内存优化

## 问题

3D 生成页面报错：`Unable to allocate 34.0 GiB for an array with shape (190979, 190979) and data type bool`

## 定位

`server/app/services/postprocess/defect_detector.py:58`，非流形边检测：

```python
mesh.edges_sparse.toarray().sum(axis=1)
```

`mesh.edges_sparse` 是 scipy CSR 稀疏矩阵（N×N），表示边的邻接关系。`.toarray()` 将其转为稠密 numpy 数组。

## 根因

稠密矩阵大小 = N² 字节。N = 190979 条边时，360 亿个元素 × 1 byte = **~34GB**，直接 OOM。

但实际上每条边最多相邻 2~3 条边，非零元素约 50 万个。

## 修复

用稀疏矩阵原生运算替代稠密转换：

```python
# 修复前（稠密，34GB）
np.where(mesh.edges_sparse.toarray().sum(axis=1) != 2)[0]

# 修复后（稀疏，~2MB）
edge_degrees = np.array(mesh.edges_sparse.sum(axis=1)).flatten()
np.where(edge_degrees != 2)[0]
```

CSR 格式的 `.sum(axis=1)` 直接在稀疏结构上计算，不需要展开稠密。结果是一个 N 长的向量（~1.5MB），远小于 N×N 稠密矩阵。

## 内存对比

| | 稠密 | 稀疏 |
|--|------|------|
| 矩阵存储 | N² = 34GB | ~50万非零 ≈ 4MB |
| 计算结果 | — | N 长向量 ≈ 1.5MB |
| 总占用 | 34GB | ~5.5MB |
| 缩小倍数 | — | ~6000x |

## 涉及文件

- `server/app/services/postprocess/defect_detector.py:56-66`
