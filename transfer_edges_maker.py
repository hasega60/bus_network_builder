import geopandas as gpd
import pandas as pd
import h3
from tqdm import tqdm
import shapely.wkt
from shapely.geometry import LineString, Point, MultiPoint
from fiona.crs import from_epsg
import pyproj
import numpy as np
from shapely.ops import split, snap, linemerge

gcs_jgd = 4612  # jgd2000 latlon
pcs_jgd = 2451  # jgd2000　japanzone9
rounding=1 #xyの丸め桁数

distance_transfer = 50 #乗換可能距離（meters)

def nearest_neighbor_within(others, point, max_distance):
    search_region = point.buffer(max_distance)
    interesting_points = search_region.intersection(MultiPoint(others))

    if not interesting_points:
        closest_point = None
    elif isinstance(interesting_points, Point):
        closest_point = interesting_points
    else:
        distances = [point.distance(ip) for ip in interesting_points
                     if point.distance(ip) > 0]
        closest_point = interesting_points[distances.index(min(distances))]

    return closest_point

def add_h3_index(gdf):
    coords = gdf[["lat", "lng"]].values
    index_7, index_8, index_9 = [], [], []
    for coord in tqdm(coords):
        index_7.append(h3.geo_to_h3(coord[0], coord[1], 7))
        index_8.append(h3.geo_to_h3(coord[0], coord[1], 8))
        index_9.append(h3.geo_to_h3(coord[0], coord[1], 9))

    gdf["h3_7"] = index_7
    gdf["h3_8"] = index_8
    gdf["h3_9"] = index_9

    return gdf

if __name__ == '__main__':
    #qgisでポイントのbuffer→intersectを実施後に出力したcsvファイル
    #重複リンクの削除
    df_stops_transfer = pd.read_csv("all/stops_transfer_50m.csv")
    df_stops_transfer = df_stops_transfer[df_stops_transfer["node_id"] != df_stops_transfer["node_id_2"]]
    od, out = [], []
    for r in tqdm(df_stops_transfer[["node_id", "node_id_2"]].values):
        i = r[0]
        j = r[1]
        if (i, j) not in od or (j, i) not in od:
            od.append((i, j))
            out.append(r)

    df_out = pd.DataFrame(r, columns=df_stops_transfer.columns)
    df_out["transfer"] = 1
    df_out.to_csv("stops_transfer_50m_2.csv", index=False)






    exit()
    # add h3 index
    print("----------add h3 index----------")
