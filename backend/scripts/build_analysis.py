"""离线预计算脚本：人口格网、区县人口、设施最近距离、2SFCA 可达性。

为什么要预计算：
    - 2SFCA 需要遍历「设施 × 人口格网」共百万级配对，单次 10–60 秒，不能放在接口里实时算；
    - 区县人口、设施最近距离也是稳定的中间结果，提前物化后接口只做单表查询。

运行方式：
    python backend/scripts/build_analysis.py

脚本可重复执行（先 DROP 再 CREATE），不会改动原始数据表。
"""

import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text

# 允许以 `python backend/scripts/build_analysis.py` 方式运行时导入 app 包
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Config  # noqa: E402

# 2SFCA 服务半径（米）
SERVICE_RADIUS = {"小学": 1000, "中学": 1500, "菜市场": 500}
CATEGORIES = list(SERVICE_RADIUS)

engine = create_engine(Config.DATABASE_URL, future=True)


def run(label: str, sql: str, params: dict | None = None, fetch: bool = False):
    t0 = time.time()
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        rows = result.fetchall() if fetch else None
    print(f"[{time.time() - t0:6.1f}s] {label}", flush=True)
    return rows


def main():
    print("=" * 64)
    print("开始构建分析预计算表（可重复执行）")
    print("=" * 64)

    # ------------------------------------------------------------------
    # 1. 人口格网：把 100m 栅格转成点（只保留有人口的格子）
    # ------------------------------------------------------------------
    run("D1 删除旧表", """
        DROP TABLE IF EXISTS accessibility_thresholds, accessibility_district,
                             accessibility_2sfca, accessibility_rj,
                             facility_grid_pairs, facility_nearest,
                             district_pop, pop_grid_district, pop_grid_100m CASCADE
    """)

    run("D2 构建人口格网 pop_grid_100m", """
        CREATE TABLE pop_grid_100m AS
        SELECT row_number() OVER () AS cell_id,
               val::double precision AS pop,
               geom
        FROM (
            SELECT (ST_PixelAsPoints(rast, 1)).*
            FROM chengdu_pop_100m
        ) t
        WHERE val > 0
    """)

    run("D3 增加 geography 列（米制距离）", """
        ALTER TABLE pop_grid_100m ADD COLUMN geog geography(Point, 4326);
        UPDATE pop_grid_100m SET geog = geom::geography;
    """)

    run("D4 建索引与主键", """
        ALTER TABLE pop_grid_100m ADD PRIMARY KEY (cell_id);
        CREATE INDEX pop_grid_100m_geom_gix ON pop_grid_100m USING GIST (geom);
        CREATE INDEX pop_grid_100m_geog_gix ON pop_grid_100m USING GIST (geog);
        ANALYZE pop_grid_100m;
    """)

    rows = run(
        "D5 校验格网总量",
        "SELECT COUNT(*) AS cells, ROUND(SUM(pop)) AS pop FROM pop_grid_100m",
        fetch=True,
    )
    print("      格网数=%s 人口合计=%s" % (rows[0][0], rows[0][1]), flush=True)

    # ------------------------------------------------------------------
    # 2. 格网 → 区县映射，以及区县人口
    # ------------------------------------------------------------------
    run("D6 格网归属区县 pop_grid_district", """
        CREATE TABLE pop_grid_district AS
        SELECT g.cell_id, d.adcode, g.pop
        FROM pop_grid_100m g
        JOIN chengdu_districts d ON ST_Intersects(d.geom, g.geom)
    """)
    run("D7 建索引", """
        ALTER TABLE pop_grid_district ADD PRIMARY KEY (cell_id);
        CREATE INDEX pop_grid_district_adcode_idx ON pop_grid_district (adcode);
        ANALYZE pop_grid_district;
    """)

    run("D8 区县人口 district_pop", """
        CREATE TABLE district_pop AS
        SELECT adcode, ROUND(SUM(pop))::bigint AS pop2020
        FROM pop_grid_district
        GROUP BY adcode
    """)

    # ------------------------------------------------------------------
    # 3. 每个设施到「同类最近设施」的距离（供区县统计的 avg_nearest_m）
    # ------------------------------------------------------------------
    run("D9 设施最近同类距离 facility_nearest", """
        CREATE TABLE facility_nearest AS
        SELECT p.poi_id,
               p.category,
               p.adcode,
               (
                   SELECT ST_Distance(p.geom::geography, q.geom::geography)
                   FROM chengdu_poi q
                   WHERE q.category = p.category
                     AND q.poi_id <> p.poi_id
                   ORDER BY q.geom <-> p.geom
                   LIMIT 1
               ) AS nearest_m
        FROM chengdu_poi p
    """)
    run("D10 建索引", """
        ALTER TABLE facility_nearest ADD PRIMARY KEY (poi_id);
        CREATE INDEX facility_nearest_cat_adcode_idx ON facility_nearest (category, adcode);
    """)

    # ------------------------------------------------------------------
    # 4. 2SFCA：先建「设施-格网」邻接表（只存 d_ij <= d0 的对）
    # ------------------------------------------------------------------
    run("D11 建邻接表结构", """
        CREATE TABLE facility_grid_pairs (
            category varchar(16) NOT NULL,
            poi_id   varchar(64) NOT NULL,
            cell_id  bigint      NOT NULL,
            dist_m   double precision NOT NULL,
            PRIMARY KEY (category, poi_id, cell_id)
        )
    """)

    for category in CATEGORIES:
        radius = SERVICE_RADIUS[category]
        run(f"D12 邻接对 {category}（d0={radius}m）", """
            INSERT INTO facility_grid_pairs (category, poi_id, cell_id, dist_m)
            SELECT p.category, p.poi_id, g.cell_id,
                   ST_Distance(g.geog, p.geom::geography) AS dist_m
            FROM chengdu_poi p
            JOIN pop_grid_100m g
              ON ST_DWithin(g.geog, p.geom::geography, :radius)
            WHERE p.category = :category
        """, {"radius": radius, "category": category})

    run("D13 邻接表索引", """
        CREATE INDEX facility_grid_pairs_cat_idx ON facility_grid_pairs (category);
        CREATE INDEX facility_grid_pairs_cell_idx ON facility_grid_pairs (category, cell_id);
        ANALYZE facility_grid_pairs;
    """)

    pairs = run(
        "D14 邻接对总数",
        "SELECT COUNT(*) FROM facility_grid_pairs",
        fetch=True,
    )
    print("      邻接对 = %s" % pairs[0][0], flush=True)

    # 第一步：R_j = S_j / Σ P_i（S_j 固定为 1）
    run("D15 计算 R_j", """
        CREATE TABLE accessibility_rj AS
        SELECT f.category,
               f.poi_id,
               1.0 / NULLIF(SUM(g.pop), 0) AS r_j
        FROM facility_grid_pairs f
        JOIN pop_grid_100m g USING (cell_id)
        GROUP BY f.category, f.poi_id
        HAVING SUM(g.pop) > 0
    """)

    # 第二步：A_i = Σ R_j（只存非零值，0 由查询时 COALESCE 得到）
    run("D16 计算 A_i（稀疏存储）", """
        CREATE TABLE accessibility_2sfca AS
        SELECT f.category,
               f.cell_id,
               SUM(r.r_j)::double precision AS a_i
        FROM facility_grid_pairs f
        JOIN accessibility_rj r USING (category, poi_id)
        GROUP BY f.category, f.cell_id
    """)
    run("D17 建索引", """
        ALTER TABLE accessibility_2sfca ADD PRIMARY KEY (category, cell_id);
        ANALYZE accessibility_2sfca;
    """)

    # ------------------------------------------------------------------
    # 5. 区县尺度可达性（人口加权平均），并按分位数分级
    # ------------------------------------------------------------------
    run("D18 区县可达性 accessibility_district", """
        CREATE TABLE accessibility_district AS
        SELECT c.category,
               d.adcode,
               d.name,
               COALESCE(
                   SUM(pgd.pop * COALESCE(s.a_i, 0)) / NULLIF(SUM(pgd.pop), 0),
                   0
               )::double precision AS value,
               SUM(pgd.pop)::bigint AS pop,
               '待定'::text AS level
        FROM chengdu_districts d
        CROSS JOIN (SELECT DISTINCT category FROM accessibility_2sfca) c
        JOIN pop_grid_district pgd ON pgd.adcode = d.adcode
        LEFT JOIN accessibility_2sfca s
               ON s.cell_id = pgd.cell_id AND s.category = c.category
        GROUP BY c.category, d.adcode, d.name
    """)

    run("D19 分位数阈值 accessibility_thresholds", """
        CREATE TABLE accessibility_thresholds AS
        SELECT category,
               percentile_cont(0.25) WITHIN GROUP (ORDER BY value) AS p25,
               percentile_cont(0.50) WITHIN GROUP (ORDER BY value) AS p50,
               percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75
        FROM accessibility_district
        GROUP BY category
    """)

    run("D20 按分位数分级", """
        UPDATE accessibility_district a
        SET level = CASE
            WHEN a.value > t.p75 THEN '优'
            WHEN a.value > t.p50 THEN '良'
            WHEN a.value > t.p25 THEN '一般'
            ELSE '差'
        END
        FROM accessibility_thresholds t
        WHERE t.category = a.category
    """)
    run("D21 建主键", """
        ALTER TABLE accessibility_district ADD PRIMARY KEY (category, adcode);
    """)

    # ------------------------------------------------------------------
    # 6. 结果自检
    # ------------------------------------------------------------------
    print("-" * 64)
    rows = run(
        "S1 各区县可达性（小学）",
        """
        SELECT name, ROUND(value::numeric, 4) AS value, level
        FROM accessibility_district WHERE category = '小学' ORDER BY value DESC
        """,
        fetch=True,
    )
    for r in rows:
        print(f"      {r[0]:<8} {r[1]:>10}  {r[2]}", flush=True)

    rows = run(
        "S2 零值校验（A_i 缺失时应为 0 而非 NULL）",
        """
        SELECT COUNT(*) FILTER (WHERE value IS NULL) AS null_values,
               COUNT(*) FILTER (WHERE value = 0) AS zero_values
        FROM accessibility_district
        """,
        fetch=True,
    )
    print("      NULL=%s  零值=%s" % (rows[0][0], rows[0][1]), flush=True)

    rows = run(
        "S3 区县统计抽查（小学，前 3）",
        """
        SELECT d.name, COUNT(p.poi_id) AS n, ROUND(AVG(fn.nearest_m)::numeric,1) AS avg_m
        FROM chengdu_districts d
        LEFT JOIN chengdu_poi p ON p.adcode = d.adcode AND p.category = '小学'
        LEFT JOIN facility_nearest fn ON fn.poi_id = p.poi_id
        GROUP BY d.name ORDER BY d.name LIMIT 3
        """,
        fetch=True,
    )
    for r in rows:
        print(f"      {r[0]:<8} n={r[1]:<5} avg_nearest={r[2]}", flush=True)

    print("=" * 64)
    print("预计算完成")
    print("=" * 64)


if __name__ == "__main__":
    main()
