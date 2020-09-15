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
pcs_jgd = 3100  # jgd2000　utm54



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

def inverse_lookup(d, x):
    for k, v in d.items():
        if x == v:
            return k

def format_yuragi(gdf:gpd.GeoDataFrame, cols):
    for col in cols:
        gdf[col] = gdf[col].str.replace('　', ' ')
        gdf[col] = gdf[col].str.replace('～', '〜')
    return gdf


def get_route_id(id):
    try:
        category = stop_category_dict[id]
        company_name = stop_company_name_dict[id]
        route_name = stop_route_name_dict[id]
        if stop_category_dict[id] == None:
            #print(f"no_id_in_stops :{id},{stop_name_dict[id]}:{route_name}")
            return None
        route_id = inverse_lookup(route_dict, {'category': int(category), 'company_name': company_name,
                                               'route_name': route_name})
        if route_id is None:
            #print(f"not found route :{id},{stop_name_dict[id]}:{route_name}")
            return None
        else:
            return route_id
    except:
        #print(f"error :{id},{stop_name_dict[id]}:{route_name}")
        return None


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


def get_node_id_from_point(point, node_dict, virtual_node_dict, virtual_id):
    if point in node_dict.keys():
        return node_dict[point], virtual_id
    elif point in virtual_node_dict.keys():
        return virtual_node_dict[point], virtual_id
    else:
        virtual_node_dict[point] = virtual_id
        return virtual_id, virtual_id + 1


def ___set_crs(gdf: gpd.GeoDataFrame, epsg: int):
    if gdf.crs is None:
        gdf.crs = {'init': 'epsg:' + str(epsg)}
    else:
        gdf = gdf.to_crs({'init': 'epsg:' + str(epsg)})
    return gdf


def multilinestring_to_linestring(line, line_list):
    if isinstance(line, shapely.geometry.MultiLineString):
        for l in line:
            if isinstance(l, shapely.geometry.MultiLineString):
                line_list = multilinestring_to_linestring(l, line_list)
            else:
                line_list.append(l)
    return line_list


def bus_stops(df_bus_stop):
    # 　バス停リスト作成
    vals = []
    cols = [
        "stop_name",
        "lat",
        "lng",
        "category",
        "company_name",
        "route_name",
    ]
    # h3 indexを付与
    df_bus_stop = add_h3_index(df_bus_stop)

    # P11_002をsplitしたもののlenでループをまわし、一行ずつ新たにrowを作成する
    col_num_company = 2
    col_num_route = 21
    for row in tqdm(df_bus_stop.values):
        name, list_category, geom = row[0], row[1], row[-1]
        lat = geom.y
        lng = geom.x
        cnt = 0
        if list_category is not None:
            list_category = list_category.split(",")
            list_company, list_route = [], []
            for i in range(col_num_company, col_num_route):
                v = row[i]
                if v is None:
                    break
                else:
                    list_company.extend(v.split(","))

            for i in range(col_num_route, len(row) - 1):
                v = row[i]
                if v is None:
                    break
                else:
                    list_route.extend(v.split(","))

            for i in range(len(list_category)):
                category = list_category[i]
                company = list_company[i]
                route = list_route[i]
                vals.append([
                    name,
                    lat,
                    lng,
                    category,
                    company,
                    route
                ])

        else:
            vals.append([
                name,
                lat,
                lng,
                None,
                None,
                None
            ])
    df_stops = pd.DataFrame(vals, columns=cols)
    df_stops["id"] = df_stops.index + 1
    return df_stops

def bus_route(df_bus_route):
    df_bus_route = df_bus_route.rename(columns={
        'N07_001': 'category',
        'N07_002': 'company_name',
        'N07_003': 'route_name',
        'N07_004': 'freq_weekday',
        'N07_005': 'freq_saturday',
        'N07_006': 'freq_sunday',
        'N07_007': 'note',
        'length': 'route_length'
    })
    df_bus_route["id"] = df_bus_route.index + 1
    merged_route, merged_route_ids = [], []
    for row in tqdm(df_bus_route.values):
        category, company_name, route_name, route_id = row[0], row[1], row[2], row[9]

        if route_id in merged_route_ids:
            continue

        df_route_filter = df_bus_route[(df_bus_route["category"] == category) &
                                       (df_bus_route["company_name"] == company_name) &
                                       (df_bus_route["route_name"] == route_name)]
        if len(df_route_filter) >= 2:
            lines = []
            lines_org = list(df_route_filter["geometry"].values)
            for l in lines_org:
                lines = multilinestring_to_linestring(l, lines)

            merged_line = linemerge(lines)
            sum_length = np.sum(df_route_filter["route_length"].values)

            # 複数ヒットした場合はshapeをマージして，長さを合計する
            row[7] = sum_length
            row[8] = merged_line

            for i in df_route_filter["id"].values:
                if i not in merged_route_ids:
                    merged_route_ids.append(i)

        merged_route.append(row)

    return gpd.GeoDataFrame(merged_route, columns=df_bus_route.columns)


if __name__ == '__main__':

    df_bus_route_org = gpd.read_file("all/bus_route_all.gpkg", layer="bus_route_all_2")
    df_bus_stop_org = gpd.read_file("all/bus_stop_all.gpkg", layer="bus_stop_all")

    print("----------merge lines by category, company_name, route_name----------")
    df_bus_route = bus_route(df_bus_route_org)

    print("----------partition stops by route----------")
    df_stops = bus_stops(df_bus_stop_org)

    # 文字のゆらぎを変換させてdict化
    df_stops = format_yuragi(df_stops, ["company_name", "route_name"])
    df_stops.index = df_stops.id
    df_bus_route.index = df_bus_route.id
    df_bus_route = format_yuragi(df_bus_route, ["company_name", "route_name"])


    df_stops.index = df_stops.id
    stop_name_dict = df_stops["stop_name"].to_dict()
    stop_category_dict = df_stops["category"].to_dict()
    stop_company_name_dict = df_stops["company_name"].to_dict()
    stop_route_name_dict = df_stops["route_name"].to_dict()
    route_dict = df_bus_route[["category", "company_name", "route_name"]].to_dict(orient='index')

    rids = []
    print("----------join stops and route----------")
    for stop_id in tqdm(df_stops["id"].values):
        rids.append(get_route_id(stop_id))

    df_stops["route_id"] = rids
    # routeが紐付かないバス停は削除
    df_stops_a= df_stops[df_stops["route_id"] >= 0]

    df_stops_a = df_stops_a.rename(columns={'id': 'node_id'})
    df_bus_route = df_bus_route.rename(columns={'id': 'route_id', 'length': 'route_length'})

    df_stops_a.to_csv("out/nodes.csv", index=False)
    df_bus_route.to_file("out/route_m.shp", encoding='utf-8')

    #TODO 投影変換　epsg4614→2451


    exit()
