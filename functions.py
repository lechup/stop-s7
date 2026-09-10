import geopandas as gpd
import pandas as pd
import fiona
import shapely
import consts


def get_variant_path(variant):
  return "warianty/wariant{}.gml".format(variant)

def get_layers_per_variant(variant, what):
  layers = consts.LAYERS_DICT_PER_VARIANT.get(variant, {})
  return layers.get(what, [])

def generate():
  addresses = gpd.read_file("wojewodztwa-adresy/malopolska/NOWE_PRG_PunktyAdresowe_12.shp")

  for variant in consts.VARIANTS:
    variant_addresses_file_name = "raporty/wariant-{}-adresy.csv".format(variant)
    variant_polygon_file_name = "raporty/wariant-{}-polygon.gml".format(variant)
    variant_path = get_variant_path(variant)
    crs = None

    BUFFER_METERS = 200

    all_lines = []
    for layer in get_layers_per_variant(variant, consts.WAY):
      gdf = gpd.read_file(variant_path, layer=layer)
      crs = gdf.crs if crs is None else crs
      gdf = gdf.to_crs(crs)
      gdf["geometry"] = gdf.geometry.make_valid()
      all_lines.append(gdf.geometry.union_all())

    merged = shapely.unary_union(all_lines)
    road_polygon = merged.buffer(BUFFER_METERS).simplify(10)

    addresses_reproj = addresses.to_crs(crs)
    multilinestring_all_layers_gdf = gpd.GeoDataFrame(
        geometry=[road_polygon],
        crs=crs
    )

    multilinestring_all_layers_gdf.to_file(variant_polygon_file_name, driver="GML")
    variant_addresses = addresses_reproj.sjoin(multilinestring_all_layers_gdf, predicate="within")
    variant_addresses.to_csv(variant_addresses_file_name, index=False)
    print("Wygenerowałem plik {}!".format(variant_addresses_file_name))
    break

def debug():
  for variant in consts.VARIANTS:
    variant_path = get_variant_epath(variant)
    layers = fiona.listlayers(variant_path)
    print("Wariant {}:".format(variant), layers)
    print("---")

    addresses = gpd.read_file("wojewodztwa-adresy/malopolska/NOWE_PRG_PunktyAdresowe_12.shp")

    results = []

    for layer in layers:
      print("Warstwa '{}':".format(layer))
      gdf = gpd.read_file(variant_path, layer=layer)

      # ignoruj warstwy bez geometrii lub nie-polygon
      if gdf.empty or gdf.geometry.isna().all():
        print(" - pomijam (brak geometrii)")
        continue
      geom_type = gdf.geometry.geom_type.unique()
      if not any(t in ["Polygon", "MultiPolygon"] for t in geom_type):
        print(" - pomijam (nie poligon)")
        continue
      print(" - warstwa poligonowa ✓")

      # Dopasuj CRS
      addresses_reproj = addresses.to_crs(gdf.crs)
      # Spatial join
      inside = gpd.sjoin(addresses_reproj, gdf, predicate="within")
      inside["layer"] = layer
      results.append(inside)

    if results:
      final = gpd.GeoDataFrame(pd.concat(results, ignore_index=True))
      final.to_file("raporty/adresy-dla-wariantu-{}.geojson".format(variant), driver="GeoJSON")
      print("Dla wariantu {} znaleziono adresów {}!".format(variant, len(final)))
    else:
      print("Dla wariantu {} Nie znaleziono żadnych warstw poligonowych!".format(variant))
    print("")


