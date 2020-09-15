# bus_network_builder
国土数値情報のバス停・バスルートデータからネットワークデータを作成

作成手順
```

1. QGISで以下のshpファイルを開き，データをマージしてgpkgとして出力
https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11.html
https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N07.html

2. line_point_splitter.py　にて，　バス停・バスルートを路線ごとに分割し，node_id, route_idを採番
3. QGISで平面直角座標系（JGD2000 zon9 epsg:2451）に変換
4. route_splitter.py　にて，路線のLineStringをpointでedgeに分割

5. QGISでポイントから50ｍのバッファを作成し，ポイントとIntersect，ポイント側とバッファ側のnode_idがことなるものだけcsv出力
6. transfer_edges_maker.py　にて，別路線に乗り換えるためのリンクを作成
```
