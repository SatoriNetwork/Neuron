import pyarrow.parquet as pq
df = pq.read_table(
    r'C://repos//Satori//Node//data//mt8n5T6TF2H2qQLp-6aQQTnoGYs=//aggregate.parquet').to_pandas()
df
