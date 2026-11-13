"""Optional PySpark version of the gold build, for volumes beyond a single machine (ADR-0017).

Not imported by Django and not part of the runtime dependencies (it needs Java and pyspark):

    pip install pyspark==4.0.1
    spark-submit scripts/spark_gold_job.py data/lake

It reads the same silver Parquet files and writes the same star schema as ``pipeline.build``.
"""

import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F  # noqa: N812


def main(base: str) -> None:
    spark = SparkSession.builder.appName("byte-gold").getOrCreate()
    sales = spark.read.parquet(f"{base}/silver/sales_lines.parquet")
    products = spark.read.parquet(f"{base}/silver/products.parquet")
    stores = spark.read.parquet(f"{base}/silver/stores.parquet")
    dim_product = products.drop("price").withColumn("product_key", F.monotonically_increasing_id())
    dim_store = stores.withColumn("store_key", F.monotonically_increasing_id())
    fact = (
        sales.join(dim_product.select("sku", "product_key"), "sku")
        .join(dim_store.select("store_code", "store_key"), "store_code")
        .withColumn("date_key", F.date_format("order_date", "yyyyMMdd").cast("int"))
        .withColumn("revenue", F.col("quantity") * F.col("unit_price"))
        .withColumn("vat", F.round(F.col("revenue") - F.col("revenue") / 1.19, 2))
        .select(
            "date_key",
            "product_key",
            "store_key",
            "channel",
            "customer_key",
            "order_id",
            "quantity",
            "revenue",
            "vat",
            "source",
        )
    )
    dim_product.write.mode("overwrite").parquet(f"{base}/gold_spark/dim_product.parquet")
    dim_store.write.mode("overwrite").parquet(f"{base}/gold_spark/dim_store.parquet")
    fact.write.mode("overwrite").partitionBy("channel").parquet(
        f"{base}/gold_spark/fact_sales.parquet"
    )
    spark.stop()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/lake")
