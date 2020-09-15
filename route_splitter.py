import geopandas as gpd
from tqdm import tqdm
import shapely.wkt
from shapely.geometry import LineString, Point, MultiPoint
from shapely.ops import split, snap, nearest_points, linemerge


gcs_jgd = 4612  # jgd2000 latlon
pcs_jgd = 2451  # jgd2000　japanzone9
rounding=1 #xyの丸め桁数
virtual_id = 900000


if __name__ == '__main__':
    #read file (pcs)
    # TODO geopandasで gcs→pcs へと投影変換
    gdf_stop = gpd.read_file("all/pcs/bus_stop_p.shp", crs=pcs_jgd)
    gdf_route = gpd.read_file("all/pcs/route_p.shp", crs=pcs_jgd)


    # bus routeのlineをpointで分割し、両端にpoint加える

    #rounding = 1  # xyの丸め桁数
    starts, ends, routes, geoms, nodes, lengths = [], [], [], [], [], []
    categories, company_names, route_names, freq_weekdays, freq_saturdays, freq_sundays, notes = [],[],[],[],[],[],[]

    for route in tqdm(gdf_route.values):

        category, company_name, route_name,freq_weekday,freq_saturday,freq_sunday,note, route_length, route_id, shape = \
            route[0], route[1], route[2], route[3],route[4], route[5], route[6], route[7], route[8], route[9]

        points = []
        route_shp = shape
        df_stops_in_route = gdf_stop[gdf_stop["route_id"] == route_id]
        if len(df_stops_in_route) == 0:
            continue

        for g in df_stops_in_route["geometry"].values:
            points.append(shapely.wkt.loads(shapely.wkt.dumps(g, rounding_precision=rounding)))

        df_stops_in_route["geometry_round"] = points
        points = MultiPoint(points)

        snapped = snap(points, route_shp, tolerance=10)
        # snap後の座標とnode情報を紐付け
        nodeid_in_route = df_stops_in_route["node_id"].values
        node_dict = {}
        virtual_node_coords = []
        if isinstance(snapped, shapely.geometry.MultiPoint):
            for s in range(len(snapped)):
                # pcsでメートルXY座標なので，整数値にして判定
                node_dict[(int(snapped[s].coords[0][0]), int(snapped[s].coords[0][1]))] = nodeid_in_route[s]
        elif isinstance(snapped, shapely.geometry.Point):
            # 一点だけ
            node_dict[(int(snapped.coords[0][0]), int(snapped.coords[0][1]))] = nodeid_in_route[0]

        splitted = split(route_shp, snapped)
        for i in range(len(splitted)):

            line_points = splitted[i].coords
            start = (int(line_points[0][0]), int(line_points[0][1]))
            start_double = (line_points[0][0], line_points[0][1])

            end = (int(line_points[-1][0]), int(line_points[-1][1]))
            end_double = (line_points[-1][0], line_points[-1][1])
            start_id, end_id = 0, 0

            if start not in node_dict.keys():
                start_id = virtual_id
                virtual_id += 1
                node_dict[start] = start_id
                virtual_node_coords.append(start_double)
            else:
                start_id = node_dict[start]

            if end not in node_dict.keys():
                end_id = virtual_id
                virtual_id += 1
                node_dict[end] = end_id
                virtual_node_coords.append(end_double)
            else:
                end_id = node_dict[end]

        if isinstance(snapped, shapely.geometry.Point):
            starts.append(start_id)
            ends.append(end_id)
            routes.append(route_id)
            categories.append(category)
            company_names.append(company_name)
            route_names.append(route_name)
            freq_weekdays.append(freq_weekday)
            freq_saturdays.append(freq_saturday)
            freq_sundays.append(freq_sunday)
            notes.append(note)
            geoms.append(splitted[i])
            lengths.append(splitted[i].length)

        # 仮nodeも含めて再度split
        elif isinstance(snapped, shapely.geometry.MultiPoint):
            list_snapped = list(snapped)
            list_snapped.extend([Point(c) for c in virtual_node_coords])

            snapped = MultiPoint(list_snapped)
            splitted = split(route_shp, snapped)
            for i in range(len(splitted)):
                line_points = splitted[i].coords
                start = (int(line_points[0][0]), int(line_points[0][1]))

                end = (int(line_points[-1][0]), int(line_points[-1][1]))
                start_id = node_dict[start]
                end_id = node_dict[end]

                starts.append(start_id)
                ends.append(end_id)
                routes.append(route_id)
                categories.append(category)
                company_names.append(company_name)
                route_names.append(route_name)
                freq_weekdays.append(freq_weekday)
                freq_saturdays.append(freq_saturday)
                freq_sundays.append(freq_sunday)
                notes.append(note)
                geoms.append(splitted[i])
                lengths.append(splitted[i].length)


    gdf_edge = gpd.GeoDataFrame(geometry=geoms)
    gdf_edge["from_node_id"] = starts
    gdf_edge["to_node_id"] = ends
    gdf_edge["route_id"] = routes
    gdf_edge["length"] = lengths
    gdf_edge["category"] = categories
    gdf_edge["company_name"] = company_names
    gdf_edge["route_name"] = route_names
    gdf_edge["freq_weekday"] = freq_weekdays
    gdf_edge["freq_saturday"] = freq_saturdays
    gdf_edge["freq_sunday"] = freq_sundays
    gdf_edge["note"] = notes

    gdf_edge.to_file("out/edges.shp", encoding='utf-8')


    # G = nx.from_pandas_edgelist(gdf_route, edge_attr=True)
